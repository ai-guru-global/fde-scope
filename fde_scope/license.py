"""Offline license verification (commercialization tiering).

This is an *honesty mechanism, not DRM*: keys are self-contained
HMAC-signed payloads checked fully offline, with no phone-home, no
obfuscation and no attempt to stop a determined user from patching the
check out of this MIT-licensed codebase. The point is to give honest
customers a clear tier boundary (and a clear 402 when they hit it), not
to build a fortress.

Key format::

    base64url(json_payload) "." base64url(hmac_sha256(secret, payload_b64))

The signing secret comes from the ``FDE_SCOPE_LICENSE_SECRET`` environment
variable only (AGENTS.md invariant 3): it is never read from a file,
never written to disk, never logged and never echoed. When the variable
is unset, *every* key is invalid — there is no plaintext fallback secret
compiled into the package.

The license key itself is read from ``FDE_SCOPE_LICENSE_KEY`` first, then
from ``<data root>/.fde_scope/license.key``. An expired key does not lock
the user out: the install degrades to the community tier with a WARNING
in the log, so a lapsed renewal never strands a running engagement.

Nothing here is cached at import time: env vars are re-read on every call
so tests can ``monkeypatch.setenv`` freely.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from . import paths
from .logutil import get_logger

logger = get_logger("license")

ENV_LICENSE_KEY = "FDE_SCOPE_LICENSE_KEY"
ENV_LICENSE_SECRET = "FDE_SCOPE_LICENSE_SECRET"

#: Valid tiers, ordered by capability (index = rank).
Tier = Literal["community", "pro", "enterprise"]
TIER_ORDER: dict[str, int] = {"community": 0, "pro": 1, "enterprise": 2}

#: Default feature table per tier. A license payload may additionally carry
#: an explicit ``features`` list which is *unioned* with its tier defaults,
#: so a custom deal can grant a feature without minting a new tier.
_COMMUNITY_FEATURES = frozenset({"sop", "forge", "kpi", "connectors"})
_PRO_FEATURES = _COMMUNITY_FEATURES | frozenset({"audit_export", "evidence", "llm_synthesis"})

TIER_FEATURES: dict[str, frozenset[str]] = {
    "community": _COMMUNITY_FEATURES,
    "pro": _PRO_FEATURES,
    "enterprise": _PRO_FEATURES | frozenset({"deploy_serve", "multi_tenant"}),
}

KEY_FILENAME = "license.key"


class LicenseError(Exception):
    """Raised by issuing tooling (never by verification — verify fails closed)."""


class LicenseInfo(BaseModel):
    """A verified license payload (or the community fallback)."""

    license_id: str = ""
    customer: str = ""
    tier: Tier = "community"
    seats: int = 1
    expires_at: datetime | None = None
    #: Explicit feature grants on top of the tier defaults.
    features: list[str] = Field(default_factory=list)
    #: True when this record is the result of an expired key being downgraded.
    expired: bool = False

    def effective_features(self) -> frozenset[str]:
        return TIER_FEATURES[self.tier] | frozenset(self.features)

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        expiry = self.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return (now or datetime.now(UTC)) >= expiry


#: The no-key / invalid-key fallback: a working community install.
COMMUNITY_FALLBACK = LicenseInfo(license_id="", customer="", tier="community")


# ---------------------------------------------------------------------------
# signing / verification
# ---------------------------------------------------------------------------
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _secret() -> str | None:
    secret = os.environ.get(ENV_LICENSE_SECRET, "").strip()
    return secret or None


def _sign(payload_b64: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64e(digest)


def issue_license(
    customer: str,
    tier: Tier,
    seats: int = 1,
    expires_at: datetime | None = None,
    features: list[str] | None = None,
    license_id: str | None = None,
    secret: str | None = None,
) -> str:
    """Sign a license key for a customer (delivery tooling — vendor side).

    The secret defaults to ``FDE_SCOPE_LICENSE_SECRET``; without one there
    is deliberately no way to mint a key.
    """
    secret = secret if secret is not None else _secret()
    if not secret:
        raise LicenseError(f"{ENV_LICENSE_SECRET} is not set — cannot sign a license key")
    if tier not in TIER_ORDER:
        raise LicenseError(f"unknown tier: {tier!r}")
    info = LicenseInfo(
        license_id=license_id or f"lic-{uuid.uuid4().hex[:12]}",
        customer=customer,
        tier=tier,  # type: ignore[arg-type]
        seats=seats,
        expires_at=expires_at,
        features=features or [],
    )
    payload = json.dumps(info.model_dump(mode="json", exclude={"expired"}), sort_keys=True).encode("utf-8")
    payload_b64 = _b64e(payload)
    return f"{payload_b64}.{_sign(payload_b64, secret)}"


def parse_license(key: str, secret: str | None = None) -> LicenseInfo | None:
    """Verify and decode a key; ``None`` on any failure (fail closed).

    No exception carries key material, and nothing is logged beyond the
    failure category — the key is a credential-adjacent artifact.
    """
    secret = secret if secret is not None else _secret()
    if not secret:
        logger.warning("license key present but %s is not set — treating key as invalid", ENV_LICENSE_SECRET)
        return None
    payload_b64, sep, signature = key.strip().partition(".")
    if not sep or not payload_b64 or not signature:
        return None
    if not hmac.compare_digest(_sign(payload_b64, secret), signature):
        return None
    try:
        data = json.loads(_b64d(payload_b64))
        return LicenseInfo.model_validate(data)
    except (ValueError, TypeError, KeyError):
        return None


# ---------------------------------------------------------------------------
# loading / tier API
# ---------------------------------------------------------------------------
def _read_key() -> str | None:
    key = os.environ.get(ENV_LICENSE_KEY, "").strip()
    if key:
        return key
    path = paths.data_root() / paths.DATA_SUBDIR / KEY_FILENAME
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        logger.warning("could not read license file %s", path)
    return None


def load_license() -> LicenseInfo:
    """Resolve the effective license: env key → key file → community.

    A *valid but expired* key downgrades to community with a WARNING —
    the customer keeps a working system and a clear signal to renew.
    """
    key = _read_key()
    if key is None:
        return COMMUNITY_FALLBACK
    info = parse_license(key)
    if info is None:
        return COMMUNITY_FALLBACK
    if info.is_expired():
        logger.warning(
            "license %s for %r expired at %s — downgrading to community tier",
            info.license_id,
            info.customer,
            info.expires_at,
        )
        return LicenseInfo(
            license_id=info.license_id,
            customer=info.customer,
            tier="community",
            seats=1,
            expires_at=info.expires_at,
            expired=True,
        )
    return info


def current_tier() -> Tier:
    """The effective tier right now (``community`` without a valid key)."""
    return load_license().tier


def has_feature(name: str) -> bool:
    """True when the effective license grants ``name``."""
    return name in load_license().effective_features()


def check_seats(n: int) -> bool:
    """True when the effective license covers at least ``n`` seats."""
    return load_license().seats >= n


def tier_at_least(tier: str) -> bool:
    """True when the effective tier ranks at or above ``tier``."""
    return TIER_ORDER[current_tier()] >= TIER_ORDER.get(tier, 0)

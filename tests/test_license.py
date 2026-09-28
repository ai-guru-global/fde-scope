"""Tests for fde_scope.license — offline HMAC-signed license keys."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fde_scope import license as lic
from fde_scope.cli import app

runner = CliRunner()

SECRET = "unit-test-secret"


@pytest.fixture
def licensed(monkeypatch: pytest.MonkeyPatch):
    """Set a secret and return an issue() helper bound to it."""

    def issue(**kwargs):
        monkeypatch.setenv(lic.ENV_LICENSE_SECRET, SECRET)
        return lic.issue_license(secret=SECRET, **kwargs)

    return issue


def test_issue_parse_roundtrip(monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    key = licensed(customer="Aurora Motors", tier="pro", seats=10, features=["custom_flag"])
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, key)
    info = lic.load_license()
    assert info.customer == "Aurora Motors"
    assert info.tier == "pro"
    assert info.seats == 10
    assert info.license_id.startswith("lic-")
    assert "audit_export" in info.effective_features()  # tier default
    assert "custom_flag" in info.effective_features()  # explicit grant


def test_tampered_signature_rejected(monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    key = licensed(customer="Mallory", tier="enterprise", seats=999)
    payload, _, sig = key.partition(".")
    forged = f"{payload}.{sig[:-2]}{'A' if sig[-2] != 'A' else 'B'}{sig[-1]}"
    assert lic.parse_license(forged) is None
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, forged)
    assert lic.current_tier() == "community"
    assert not lic.has_feature("audit_export")


def test_tampered_payload_rejected(licensed) -> None:
    key = licensed(customer="Aurora", tier="pro")
    payload, _, _ = key.partition(".")
    # re-encode a different payload but keep the old signature
    import base64
    import json

    raw = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    raw["tier"] = "enterprise"
    forged_payload = base64.urlsafe_b64encode(json.dumps(raw).encode()).decode().rstrip("=")
    assert lic.parse_license(f"{forged_payload}.{key.partition('.')[2]}") is None


def test_missing_secret_invalidates_everything(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    key = lic.issue_license(customer="Aurora", tier="enterprise", secret=SECRET)
    monkeypatch.delenv(lic.ENV_LICENSE_SECRET, raising=False)
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, key)
    with caplog.at_level(logging.WARNING, logger="fde_scope.license"):
        info = lic.load_license()
    assert info.tier == "community"
    assert not lic.has_feature("deploy_serve")
    assert any(lic.ENV_LICENSE_SECRET in r.message for r in caplog.records)
    assert key not in caplog.text and SECRET not in caplog.text  # credentials never logged


def test_wrong_secret_rejected(licensed) -> None:
    key = licensed(customer="Aurora", tier="pro")
    assert lic.parse_license(key, secret="a-different-secret") is None


def test_expired_license_downgrades_with_warning(
    monkeypatch: pytest.MonkeyPatch, licensed, caplog: pytest.LogCaptureFixture
) -> None:
    key = licensed(
        customer="Aurora", tier="enterprise", seats=20, expires_at=datetime.now(UTC) - timedelta(days=1)
    )
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, key)
    with caplog.at_level(logging.WARNING, logger="fde_scope.license"):
        info = lic.load_license()
    assert info.tier == "community"
    assert info.expired is True
    assert info.customer == "Aurora"  # identity kept for the renewal conversation
    assert lic.current_tier() == "community"
    assert not lic.has_feature("audit_export")
    assert any("expired" in r.message.lower() for r in caplog.records)


def test_future_expiry_stays_valid(monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    key = licensed(customer="Aurora", tier="pro", expires_at=datetime.now(UTC) + timedelta(days=30))
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, key)
    info = lic.load_license()
    assert info.tier == "pro"
    assert info.expired is False


def test_no_key_is_community(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(lic.ENV_LICENSE_KEY, raising=False)
    assert lic.current_tier() == "community"
    assert lic.has_feature("sop") and lic.has_feature("forge")
    assert not lic.has_feature("audit_export")
    assert not lic.has_feature("deploy_serve")


def test_key_file_fallback(monkeypatch: pytest.MonkeyPatch, licensed, tmp_path: Path) -> None:
    monkeypatch.delenv(lic.ENV_LICENSE_KEY, raising=False)
    key = licensed(customer="FileCo", tier="pro")
    key_dir = tmp_path / ".fde_scope"
    key_dir.mkdir()
    (key_dir / "license.key").write_text(key + "\n", encoding="utf-8")
    monkeypatch.setenv("FDE_SCOPE_HOME", str(tmp_path))
    info = lic.load_license()
    assert info.customer == "FileCo"
    assert info.tier == "pro"


def test_env_key_beats_key_file(monkeypatch: pytest.MonkeyPatch, licensed, tmp_path: Path) -> None:
    key_dir = tmp_path / ".fde_scope"
    key_dir.mkdir()
    (key_dir / "license.key").write_text(licensed(customer="FileCo", tier="pro"), encoding="utf-8")
    monkeypatch.setenv("FDE_SCOPE_HOME", str(tmp_path))
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, licensed(customer="EnvCo", tier="enterprise"))
    assert lic.load_license().customer == "EnvCo"


def test_malformed_keys_fail_closed(licensed) -> None:
    for junk in ("", "not-a-key", "onlyonepart", "..", "aaa.bbb.ccc"):
        assert lic.parse_license(junk) is None


def test_check_seats(monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, licensed(customer="Aurora", tier="pro", seats=5))
    assert lic.check_seats(5)
    assert not lic.check_seats(6)
    monkeypatch.delenv(lic.ENV_LICENSE_KEY, raising=False)
    assert lic.check_seats(1)  # community fallback: 1 seat
    assert not lic.check_seats(2)


def test_tier_ordering(monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, licensed(customer="Aurora", tier="enterprise"))
    assert lic.tier_at_least("pro")
    assert lic.tier_at_least("enterprise")


def test_issue_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(lic.ENV_LICENSE_SECRET, raising=False)
    with pytest.raises(lic.LicenseError):
        lic.issue_license(customer="Aurora", tier="pro")


def test_issue_rejects_unknown_tier() -> None:
    with pytest.raises(lic.LicenseError):
        lic.issue_license(customer="Aurora", tier="gold", secret=SECRET)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def test_cli_license_shows_tier(monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, licensed(customer="Aurora", tier="pro", seats=3))
    result = runner.invoke(app, ["license"])
    assert result.exit_code == 0, result.stdout
    assert "pro" in result.stdout
    assert "Aurora" in result.stdout
    assert "audit_export" in result.stdout


def test_cli_license_without_key_is_community(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(lic.ENV_LICENSE_KEY, raising=False)
    result = runner.invoke(app, ["license"])
    assert result.exit_code == 0
    assert "community" in result.stdout


def test_cli_license_issue_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(lic.ENV_LICENSE_SECRET, SECRET)
    out = tmp_path / "aurora.key"
    result = runner.invoke(
        app,
        [
            "license-issue",
            "--customer",
            "Aurora",
            "--tier",
            "enterprise",
            "--seats",
            "7",
            "--expires",
            "2099-01-01",
            "--features",
            "beta_flag",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert SECRET not in result.stdout
    key = out.read_text(encoding="utf-8").strip()
    info = lic.parse_license(key)
    assert info is not None
    assert info.tier == "enterprise" and info.seats == 7
    assert "beta_flag" in info.effective_features()


def test_cli_license_issue_needs_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(lic.ENV_LICENSE_SECRET, raising=False)
    result = runner.invoke(app, ["license-issue", "--customer", "Aurora", "--tier", "pro"])
    assert result.exit_code == 2


def test_cli_license_issue_rejects_bad_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(lic.ENV_LICENSE_SECRET, SECRET)
    result = runner.invoke(
        app, ["license-issue", "--customer", "Aurora", "--tier", "pro", "--expires", "soon"]
    )
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# web tier gate (402)
# ---------------------------------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app as web_app

    return TestClient(web_app)


def _mk_engagement(client) -> str:
    r = client.post("/api/engagements", data={"customer": "GateCo", "profile": "ticket"})
    return r.json()["engagement_id"]


def test_web_pro_routes_402_without_key(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(lic.ENV_LICENSE_KEY, raising=False)
    eid = _mk_engagement(client)
    r = client.get(f"/api/engagements/{eid}/audit/export")
    assert r.status_code == 402
    assert "pro or enterprise" in r.json()["detail"]
    assert "community" in r.json()["detail"]
    r = client.post(
        f"/api/engagements/{eid}/evidence",
        data={"name": "fat.pdf"},
        files={"file": ("fat.pdf", b"signed")},
    )
    assert r.status_code == 402


def test_web_pro_routes_pass_with_pro_key(client, monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, licensed(customer="GateCo", tier="pro"))
    eid = _mk_engagement(client)
    r = client.get(f"/api/engagements/{eid}/audit/export")
    assert r.status_code == 200
    r = client.post(
        f"/api/engagements/{eid}/evidence",
        data={"name": "fat.pdf"},
        files={"file": ("fat.pdf", b"signed")},
    )
    assert r.status_code == 200


def test_web_402_with_expired_key(client, monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    monkeypatch.setenv(
        lic.ENV_LICENSE_KEY,
        licensed(customer="GateCo", tier="pro", expires_at=datetime.now(UTC) - timedelta(hours=1)),
    )
    eid = _mk_engagement(client)
    assert client.get(f"/api/engagements/{eid}/audit/export").status_code == 402


def test_web_enterprise_covers_pro_features(client, monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, licensed(customer="GateCo", tier="enterprise"))
    eid = _mk_engagement(client)
    assert client.get(f"/api/engagements/{eid}/audit/export").status_code == 200


def test_web_402_detail_never_carries_key(client, monkeypatch: pytest.MonkeyPatch, licensed) -> None:
    key = licensed(customer="GateCo", tier="pro")
    forged = key[:-2] + ("AA" if not key.endswith("AA") else "BB")
    monkeypatch.setenv(lic.ENV_LICENSE_KEY, forged)
    eid = _mk_engagement(client)
    r = client.get(f"/api/engagements/{eid}/audit/export")
    assert r.status_code == 402
    assert forged not in r.text and SECRET not in r.text

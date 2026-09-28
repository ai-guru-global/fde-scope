"""Salesforce CRM connector — real REST API implementation.

Talks to the Salesforce REST API (``GET {instance_url}/services/data/vXX.X/query``
with ``Authorization: Bearer <access_token>``) using only ``urllib`` — zero new
dependencies, same transport discipline as the Zammad connector.

Configuration (AGENTS.md invariant 3 — credentials live in env vars only and
never appear in logs, exceptions or persisted records):

- ``FDE_SCOPE_SF_INSTANCE_URL`` — e.g. ``https://acme.my.salesforce.com``
- ``FDE_SCOPE_SF_ACCESS_TOKEN`` — an OAuth access token for the instance

The constructor also accepts the CLI's uniform ``api_key``/``access_token``
options and a URL ``source``; explicit options win over the environment.
Token acquisition (OAuth flows) is intentionally out of scope — obtain the
access token outside the connector (CI secret, short-lived session token) so
no client secret ever enters this process's config surface.

Mode selection (decided once, at construction), mirroring the Zammad
connector:

1. **HTTP mode** — instance URL *and* access token resolve (options and/or env).
2. **JSONL replay mode** — ``source`` is a path to an existing ``.jsonl``
   file (one Case dict per line); fully offline.
3. **Unconfigured mode** — neither of the above: the connector stays
   selectable (schema contract intact) but ``extract_sample``/``stream``
   yield nothing, exactly like the pre-P3 skeleton.

Partial env configuration (only one of instance URL / token set) logs a
WARNING and falls back to the non-HTTP modes — never raises at import or CLI
level.

Case rows are normalized onto the corpus engine's contract
(``content``/``category``/``id`` …): ``Origin`` → ``channel``, ``Status`` →
``state``, ``Description`` (falling back to ``Subject``) → ``content``.

The connector is a strictly read-only channel: the SOQL query must start with
``SELECT``; anything else is rejected before a request is made.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..logutil import get_logger
from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

logger = get_logger("connectors.salesforce")

ENV_INSTANCE_URL = "FDE_SCOPE_SF_INSTANCE_URL"
ENV_ACCESS_TOKEN = "FDE_SCOPE_SF_ACCESS_TOKEN"

# urllib's urlopen() takes a single timeout covering connect + read (see the
# Zammad connector for the rationale).
_TIMEOUT_SECONDS = 30.0
# Salesforce caps query pages at 2000 records by default.
_PAGE_SIZE = 2000

_DEFAULT_SOQL = (
    "SELECT Id, CaseNumber, Subject, Description, Status, Priority, Origin, "
    "CreatedDate FROM Case ORDER BY CreatedDate DESC"
)


class SalesforceError(RuntimeError):
    """Raised when the Salesforce API call fails (network, auth, or protocol).

    Messages carry HTTP status and endpoint context only — never the token.
    """


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def _validate_soql(soql: str) -> str:
    """Reject anything but a read-only SELECT before it reaches the wire."""
    normalized = soql.strip()
    if not normalized[:7].upper().startswith("SELECT"):
        raise SalesforceError("SOQL query must start with SELECT (connector is read-only)")
    upper = normalized.upper()
    for keyword in ("DELETE", "UPDATE", "INSERT", "UPSERT", "MERGE"):
        if keyword in upper:
            raise SalesforceError(f"SOQL query contains forbidden keyword {keyword}")
    return normalized


def _normalize_case(record: dict[str, Any]) -> dict[str, Any]:
    """Map a Salesforce Case record onto the corpus engine's row contract."""
    subject = record.get("Subject")
    description = record.get("Description")
    return {
        "id": record.get("Id"),
        "number": record.get("CaseNumber"),
        "title": subject,
        "category": record.get("Priority"),
        "state": record.get("Status"),
        "channel": record.get("Origin"),
        "content": description or subject,
        "created_at": record.get("CreatedDate"),
    }


def _contract_schema(source: str) -> Schema:
    return Schema(
        source=source,
        row_count=None,
        fields=[
            SchemaField(name="id", inferred_type="string"),
            SchemaField(name="number", inferred_type="string"),
            SchemaField(name="title", inferred_type="string"),
            SchemaField(name="category", inferred_type="string"),
            SchemaField(name="state", inferred_type="string"),
            SchemaField(name="channel", inferred_type="string"),
            SchemaField(name="content", inferred_type="string", pii_candidate=True),
            SchemaField(name="created_at", inferred_type="string"),
        ],
    )


@register
class SalesforceConnector(DataConnector):
    """Connect to Salesforce (Case object) via the REST API."""

    type = "salesforce"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        # Instance URL: a URL `source` wins, then the env var.
        if "://" in source:
            self.instance_url: str | None = source.rstrip("/")
        else:
            self.instance_url = _env(ENV_INSTANCE_URL)
        # Token: options (CLI's uniform `api_key`) win, then the env var.
        self.access_token = (
            options.get("access_token") or options.get("api_key") or _env(ENV_ACCESS_TOKEN) or ""
        )
        self.api_version = str(options.get("api_version", "59.0"))
        self._soql = _validate_soql(str(options.get("soql", _DEFAULT_SOQL)))
        self._jsonl_path: Path | None = None
        if "://" not in source:
            candidate = Path(source)
            if candidate.suffix == ".jsonl" and candidate.is_file():
                self._jsonl_path = candidate
        if bool(self.instance_url) != bool(self.access_token):
            logger.warning(
                "incomplete Salesforce configuration (%s without %s); falling back to non-HTTP mode",
                ENV_INSTANCE_URL if self.instance_url else ENV_ACCESS_TOKEN,
                ENV_ACCESS_TOKEN if self.instance_url else ENV_INSTANCE_URL,
            )

    # -- mode -------------------------------------------------------------------
    @property
    def _http_mode(self) -> bool:
        return bool(self.instance_url and self.access_token)

    # -- HTTP transport ---------------------------------------------------------
    def _get(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            method="GET",
        )
        logger.debug("Salesforce query request: %s", url.split("?")[0])
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            logger.warning("Salesforce query failed: HTTP %d", exc.code)
            raise SalesforceError(f"Salesforce API HTTP {exc.code} (GET query)") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Salesforce query failed: %s", type(exc).__name__)
            raise SalesforceError(f"Salesforce API request failed (GET query): {type(exc).__name__}") from exc
        if not isinstance(body, dict):
            raise SalesforceError(f"unexpected Salesforce response shape: {str(body)[:200]!r}")
        return body

    def _query_url(self, soql: str) -> str:
        assert self.instance_url is not None  # callers gate on _http_mode
        return f"{self.instance_url}/services/data/v{self.api_version}/query?q={urllib.parse.quote(soql)}"

    def _iter_http_rows(self, soql: str) -> Iterator[dict[str, Any]]:
        body = self._get(self._query_url(soql))
        while True:
            records = body.get("records") or []
            for record in records:
                yield _normalize_case(record)
            if body.get("done", True) or not body.get("nextRecordsUrl"):
                return
            assert self.instance_url is not None
            body = self._get(self.instance_url + body["nextRecordsUrl"])

    # -- JSONL replay -----------------------------------------------------------
    def _iter_jsonl_rows(self) -> Iterator[dict[str, Any]]:
        assert self._jsonl_path is not None  # callers gate on it
        with open(self._jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if isinstance(record, dict):
                    yield record

    # -- the three-step contract -----------------------------------------------
    def discover_schema(self) -> Schema:
        if self._http_mode:
            # Probe with a one-row query so a bad token fails here, cheaply.
            probe = _validate_soql(self._soql)
            for _ in self._iter_http_rows(f"{probe} LIMIT 1"):
                break
            return _contract_schema(self.instance_url or self.source)
        if self._jsonl_path is not None:
            row_count = sum(1 for _ in self._iter_jsonl_rows())
            schema = _contract_schema(str(self._jsonl_path))
            return schema.model_copy(update={"row_count": row_count})
        return _contract_schema(self.source)

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        if n < 1:
            raise ValueError(f"extract_sample requires n >= 1 (got {n})")
        out: list[dict[str, Any]] = []
        if self._http_mode:
            soql = f"{self._soql} LIMIT {n}"
            for row in self._iter_http_rows(soql):
                out.append(row)
                if len(out) >= n:
                    break
        elif self._jsonl_path is not None:
            for row in self._iter_jsonl_rows():
                out.append(row)
                if len(out) >= n:
                    break
        else:
            logger.warning(
                "Salesforce connector is unconfigured (set %s and %s, or pass a "
                ".jsonl source); returning empty sample",
                ENV_INSTANCE_URL,
                ENV_ACCESS_TOKEN,
            )
        return out

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        if batch_size < 1:
            raise ValueError(f"stream requires batch_size >= 1 (got {batch_size})")
        if self._http_mode:
            rows: Iterator[dict[str, Any]] = self._iter_http_rows(self._soql)
            source = self.instance_url or self.source
        elif self._jsonl_path is not None:
            rows = self._iter_jsonl_rows()
            source = str(self._jsonl_path)
        else:
            logger.warning(
                "Salesforce connector is unconfigured (set %s and %s, or pass a "
                ".jsonl source); stream yields nothing",
                ENV_INSTANCE_URL,
                ENV_ACCESS_TOKEN,
            )
            return
        batch: list[dict[str, Any]] = []
        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                yield Batch(batch, source=source)
                batch = []
        if batch:
            yield Batch(batch, source=source)

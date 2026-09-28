"""Zammad (open-source ticketing) connector — real HTTP implementation.

Talks to the Zammad REST API (``GET {base_url}/api/v1/tickets`` with
``Authorization: Token token=<api_token>``) using only ``urllib`` — zero new
dependencies, same transport discipline as ``fde_scope/llm.py``.

Configuration (AGENTS.md invariant 3 — credentials live in env vars only and
never appear in logs, exceptions or persisted records):

- ``FDE_SCOPE_ZAMMAD_BASE_URL`` — e.g. ``https://support.example.com``
- ``FDE_SCOPE_ZAMMAD_API_TOKEN`` — a Zammad API access token

The constructor also accepts the CLI's uniform ``api_key``/``token`` options
and a URL ``source``; explicit options win over the environment.

Mode selection (decided once, at construction):

1. **HTTP mode** — base URL *and* token resolve (options and/or env).
2. **JSONL replay mode** — ``source`` is a path to an existing ``.jsonl``
   file (one ticket dict per line); fully offline, mirrors the MES/MQTT
   connectors' replay path.
3. **Unconfigured mode** — neither of the above: the connector stays
   selectable (schema contract intact) but ``extract_sample``/``stream``
   yield nothing, exactly like the pre-P3 skeleton.

Partial env configuration (only one of base URL / token set) logs a WARNING
and falls back to the non-HTTP modes — never raises at import or CLI level.

Ticket rows are normalized onto the corpus engine's contract
(``content``/``category``/``id`` …): Zammad ``group`` → ``category``,
``state`` → ``state``, ticket ``note`` (falling back to ``title``) →
``content``. Requests use ``expand=true`` so ``group``/``state`` arrive as
names rather than ids.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..logutil import get_logger
from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

logger = get_logger("connectors.zammad")

ENV_BASE_URL = "FDE_SCOPE_ZAMMAD_BASE_URL"
ENV_API_TOKEN = "FDE_SCOPE_ZAMMAD_API_TOKEN"

# urllib's urlopen() takes a single timeout covering connect + read; 30s is
# the read budget (a hung connect typically fails well inside it on any
# reasonable network, and the FDE workflow is interactive).
_TIMEOUT_SECONDS = 30.0
# Zammad caps per-page at 100; larger values are silently clamped server-side.
_PAGE_SIZE = 100


class ZammadError(RuntimeError):
    """Raised when the Zammad API call fails (network, auth, or protocol).

    Messages carry HTTP status and endpoint context only — never the token.
    """


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def _normalize_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    """Map a Zammad ticket object onto the corpus engine's row contract."""
    note = ticket.get("note")
    title = ticket.get("title")
    return {
        "id": ticket.get("id"),
        "number": ticket.get("number"),
        "title": title,
        "note": note,
        "category": ticket.get("group") or ticket.get("group_id"),
        "state": ticket.get("state") or ticket.get("state_id"),
        "channel": ticket.get("create_article_type") or ticket.get("channel"),
        # The ticket list endpoint carries no article body; the ticket note
        # (falling back to the title) is the closest text field.
        "content": note or title,
        "created_at": ticket.get("created_at"),
    }


def _contract_schema(source: str) -> Schema:
    return Schema(
        source=source,
        row_count=None,
        fields=[
            SchemaField(name="id", inferred_type="int"),
            SchemaField(name="number", inferred_type="string"),
            SchemaField(name="title", inferred_type="string"),
            SchemaField(name="note", inferred_type="string", pii_candidate=True),
            SchemaField(name="category", inferred_type="string"),
            SchemaField(name="state", inferred_type="string"),
            SchemaField(name="channel", inferred_type="string"),
            SchemaField(name="content", inferred_type="string"),
        ],
    )


@register
class ZammadConnector(DataConnector):
    """Connect to a Zammad ticketing instance via its REST API."""

    type = "zammad"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        # Base URL: a URL `source` wins, then the env var.
        if "://" in source:
            self.base_url: str | None = source.rstrip("/")
        else:
            self.base_url = _env(ENV_BASE_URL)
        # Token: options (CLI's uniform `api_key`) win, then the env var.
        self.api_key = options.get("api_key") or options.get("token") or _env(ENV_API_TOKEN) or ""
        self._jsonl_path: Path | None = None
        if "://" not in source:
            candidate = Path(source)
            if candidate.suffix == ".jsonl" and candidate.is_file():
                self._jsonl_path = candidate
        if bool(self.base_url) != bool(self.api_key):
            logger.warning(
                "incomplete Zammad configuration (%s without %s); falling back to non-HTTP mode",
                ENV_BASE_URL if self.base_url else ENV_API_TOKEN,
                ENV_API_TOKEN if self.base_url else ENV_BASE_URL,
            )

    # -- mode -------------------------------------------------------------------
    @property
    def _http_mode(self) -> bool:
        return bool(self.base_url and self.api_key)

    # -- HTTP transport ---------------------------------------------------------
    def _get_tickets_page(self, *, page: int, limit: int) -> list[dict[str, Any]]:
        assert self.base_url is not None  # callers gate on _http_mode
        url = f"{self.base_url}/api/v1/tickets?expand=true&limit={limit}&page={page}"
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Token token={self.api_key}"},
            method="GET",
        )
        logger.debug("Zammad tickets request: page=%d limit=%d", page, limit)
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            logger.warning("Zammad tickets request failed: HTTP %d", exc.code)
            raise ZammadError(f"Zammad API HTTP {exc.code} (GET /api/v1/tickets)") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Zammad tickets request failed: %s", type(exc).__name__)
            raise ZammadError(
                f"Zammad API request failed (GET /api/v1/tickets): {type(exc).__name__}"
            ) from exc
        if not isinstance(body, list):
            raise ZammadError(f"unexpected Zammad response shape: {str(body)[:200]!r}")
        return body

    def _iter_http_rows(self) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            tickets = self._get_tickets_page(page=page, limit=_PAGE_SIZE)
            if not tickets:
                return
            for ticket in tickets:
                yield _normalize_ticket(ticket)
            if len(tickets) < _PAGE_SIZE:
                return
            page += 1

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
            # Probe with a single-ticket page so a bad token fails here, cheaply.
            self._get_tickets_page(page=1, limit=1)
            return _contract_schema(self.base_url or self.source)
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
            for row in self._iter_http_rows():
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
                "Zammad connector is unconfigured (set %s and %s, or pass a .jsonl source); "
                "returning empty sample",
                ENV_BASE_URL,
                ENV_API_TOKEN,
            )
        return out

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        if batch_size < 1:
            raise ValueError(f"stream requires batch_size >= 1 (got {batch_size})")
        if self._http_mode:
            rows: Iterator[dict[str, Any]] = self._iter_http_rows()
            source = self.base_url or self.source
        elif self._jsonl_path is not None:
            rows = self._iter_jsonl_rows()
            source = str(self._jsonl_path)
        else:
            logger.warning(
                "Zammad connector is unconfigured (set %s and %s, or pass a .jsonl source); "
                "stream yields nothing",
                ENV_BASE_URL,
                ENV_API_TOKEN,
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

"""MES connector — ISA-95 Level 3 manufacturing execution data.

Talks to a MES over HTTP (``GET {base_url}/api/v1/work-orders?limit=N&offset=M``
with ``Authorization: Bearer <api_token>``) using only ``urllib`` — zero new
dependencies, same transport discipline as the Zammad/Salesforce connectors.

The endpoint is modeled on the common MES REST convention (SAP DMC, Apriso,
Camstar-style public APIs all expose a list-of-work-orders resource); a
specific customer installation can override the path via the ``endpoint``
option (e.g. ``endpoint="/api/production/orders"``).

Configuration (AGENTS.md invariant 3 — credentials live in env vars only and
never appear in logs, exceptions or persisted records):

- ``FDE_SCOPE_MES_BASE_URL`` — e.g. ``https://mes.plant.example.com``
- ``FDE_SCOPE_MES_API_TOKEN`` — a Bearer token issued by the MES

The constructor also accepts the CLI's uniform ``api_key``/``token`` options
and a URL ``source``; explicit options win over the environment.

Mode selection (decided once, at construction):

1. **HTTP mode** — base URL *and* token resolve (options and/or env).
2. **JSONL replay mode** — ``source`` is a path to an existing JSONL export
   (one record per line: work-order / quality / downtime); the cold-start
   path an FDE uses when the live API isn't reachable yet.
3. **Unconfigured mode** — neither of the above: the connector stays
   selectable (schema contract intact) but ``extract_sample``/``stream``
   yield nothing, exactly like the pre-P3 skeleton.

Partial env configuration (only one of base URL / token set) logs a WARNING
and falls back to the non-HTTP modes — never raises at import or CLI level.

Work-order rows are normalized onto the corpus engine's contract
(``content``/``category``/``id`` …): MES ``order_id`` → ``id``,
``product`` → ``category``, ``status`` → ``state``, ``description`` →
``content``; ``quantity``/``defect_count`` and friends pass through.

Industry note: ISA-95 Level 3 (MES) is the bridge between the plant floor
(L0-2) and ERP (L4). This is where downtime reason codes, FPY, and
genealogy live.
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

logger = get_logger("connectors.mes")

ENV_BASE_URL = "FDE_SCOPE_MES_BASE_URL"
ENV_API_TOKEN = "FDE_SCOPE_MES_API_TOKEN"

# urllib's urlopen() takes a single timeout covering connect + read; 30s is
# the read budget (a hung connect typically fails well inside it on any
# reasonable network, and the FDE workflow is interactive).
_TIMEOUT_SECONDS = 30.0
# Page size for limit/offset pagination; larger values are commonly clamped
# server-side by MES REST gateways.
_PAGE_SIZE = 100
# Default work-orders list path; override via the `endpoint` option.
_DEFAULT_ENDPOINT = "/api/v1/work-orders"


class MesError(RuntimeError):
    """Raised when the MES API call fails (network, auth, or protocol).

    Messages carry HTTP status and endpoint context only — never the token.
    """


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def _normalize_work_order(order: dict[str, Any]) -> dict[str, Any]:
    """Map a MES work-order object onto the corpus engine's row contract."""
    return {
        "id": order.get("order_id") or order.get("id"),
        "category": order.get("product"),
        "state": order.get("status"),
        "quantity": order.get("quantity"),
        "defect_count": order.get("defect_count"),
        "content": order.get("description"),
    }


# Per-entity field shapes (used by discover_schema for all modes).
_FIELDS_BY_ENTITY: dict[str, list[SchemaField]] = {
    "work_orders": [
        SchemaField(name="work_order_id", inferred_type="string"),
        SchemaField(name="product", inferred_type="string"),
        SchemaField(name="planned_qty", inferred_type="int"),
        SchemaField(name="good_qty", inferred_type="int"),
        SchemaField(name="started_units", inferred_type="int"),
        SchemaField(name="status", inferred_type="string"),
    ],
    "downtime": [
        SchemaField(name="asset", inferred_type="string"),
        SchemaField(name="reason_code", inferred_type="string"),
        SchemaField(name="duration_minutes", inferred_type="float"),
        SchemaField(name="shift", inferred_type="string"),
    ],
    "quality": [
        SchemaField(name="serial", inferred_type="string"),
        SchemaField(name="defect_class", inferred_type="string"),
        SchemaField(name="station", inferred_type="string"),
    ],
    # KPI-per-station records (the quickstart_manufacturing shape).
    "station_kpi": [
        SchemaField(name="station", inferred_type="string"),
        SchemaField(name="availability", inferred_type="float"),
        SchemaField(name="performance", inferred_type="float"),
        SchemaField(name="quality", inferred_type="float"),
        SchemaField(name="uptime_hours", inferred_type="float"),
        SchemaField(name="failures", inferred_type="int"),
        SchemaField(name="grasp_successes", inferred_type="int"),
        SchemaField(name="grasp_attempts", inferred_type="int"),
        SchemaField(name="interventions", inferred_type="int"),
        SchemaField(name="cycles", inferred_type="int"),
    ],
}


@register
class MesConnector(DataConnector):
    """Connect to a Manufacturing Execution System (ISA-95 Level 3).

    ``source`` is either a URL (live REST API) or a path to a JSONL export;
    the connector auto-detects which. HTTP mode additionally requires a
    token (options or ``FDE_SCOPE_MES_API_TOKEN``).
    """

    type = "mes"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.entity = options.get("entity", "work_orders")
        # Base URL: a URL `source` wins, then the env var.
        if "://" in source:
            self.base_url: str | None = source.rstrip("/")
        else:
            self.base_url = _env(ENV_BASE_URL)
        # Token: options (CLI's uniform `api_key`) win, then the env var.
        self.api_token = options.get("api_key") or options.get("token") or _env(ENV_API_TOKEN) or ""
        # Endpoint path: option wins, else the common MES REST convention.
        endpoint = str(options.get("endpoint") or _DEFAULT_ENDPOINT)
        self.endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self._jsonl_path: Path | None = None
        if "://" not in source:
            candidate = Path(source)
            if candidate.suffix == ".jsonl" and candidate.is_file():
                self._jsonl_path = candidate
        if bool(self.base_url) != bool(self.api_token):
            logger.warning(
                "incomplete MES configuration (%s without %s); falling back to non-HTTP mode",
                ENV_BASE_URL if self.base_url else ENV_API_TOKEN,
                ENV_API_TOKEN if self.base_url else ENV_BASE_URL,
            )

    # -- mode -------------------------------------------------------------------
    @property
    def _http_mode(self) -> bool:
        return bool(self.base_url and self.api_token)

    @property
    def _is_jsonl(self) -> bool:
        return self._jsonl_path is not None

    # -- HTTP transport ---------------------------------------------------------
    def _get_work_orders_page(self, *, offset: int, limit: int) -> list[dict[str, Any]]:
        assert self.base_url is not None  # callers gate on _http_mode
        url = f"{self.base_url}{self.endpoint}?limit={limit}&offset={offset}"
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.api_token}"},
            method="GET",
        )
        logger.debug("MES work-orders request: offset=%d limit=%d", offset, limit)
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            logger.warning("MES work-orders request failed: HTTP %d", exc.code)
            raise MesError(f"MES API HTTP {exc.code} (GET {self.endpoint})") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("MES work-orders request failed: %s", type(exc).__name__)
            raise MesError(f"MES API request failed (GET {self.endpoint}): {type(exc).__name__}") from exc
        # Accept either a bare list or the common {"items"/"data": [...]} envelope.
        if isinstance(body, dict):
            for key in ("items", "data", "work_orders", "results"):
                if isinstance(body.get(key), list):
                    return body[key]
            raise MesError(f"unexpected MES response shape: {str(body)[:200]!r}")
        if not isinstance(body, list):
            raise MesError(f"unexpected MES response shape: {str(body)[:200]!r}")
        return body

    def _iter_http_rows(self) -> Iterator[dict[str, Any]]:
        offset = 0
        while True:
            orders = self._get_work_orders_page(offset=offset, limit=_PAGE_SIZE)
            if not orders:
                return
            for order in orders:
                yield _normalize_work_order(order)
            if len(orders) < _PAGE_SIZE:
                return
            offset += len(orders)

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

    # -- the three-step contract ------------------------------------------------
    def _contract_schema(self, source: str, row_count: int | None = None) -> Schema:
        fields = _FIELDS_BY_ENTITY.get(self.entity, _FIELDS_BY_ENTITY["work_orders"])
        return Schema(
            source=source,
            row_count=row_count,
            fields=fields,
            detected_categories=[self.entity],
        )

    def discover_schema(self) -> Schema:
        if self._http_mode:
            # Probe with a single-work-order page so a bad token fails here, cheaply.
            self._get_work_orders_page(offset=0, limit=1)
            return self._contract_schema(self.base_url or self.source)
        if self._is_jsonl:
            row_count = sum(1 for _ in self._iter_jsonl_rows())
            return self._contract_schema(str(self._jsonl_path), row_count=row_count)
        return self._contract_schema(self.source)

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        if n < 1:
            raise ValueError(f"extract_sample requires n >= 1 (got {n})")
        out: list[dict[str, Any]] = []
        if self._http_mode:
            for row in self._iter_http_rows():
                out.append(row)
                if len(out) >= n:
                    break
        elif self._is_jsonl:
            for row in self._iter_jsonl_rows():
                out.append(row)
                if len(out) >= n:
                    break
        else:
            logger.warning(
                "MES connector is unconfigured (set %s and %s, or pass a .jsonl source); "
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
        elif self._is_jsonl:
            rows = self._iter_jsonl_rows()
            source = str(self._jsonl_path)
        else:
            logger.warning(
                "MES connector is unconfigured (set %s and %s, or pass a .jsonl source); "
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

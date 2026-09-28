"""Historian connector — time-series history database (AVEVA PI / OSIsoft PI style).

Talks to a historian over a generic time-series REST convention using only
``urllib`` — zero new dependencies, same transport discipline as the
Zammad/Salesforce connectors. The default endpoint is modeled on a generic
samples query:

    GET {base_url}/api/v1/samples?tag={tag}&limit={n}&offset={m}[&start=...&end=...]

(the per-tag ``GET /api/v1/tags/{tag}/data?start=...&end=...&maxCount=N``
shape used by PI-Web-API-style servers is supported by overriding the
``endpoint`` option, e.g. ``endpoint="/api/v1/tags/{tag}/data"`` — ``{tag}``
is interpolated, and ``maxCount`` is sent instead of ``limit``/``offset``
when the template contains ``{tag}``).

Configuration (AGENTS.md invariant 3 — credentials live in env vars only and
never appear in logs, exceptions or persisted records):

- ``FDE_SCOPE_HISTORIAN_BASE_URL`` — e.g. ``https://pi.example.com``
- ``FDE_SCOPE_HISTORIAN_API_TOKEN`` — a Bearer token for the historian API

The constructor also accepts the CLI's uniform ``api_key``/``token`` options
and a URL ``source``; explicit options win over the environment.

Mode selection (decided once, at construction), mirroring the Zammad
connector:

1. **HTTP mode** — base URL *and* token resolve (options and/or env).
2. **JSONL replay mode** — ``source`` is a path to an existing ``.jsonl``
   file (one data-point dict per line); fully offline.
3. **Unconfigured mode** — neither of the above: the connector stays
   selectable (schema contract intact) but ``extract_sample``/``stream``
   yield nothing, exactly like the pre-P3 skeleton.

Partial env configuration (only one of base URL / token set) logs a WARNING
and falls back to the non-HTTP modes — never raises at import or CLI level.
HTTP mode without any ``tags`` option is useless (there is nothing to query)
and likewise degrades to empty output with a WARNING.

Data points are normalized onto the corpus engine's row contract
(``content``/``category``/``id`` …): ``tag`` → ``category``, ``timestamp`` →
``created_at``, ``value``/``quality`` are preserved. Time-series data only
earns its place in the corpus engine through *anomaly semantics*, so
``content`` is a textual rendering of the point: points whose quality is not
"good" (quality string outside ``{"good", "ok", "0"}``, case-insensitive)
are rendered as quality anomalies — the signal an FDE mines a historian for.
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

logger = get_logger("connectors.historian")

ENV_BASE_URL = "FDE_SCOPE_HISTORIAN_BASE_URL"
ENV_API_TOKEN = "FDE_SCOPE_HISTORIAN_API_TOKEN"

# urllib's urlopen() takes a single timeout covering connect + read (see the
# Zammad connector for the rationale).
_TIMEOUT_SECONDS = 30.0
_PAGE_SIZE = 1000
_DEFAULT_ENDPOINT = "/api/v1/samples"
# Quality strings treated as healthy; anything else is an anomaly worth
# surfacing to the corpus engine.
_GOOD_QUALITIES = frozenset({"good", "ok", "0"})


class HistorianError(RuntimeError):
    """Raised when the historian API call fails (network, auth, or protocol).

    Messages carry HTTP status and endpoint context only — never the token.
    """


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def _is_bad_quality(quality: Any) -> bool:
    if quality is None:
        return True
    return str(quality).strip().lower() not in _GOOD_QUALITIES


def _normalize_point(tag: str, point: dict[str, Any]) -> dict[str, Any]:
    """Map a historian data point onto the corpus engine's row contract."""
    timestamp = point.get("timestamp") or point.get("Timestamp") or point.get("time")
    value = point.get("value", point.get("Value"))
    quality = point.get("quality", point.get("Quality", "good"))
    if _is_bad_quality(quality):
        content = f"quality anomaly on {tag} at {timestamp}: quality={quality!r}, value={value!r}"
    else:
        content = f"{tag} = {value!r} at {timestamp}"
    return {
        "id": f"{tag}:{timestamp}",
        "tag": tag,
        "category": tag,
        "timestamp": timestamp,
        "value": value,
        "quality": quality,
        "state": quality,
        "content": content,
        "created_at": timestamp,
    }


def _contract_schema(source: str, tags: list[str]) -> Schema:
    return Schema(
        source=source,
        row_count=None,
        fields=[
            SchemaField(name="id", inferred_type="string"),
            SchemaField(name="tag", inferred_type="string"),
            SchemaField(name="category", inferred_type="string"),
            SchemaField(name="timestamp", inferred_type="string"),
            SchemaField(name="value", inferred_type="float"),
            SchemaField(name="quality", inferred_type="string"),
            SchemaField(name="content", inferred_type="string"),
            SchemaField(name="created_at", inferred_type="string"),
        ],
        detected_categories=tags,
    )


@register
class HistorianConnector(DataConnector):
    """Query a process historian for tag time-series over a REST API."""

    type = "historian"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        # Base URL: a URL `source` wins, then the env var.
        if "://" in source:
            self.base_url: str | None = source.rstrip("/")
        else:
            self.base_url = _env(ENV_BASE_URL)
        # Token: options (CLI's uniform `api_key`) win, then the env var.
        self.api_key = options.get("api_key") or options.get("token") or _env(ENV_API_TOKEN) or ""
        # Query window + tags (required for HTTP mode — no tag, no query).
        tags = options.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        self.tags: list[str] = list(tags)
        self.start = options.get("start")  # ISO8601
        self.end = options.get("end")
        self.endpoint = str(options.get("endpoint", _DEFAULT_ENDPOINT))
        self._jsonl_path: Path | None = None
        if "://" not in source:
            candidate = Path(source)
            if candidate.suffix == ".jsonl" and candidate.is_file():
                self._jsonl_path = candidate
        if bool(self.base_url) != bool(self.api_key):
            logger.warning(
                "incomplete Historian configuration (%s without %s); falling back to non-HTTP mode",
                ENV_BASE_URL if self.base_url else ENV_API_TOKEN,
                ENV_API_TOKEN if self.base_url else ENV_BASE_URL,
            )
        elif self._http_mode and not self.tags:
            logger.warning(
                "Historian connector has credentials but no tags to query "
                "(pass tags=[...]); extract_sample/stream will be empty",
            )

    # -- mode -------------------------------------------------------------------
    @property
    def _http_mode(self) -> bool:
        return bool(self.base_url and self.api_key)

    @property
    def _query_mode(self) -> bool:
        return self._http_mode and bool(self.tags)

    # -- HTTP transport ---------------------------------------------------------
    def _tag_url(self, tag: str, *, limit: int, offset: int) -> str:
        assert self.base_url is not None  # callers gate on _http_mode
        quoted_tag = urllib.parse.quote(tag, safe="")
        if "{tag}" in self.endpoint:
            # Per-tag endpoint convention (PI Web API style):
            # GET /api/v1/tags/{tag}/data?start=...&end=...&maxCount=N
            path = self.endpoint.replace("{tag}", quoted_tag)
            params: dict[str, str] = {"maxCount": str(limit)}
        else:
            path = self.endpoint
            params = {"tag": tag, "limit": str(limit), "offset": str(offset)}
        if self.start:
            params["start"] = str(self.start)
        if self.end:
            params["end"] = str(self.end)
        return f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"

    def _get_points_page(self, tag: str, *, limit: int, offset: int) -> list[dict[str, Any]]:
        url = self._tag_url(tag, limit=limit, offset=offset)
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            method="GET",
        )
        logger.debug("Historian samples request: tag=%s limit=%d offset=%d", tag, limit, offset)
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            logger.warning("Historian samples request failed: HTTP %d", exc.code)
            raise HistorianError(f"Historian API HTTP {exc.code} (GET {self.endpoint})") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Historian samples request failed: %s", type(exc).__name__)
            raise HistorianError(
                f"Historian API request failed (GET {self.endpoint}): {type(exc).__name__}"
            ) from exc
        if isinstance(body, dict):
            for key in ("samples", "items", "data", "points"):
                if isinstance(body.get(key), list):
                    body = body[key]
                    break
        if not isinstance(body, list):
            raise HistorianError(f"unexpected Historian response shape: {str(body)[:200]!r}")
        return [p for p in body if isinstance(p, dict)]

    def _iter_http_rows(self) -> Iterator[dict[str, Any]]:
        per_tag = "{tag}" in self.endpoint
        for tag in self.tags:
            offset = 0
            while True:
                points = self._get_points_page(tag, limit=_PAGE_SIZE, offset=offset)
                if not points:
                    break
                for point in points:
                    yield _normalize_point(tag, point)
                if per_tag or len(points) < _PAGE_SIZE:
                    break
                offset += len(points)

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
        if self._query_mode:
            # Probe with a single-point page so a bad token fails here, cheaply.
            self._get_points_page(self.tags[0], limit=1, offset=0)
            return _contract_schema(self.base_url or self.source, self.tags)
        if self._jsonl_path is not None:
            row_count = sum(1 for _ in self._iter_jsonl_rows())
            schema = _contract_schema(str(self._jsonl_path), self.tags)
            return schema.model_copy(update={"row_count": row_count})
        return _contract_schema(self.base_url or self.source, self.tags)

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        if n < 1:
            raise ValueError(f"extract_sample requires n >= 1 (got {n})")
        out: list[dict[str, Any]] = []
        if self._query_mode:
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
                "Historian connector is unconfigured (set %s and %s plus a tags "
                "option, or pass a .jsonl source); returning empty sample",
                ENV_BASE_URL,
                ENV_API_TOKEN,
            )
        return out

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        if batch_size < 1:
            raise ValueError(f"stream requires batch_size >= 1 (got {batch_size})")
        if self._query_mode:
            rows: Iterator[dict[str, Any]] = self._iter_http_rows()
            source = self.base_url or self.source
        elif self._jsonl_path is not None:
            rows = self._iter_jsonl_rows()
            source = str(self._jsonl_path)
        else:
            logger.warning(
                "Historian connector is unconfigured (set %s and %s plus a tags "
                "option, or pass a .jsonl source); stream yields nothing",
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

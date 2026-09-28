"""Historian connector tests — HTTP mode (urllib mocked, offline) + JSONL fallback.

No real historian instance or token is ever contacted: the transport is mocked
at ``urllib.request.urlopen`` level, mirroring ``tests/test_zammad_connector.py``.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from fde_scope.connectors._registry import get
from fde_scope.connectors.historian import (
    ENV_API_TOKEN,
    ENV_BASE_URL,
    HistorianConnector,
    HistorianError,
    _normalize_point,
)

_URL = "https://pi.example.com"
_TOKEN = "historian-secret-token"
_TAGS = ["TEMP_01", "PRESS_02"]


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _points(tag: str, *, count: int, start: int = 0, quality: str = "good") -> list[dict]:
    return [
        {
            "timestamp": f"2026-09-01T10:{(start + i) % 60:02d}:00Z",
            "value": 20.0 + start + i,
            "quality": quality,
        }
        for i in range(count)
    ]


@pytest.fixture()
def clean_historian_env(monkeypatch):
    monkeypatch.delenv(ENV_BASE_URL, raising=False)
    monkeypatch.delenv(ENV_API_TOKEN, raising=False)
    return monkeypatch


def _connector(**options) -> HistorianConnector:
    cls = get("historian")
    return cls(_URL, api_key=_TOKEN, tags=_TAGS, **options)


def _install_pager(monkeypatch, pages_by_tag: dict[str, list[bytes]], calls: list[str]) -> None:
    """Serve per-tag offset pages; pages_by_tag maps tag -> list of page bodies."""

    def fake_urlopen(request, timeout):  # noqa: ARG001
        url = request.full_url
        calls.append(url)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        tag = query["tag"][0]
        offset = int(query.get("offset", ["0"])[0])
        return _FakeResp(pages_by_tag[tag][offset // 1000])

    monkeypatch.setattr("fde_scope.connectors.historian.urllib.request.urlopen", fake_urlopen)


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------
def test_http_mode_via_options(clean_historian_env) -> None:
    c = _connector()
    assert c._http_mode
    assert c._query_mode
    assert c.base_url == _URL
    assert c.api_key == _TOKEN
    assert c.tags == _TAGS


def test_http_mode_via_env(clean_historian_env) -> None:
    clean_historian_env.setenv(ENV_BASE_URL, _URL)
    clean_historian_env.setenv(ENV_API_TOKEN, _TOKEN)
    c = get("historian")(_URL, tags=_TAGS)
    assert c._http_mode
    assert c.api_key == _TOKEN


def test_tags_option_accepts_comma_string(clean_historian_env) -> None:
    c = get("historian")(_URL, api_key=_TOKEN, tags="TEMP_01, PRESS_02 ,")
    assert c.tags == ["TEMP_01", "PRESS_02"]


def test_unconfigured_without_env_or_jsonl(clean_historian_env) -> None:
    c = get("historian")(_URL)
    assert not c._http_mode
    assert c._jsonl_path is None
    # Skeleton-compatible: selectable, schema intact, empty sample/stream.
    assert "content" in c.discover_schema().field_names()
    assert c.extract_sample(5) == []
    assert list(c.stream()) == []


def test_partial_env_warns_and_falls_back(clean_historian_env, caplog) -> None:
    clean_historian_env.setenv(ENV_BASE_URL, _URL)  # no token
    with caplog.at_level("WARNING", logger="fde_scope.connectors.historian"):
        c = get("historian")(_URL, tags=_TAGS)
    assert not c._http_mode
    assert c.extract_sample(3) == []
    assert any("incomplete Historian configuration" in r.message for r in caplog.records)


def test_http_mode_without_tags_warns_and_yields_nothing(clean_historian_env, caplog) -> None:
    with caplog.at_level("WARNING", logger="fde_scope.connectors.historian"):
        c = get("historian")(_URL, api_key=_TOKEN)  # credentials but no tags
    assert c._http_mode
    assert not c._query_mode
    assert c.extract_sample(3) == []
    assert list(c.stream()) == []
    assert any("no tags" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# HTTP mode — request shape, mapping, pagination
# ---------------------------------------------------------------------------
def test_extract_sample_sends_bearer_header_and_maps_rows(clean_historian_env, monkeypatch) -> None:
    captured: dict = {}
    body = json.dumps(_points("TEMP_01", count=2)).encode()

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        return _FakeResp(body)

    monkeypatch.setattr("fde_scope.connectors.historian.urllib.request.urlopen", fake_urlopen)
    rows = get("historian")(_URL, api_key=_TOKEN, tags=["TEMP_01"]).extract_sample(10)

    assert captured["url"].startswith(f"{_URL}/api/v1/samples?")
    assert "tag=TEMP_01" in captured["url"]
    assert captured["headers"]["authorization"] == f"Bearer {_TOKEN}"
    assert len(rows) == 2
    row = rows[0]
    assert row["tag"] == "TEMP_01"
    assert row["category"] == "TEMP_01"  # tag -> category
    assert row["value"] == 20.0
    assert row["quality"] == "good"
    assert row["timestamp"] == row["created_at"]
    assert "TEMP_01" in row["content"]


def test_bad_quality_point_becomes_anomaly_content(clean_historian_env) -> None:
    row = _normalize_point(
        "PRESS_02",
        {"timestamp": "2026-09-01T10:00:00Z", "value": 3.14, "quality": "Bad"},
    )
    assert "quality anomaly" in row["content"]
    assert "PRESS_02" in row["content"]
    assert "'Bad'" in row["content"]
    assert row["quality"] == "Bad"
    assert row["value"] == 3.14


def test_extract_sample_truncates_at_n(clean_historian_env, monkeypatch) -> None:
    body = json.dumps(_points("TEMP_01", count=5)).encode()
    monkeypatch.setattr(
        "fde_scope.connectors.historian.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(body),  # noqa: ARG005
    )
    rows = get("historian")(_URL, api_key=_TOKEN, tags=["TEMP_01"]).extract_sample(3)
    assert len(rows) == 3


def test_stream_paginates_per_tag_until_short_page(clean_historian_env, monkeypatch) -> None:
    calls: list[str] = []
    _install_pager(
        monkeypatch,
        {
            "TEMP_01": [
                json.dumps(_points("TEMP_01", count=1000, start=0)).encode(),
                json.dumps(_points("TEMP_01", count=3, start=1000)).encode(),
            ],
            "PRESS_02": [json.dumps(_points("PRESS_02", count=2, quality="Bad")).encode()],
        },
        calls,
    )
    batches = list(_connector().stream(batch_size=1000))
    assert [len(b) for b in batches] == [1000, 5]
    assert all(b.source == _URL for b in batches)
    assert any("tag=TEMP_01" in u and "offset=1000" in u for u in calls)
    assert any("tag=PRESS_02" in u for u in calls)
    anomalies = [r for b in batches for r in b if "quality anomaly" in r["content"]]
    assert len(anomalies) == 2


def test_extract_sample_accepts_dict_response_with_samples_key(clean_historian_env, monkeypatch) -> None:
    body = json.dumps({"samples": _points("TEMP_01", count=2), "total": 2}).encode()
    monkeypatch.setattr(
        "fde_scope.connectors.historian.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(body),  # noqa: ARG005
    )
    rows = get("historian")(_URL, api_key=_TOKEN, tags=["TEMP_01"]).extract_sample(10)
    assert len(rows) == 2


def test_per_tag_endpoint_template_uses_maxcount_and_window(clean_historian_env, monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "fde_scope.connectors.historian.urllib.request.urlopen",
        lambda request, timeout: (captured.update(url=request.full_url), _FakeResp(b"[]"))[1],  # noqa: ARG005
    )
    c = get("historian")(
        _URL,
        api_key=_TOKEN,
        tags=["TEMP 01"],
        start="2026-01-01T00:00:00Z",
        end="2026-02-01T00:00:00Z",
        endpoint="/api/v1/tags/{tag}/data",
    )
    rows = c.extract_sample(5)
    assert rows == []
    url = captured["url"]
    assert url.startswith(f"{_URL}/api/v1/tags/TEMP%2001/data?")
    assert "maxCount=1000" in url
    assert "start=2026-01-01" in url.replace("%3A", ":")
    assert "end=2026-02-01" in url.replace("%3A", ":")
    assert "offset=" not in url


def test_discover_schema_http_probes_one_point(clean_historian_env, monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "fde_scope.connectors.historian.urllib.request.urlopen",
        lambda request, timeout: (captured.update(url=request.full_url), _FakeResp(b"[]"))[1],  # noqa: ARG005
    )
    schema = _connector().discover_schema()
    assert "limit=1" in captured["url"]
    assert "tag=TEMP_01" in captured["url"]
    assert "content" in schema.field_names()
    assert schema.detected_categories == _TAGS
    assert schema.row_count is None


# ---------------------------------------------------------------------------
# HTTP mode — error paths (token must never leak into exceptions)
# ---------------------------------------------------------------------------
def test_http_401_raises_historian_error_without_token(clean_historian_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad"))

    monkeypatch.setattr("fde_scope.connectors.historian.urllib.request.urlopen", fail)
    with pytest.raises(HistorianError, match="401") as excinfo:
        _connector().extract_sample(1)
    assert _TOKEN not in str(excinfo.value)


def test_http_500_raises_historian_error(clean_historian_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, io.BytesIO(b"boom"))

    monkeypatch.setattr("fde_scope.connectors.historian.urllib.request.urlopen", fail)
    with pytest.raises(HistorianError, match="500") as excinfo:
        _connector().extract_sample(1)
    assert _TOKEN not in str(excinfo.value)


def test_timeout_raises_historian_error(clean_historian_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise TimeoutError("read timed out")

    monkeypatch.setattr("fde_scope.connectors.historian.urllib.request.urlopen", fail)
    with pytest.raises(HistorianError, match="TimeoutError") as excinfo:
        _connector().extract_sample(1)
    assert _TOKEN not in str(excinfo.value)


def test_url_error_raises_historian_error(clean_historian_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("fde_scope.connectors.historian.urllib.request.urlopen", fail)
    with pytest.raises(HistorianError, match="URLError"):
        _connector().discover_schema()


def test_unexpected_response_shape_raises(clean_historian_env, monkeypatch) -> None:
    monkeypatch.setattr(
        "fde_scope.connectors.historian.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(b'{"error": "oops"}'),  # noqa: ARG005
    )
    with pytest.raises(HistorianError, match="unexpected Historian response"):
        _connector().extract_sample(1)


# ---------------------------------------------------------------------------
# JSONL replay mode
# ---------------------------------------------------------------------------
def test_jsonl_fallback_extract_and_stream(clean_historian_env, tmp_path: Path) -> None:
    path = tmp_path / "samples.jsonl"
    lines = [
        {"id": "TEMP_01:t1", "tag": "TEMP_01", "content": "a", "category": "TEMP_01"},
        {"id": "TEMP_01:t2", "tag": "TEMP_01", "content": "b", "category": "TEMP_01"},
        {"id": "PRESS_02:t3", "tag": "PRESS_02", "content": "c", "category": "PRESS_02"},
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in lines) + "\n", "utf-8")
    c = get("historian")(str(path))
    assert not c._http_mode

    schema = c.discover_schema()
    assert schema.row_count == 3

    assert c.extract_sample(2) == lines[:2]
    batches = list(c.stream(batch_size=2))
    assert [len(b) for b in batches] == [2, 1]
    assert batches[0].source == str(path)


def test_extract_sample_rejects_nonpositive_n(clean_historian_env) -> None:
    with pytest.raises(ValueError, match="n >= 1"):
        _connector().extract_sample(0)


def test_stream_rejects_nonpositive_batch_size(clean_historian_env) -> None:
    with pytest.raises(ValueError, match="batch_size >= 1"):
        list(_connector().stream(batch_size=0))

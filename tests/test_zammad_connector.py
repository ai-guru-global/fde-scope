"""Zammad connector tests — HTTP mode (urllib mocked, offline) + JSONL fallback.

No real Zammad instance or token is ever contacted: the transport is mocked
at ``urllib.request.urlopen`` level, mirroring ``tests/test_llm.py``.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from fde_scope.connectors._registry import get
from fde_scope.connectors.zammad import (
    ENV_API_TOKEN,
    ENV_BASE_URL,
    ZammadConnector,
    ZammadError,
)

_URL = "https://zammad.example.com"
_TOKEN = "zammad-secret-token"


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _tickets(*, page: int, count: int, start: int = 1) -> list[dict]:
    return [
        {
            "id": start + i,
            "number": f"50{start + i:03d}",
            "title": f"ticket {start + i}",
            "note": f"note {start + i}",
            "group": "Support",
            "state": "open",
            "create_article_type": "email",
            "created_at": "2026-09-01T10:00:00Z",
        }
        for i in range(count)
    ]


@pytest.fixture()
def clean_zammad_env(monkeypatch):
    monkeypatch.delenv(ENV_BASE_URL, raising=False)
    monkeypatch.delenv(ENV_API_TOKEN, raising=False)
    return monkeypatch


def _connector() -> ZammadConnector:
    cls = get("zammad")
    return cls(_URL, api_key=_TOKEN)


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------
def test_http_mode_via_options(clean_zammad_env) -> None:
    c = _connector()
    assert c._http_mode
    assert c.base_url == _URL
    assert c.api_key == _TOKEN


def test_http_mode_via_env(clean_zammad_env) -> None:
    clean_zammad_env.setenv(ENV_BASE_URL, _URL)
    clean_zammad_env.setenv(ENV_API_TOKEN, _TOKEN)
    c = get("zammad")(_URL)
    assert c._http_mode
    assert c.api_key == _TOKEN


def test_unconfigured_without_env_or_jsonl(clean_zammad_env) -> None:
    c = get("zammad")(_URL)
    assert not c._http_mode
    assert c._jsonl_path is None
    # Skeleton-compatible: selectable, schema intact, empty sample/stream.
    assert "content" in c.discover_schema().field_names()
    assert c.extract_sample(5) == []
    assert list(c.stream()) == []


def test_partial_env_warns_and_falls_back(clean_zammad_env, caplog) -> None:
    clean_zammad_env.setenv(ENV_BASE_URL, _URL)  # no token
    with caplog.at_level("WARNING", logger="fde_scope.connectors.zammad"):
        c = get("zammad")(_URL)
    assert not c._http_mode
    assert c.extract_sample(3) == []
    assert any("incomplete Zammad configuration" in r.message for r in caplog.records)
    assert _TOKEN not in caplog.text


# ---------------------------------------------------------------------------
# HTTP mode — request shape, mapping, pagination
# ---------------------------------------------------------------------------
def test_extract_sample_sends_token_header_and_maps_rows(clean_zammad_env, monkeypatch) -> None:
    captured: dict = {}
    body = json.dumps(_tickets(page=1, count=2)).encode()

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        return _FakeResp(body)

    monkeypatch.setattr("fde_scope.connectors.zammad.urllib.request.urlopen", fake_urlopen)
    rows = _connector().extract_sample(10)

    assert captured["url"].startswith(f"{_URL}/api/v1/tickets?")
    assert "expand=true" in captured["url"]
    assert captured["headers"]["authorization"] == f"Token token={_TOKEN}"
    assert len(rows) == 2
    row = rows[0]
    assert row["id"] == 1
    assert row["category"] == "Support"  # group -> category
    assert row["state"] == "open"
    assert row["channel"] == "email"
    assert row["content"] == "note 1"  # note preferred over title


def test_extract_sample_truncates_at_n(clean_zammad_env, monkeypatch) -> None:
    body = json.dumps(_tickets(page=1, count=5)).encode()
    monkeypatch.setattr(
        "fde_scope.connectors.zammad.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(body),  # noqa: ARG005
    )
    rows = _connector().extract_sample(3)
    assert len(rows) == 3


def test_extract_sample_paginates_until_n(clean_zammad_env, monkeypatch) -> None:
    calls: list[str] = []
    pages = {
        1: json.dumps(_tickets(page=1, count=100, start=1)).encode(),
        2: json.dumps(_tickets(page=2, count=100, start=101)).encode(),
        3: b"[]",
    }

    def fake_urlopen(request, timeout):  # noqa: ARG001
        calls.append(request.full_url)
        page = int(request.full_url.rsplit("page=", 1)[1])
        return _FakeResp(pages[page])

    monkeypatch.setattr("fde_scope.connectors.zammad.urllib.request.urlopen", fake_urlopen)
    rows = _connector().extract_sample(150)
    assert len(rows) == 150
    assert len(calls) == 2  # stopped mid-page-2 once n was reached
    assert "page=1" in calls[0] and "page=2" in calls[1]


def test_stream_paginates_to_empty_page_and_batches(clean_zammad_env, monkeypatch) -> None:
    pages = {
        1: json.dumps(_tickets(page=1, count=100, start=1)).encode(),
        2: json.dumps(_tickets(page=2, count=3, start=101)).encode(),
    }

    def fake_urlopen(request, timeout):  # noqa: ARG001
        page = int(request.full_url.rsplit("page=", 1)[1])
        return _FakeResp(pages[page])

    monkeypatch.setattr("fde_scope.connectors.zammad.urllib.request.urlopen", fake_urlopen)
    batches = list(_connector().stream(batch_size=100))
    assert [len(b) for b in batches] == [100, 3]
    assert all(b.source == _URL for b in batches)


def test_discover_schema_http_probes_one_ticket(clean_zammad_env, monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "fde_scope.connectors.zammad.urllib.request.urlopen",
        lambda request, timeout: (captured.update(url=request.full_url), _FakeResp(b"[]"))[1],  # noqa: ARG005
    )
    schema = _connector().discover_schema()
    assert "limit=1" in captured["url"]
    assert "content" in schema.field_names()
    assert schema.row_count is None


# ---------------------------------------------------------------------------
# HTTP mode — error paths (token must never leak into exceptions)
# ---------------------------------------------------------------------------
def test_http_401_raises_zammad_error_without_token(clean_zammad_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad"))

    monkeypatch.setattr("fde_scope.connectors.zammad.urllib.request.urlopen", fail)
    with pytest.raises(ZammadError, match="401") as excinfo:
        _connector().extract_sample(1)
    assert _TOKEN not in str(excinfo.value)


def test_http_500_raises_zammad_error(clean_zammad_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, io.BytesIO(b"boom"))

    monkeypatch.setattr("fde_scope.connectors.zammad.urllib.request.urlopen", fail)
    with pytest.raises(ZammadError, match="500"):
        _connector().extract_sample(1)


def test_timeout_raises_zammad_error(clean_zammad_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise TimeoutError("read timed out")

    monkeypatch.setattr("fde_scope.connectors.zammad.urllib.request.urlopen", fail)
    with pytest.raises(ZammadError, match="TimeoutError"):
        _connector().extract_sample(1)


def test_url_error_raises_zammad_error(clean_zammad_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("fde_scope.connectors.zammad.urllib.request.urlopen", fail)
    with pytest.raises(ZammadError, match="URLError"):
        _connector().discover_schema()


def test_non_list_response_raises(clean_zammad_env, monkeypatch) -> None:
    monkeypatch.setattr(
        "fde_scope.connectors.zammad.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(b'{"error": "oops"}'),  # noqa: ARG005
    )
    with pytest.raises(ZammadError, match="unexpected Zammad response"):
        _connector().extract_sample(1)


# ---------------------------------------------------------------------------
# JSONL replay mode
# ---------------------------------------------------------------------------
def test_jsonl_fallback_extract_and_stream(clean_zammad_env, tmp_path: Path) -> None:
    path = tmp_path / "tickets.jsonl"
    lines = [
        {"id": 1, "title": "a", "content": "hello", "category": "退款"},
        {"id": 2, "title": "b", "content": "world", "category": "物流"},
        {"id": 3, "title": "c", "content": "!", "category": "退款"},
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in lines) + "\n", "utf-8")
    c = get("zammad")(str(path))
    assert not c._http_mode

    schema = c.discover_schema()
    assert schema.row_count == 3

    assert c.extract_sample(2) == lines[:2]
    batches = list(c.stream(batch_size=2))
    assert [len(b) for b in batches] == [2, 1]
    assert batches[0].source == str(path)


def test_extract_sample_rejects_nonpositive_n(clean_zammad_env) -> None:
    with pytest.raises(ValueError, match="n >= 1"):
        _connector().extract_sample(0)


def test_stream_rejects_nonpositive_batch_size(clean_zammad_env) -> None:
    with pytest.raises(ValueError, match="batch_size >= 1"):
        list(_connector().stream(batch_size=0))

"""Salesforce connector tests — HTTP mode (urllib mocked, offline) + JSONL fallback.

No real Salesforce instance or token is ever contacted: the transport is
mocked at ``urllib.request.urlopen`` level, mirroring ``tests/test_zammad_connector.py``.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from fde_scope.connectors._registry import get
from fde_scope.connectors.salesforce import (
    ENV_ACCESS_TOKEN,
    ENV_INSTANCE_URL,
    SalesforceConnector,
    SalesforceError,
)

_URL = "https://acme.my.salesforce.com"
_TOKEN = "sf-secret-access-token"


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _case(i: int) -> dict:
    return {
        "Id": f"500xx{i:06d}",
        "CaseNumber": f"0000{i:04d}",
        "Subject": f"case {i}",
        "Description": f"description {i}",
        "Status": "New",
        "Priority": "High",
        "Origin": "Web",
        "CreatedDate": "2026-09-01T10:00:00.000+0000",
    }


def _query_body(count: int, *, done: bool = True, start: int = 1) -> bytes:
    body: dict = {"totalSize": count, "done": done, "records": [_case(start + i) for i in range(count)]}
    if not done:
        body["nextRecordsUrl"] = "/services/data/v59.0/query/01gXX-next"
    return json.dumps(body).encode()


@pytest.fixture()
def clean_sf_env(monkeypatch):
    monkeypatch.delenv(ENV_INSTANCE_URL, raising=False)
    monkeypatch.delenv(ENV_ACCESS_TOKEN, raising=False)
    return monkeypatch


def _connector(**options) -> SalesforceConnector:
    cls = get("salesforce")
    return cls(_URL, api_key=_TOKEN, **options)


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------
def test_http_mode_via_options(clean_sf_env) -> None:
    c = _connector()
    assert c._http_mode
    assert c.instance_url == _URL
    assert c.access_token == _TOKEN


def test_http_mode_via_env(clean_sf_env) -> None:
    clean_sf_env.setenv(ENV_INSTANCE_URL, _URL)
    clean_sf_env.setenv(ENV_ACCESS_TOKEN, _TOKEN)
    c = get("salesforce")(_URL)
    assert c._http_mode
    assert c.access_token == _TOKEN


def test_unconfigured_without_env_or_jsonl(clean_sf_env) -> None:
    c = get("salesforce")(_URL)
    assert not c._http_mode
    assert c._jsonl_path is None
    assert "content" in c.discover_schema().field_names()
    assert c.extract_sample(5) == []
    assert list(c.stream()) == []


def test_partial_env_warns_and_falls_back(clean_sf_env, caplog) -> None:
    clean_sf_env.setenv(ENV_INSTANCE_URL, _URL)  # no token
    with caplog.at_level("WARNING", logger="fde_scope.connectors.salesforce"):
        c = get("salesforce")(_URL)
    assert not c._http_mode
    assert c.extract_sample(3) == []
    assert any("incomplete Salesforce configuration" in r.message for r in caplog.records)
    assert _TOKEN not in caplog.text


# ---------------------------------------------------------------------------
# SOQL validation (read-only channel)
# ---------------------------------------------------------------------------
def test_non_select_soql_rejected(clean_sf_env) -> None:
    with pytest.raises(SalesforceError, match="SELECT"):
        _connector(soql="DELETE FROM Case")


def test_soql_with_write_keyword_rejected(clean_sf_env) -> None:
    with pytest.raises(SalesforceError, match="forbidden keyword"):
        _connector(soql="SELECT Id FROM Case; DELETE FROM Case")


def test_custom_select_soql_accepted(clean_sf_env, monkeypatch) -> None:
    captured: dict = {}

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["url"] = request.full_url
        return _FakeResp(_query_body(1))

    monkeypatch.setattr("fde_scope.connectors.salesforce.urllib.request.urlopen", fake_urlopen)
    rows = _connector(soql="SELECT Id, Subject FROM Case").extract_sample(1)
    assert len(rows) == 1
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(captured["url"]).query)
    assert query["q"][0].startswith("SELECT Id, Subject FROM Case")


# ---------------------------------------------------------------------------
# HTTP mode — request shape, mapping, pagination
# ---------------------------------------------------------------------------
def test_extract_sample_sends_bearer_header_and_maps_rows(clean_sf_env, monkeypatch) -> None:
    captured: dict = {}

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        return _FakeResp(_query_body(2))

    monkeypatch.setattr("fde_scope.connectors.salesforce.urllib.request.urlopen", fake_urlopen)
    rows = _connector().extract_sample(10)

    assert "/services/data/v59.0/query?q=" in captured["url"]
    assert captured["headers"]["authorization"] == f"Bearer {_TOKEN}"
    assert len(rows) == 2
    row = rows[0]
    assert row["id"] == "500xx000001"
    assert row["number"] == "00000001"
    assert row["state"] == "New"  # Status -> state
    assert row["category"] == "High"  # Priority -> category
    assert row["channel"] == "Web"  # Origin -> channel
    assert row["content"] == "description 1"  # Description preferred over Subject


def test_extract_sample_falls_back_to_subject_for_content(clean_sf_env, monkeypatch) -> None:
    record = _case(1)
    del record["Description"]
    body = json.dumps({"totalSize": 1, "done": True, "records": [record]}).encode()
    monkeypatch.setattr(
        "fde_scope.connectors.salesforce.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(body),  # noqa: ARG005
    )
    assert _connector().extract_sample(1)[0]["content"] == "case 1"


def test_extract_sample_truncates_at_n(clean_sf_env, monkeypatch) -> None:
    monkeypatch.setattr(
        "fde_scope.connectors.salesforce.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(_query_body(5)),  # noqa: ARG005
    )
    rows = _connector().extract_sample(3)
    assert len(rows) == 3


def test_extract_sample_appends_limit_to_default_soql(clean_sf_env, monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "fde_scope.connectors.salesforce.urllib.request.urlopen",
        lambda request, timeout: (captured.update(url=request.full_url), _FakeResp(_query_body(0)))[1],  # noqa: ARG005
    )
    _connector().extract_sample(7)
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(captured["url"]).query)
    assert query["q"][0].endswith("LIMIT 7")


def test_stream_follows_next_records_url(clean_sf_env, monkeypatch) -> None:
    calls: list[str] = []

    def fake_urlopen(request, timeout):  # noqa: ARG001
        calls.append(request.full_url)
        if "01gXX-next" in request.full_url:
            return _FakeResp(_query_body(2, start=101))
        return _FakeResp(_query_body(3, done=False, start=1))

    monkeypatch.setattr("fde_scope.connectors.salesforce.urllib.request.urlopen", fake_urlopen)
    batches = list(_connector().stream(batch_size=4))
    assert [len(b) for b in batches] == [4, 1]
    assert len(calls) == 2
    assert calls[1] == f"{_URL}/services/data/v59.0/query/01gXX-next"
    assert all(b.source == _URL for b in batches)


def test_discover_schema_http_probes_one_record(clean_sf_env, monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "fde_scope.connectors.salesforce.urllib.request.urlopen",
        lambda request, timeout: (captured.update(url=request.full_url), _FakeResp(_query_body(0)))[1],  # noqa: ARG005
    )
    schema = _connector().discover_schema()
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(captured["url"]).query)
    assert query["q"][0].endswith("LIMIT 1")
    assert "content" in schema.field_names()
    assert schema.row_count is None


# ---------------------------------------------------------------------------
# HTTP mode — error paths (token must never leak into exceptions)
# ---------------------------------------------------------------------------
def test_http_401_raises_without_token(clean_sf_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad"))

    monkeypatch.setattr("fde_scope.connectors.salesforce.urllib.request.urlopen", fail)
    with pytest.raises(SalesforceError, match="401") as excinfo:
        _connector().extract_sample(1)
    assert _TOKEN not in str(excinfo.value)


def test_http_500_raises(clean_sf_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, io.BytesIO(b"boom"))

    monkeypatch.setattr("fde_scope.connectors.salesforce.urllib.request.urlopen", fail)
    with pytest.raises(SalesforceError, match="500"):
        _connector().extract_sample(1)


def test_timeout_raises(clean_sf_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise TimeoutError("read timed out")

    monkeypatch.setattr("fde_scope.connectors.salesforce.urllib.request.urlopen", fail)
    with pytest.raises(SalesforceError, match="TimeoutError"):
        _connector().extract_sample(1)


def test_url_error_raises(clean_sf_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("fde_scope.connectors.salesforce.urllib.request.urlopen", fail)
    with pytest.raises(SalesforceError, match="URLError"):
        _connector().discover_schema()


def test_non_dict_response_raises(clean_sf_env, monkeypatch) -> None:
    monkeypatch.setattr(
        "fde_scope.connectors.salesforce.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(b'["oops"]'),  # noqa: ARG005
    )
    with pytest.raises(SalesforceError, match="unexpected Salesforce response"):
        _connector().extract_sample(1)


# ---------------------------------------------------------------------------
# JSONL replay mode
# ---------------------------------------------------------------------------
def test_jsonl_fallback_extract_and_stream(clean_sf_env, tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    lines = [
        {"id": "1", "title": "a", "content": "hello", "category": "退款"},
        {"id": "2", "title": "b", "content": "world", "category": "物流"},
        {"id": "3", "title": "c", "content": "!", "category": "退款"},
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in lines) + "\n", "utf-8")
    c = get("salesforce")(str(path))
    assert not c._http_mode

    schema = c.discover_schema()
    assert schema.row_count == 3

    assert c.extract_sample(2) == lines[:2]
    batches = list(c.stream(batch_size=2))
    assert [len(b) for b in batches] == [2, 1]
    assert batches[0].source == str(path)


def test_extract_sample_rejects_nonpositive_n(clean_sf_env) -> None:
    with pytest.raises(ValueError, match="n >= 1"):
        _connector().extract_sample(0)


def test_stream_rejects_nonpositive_batch_size(clean_sf_env) -> None:
    with pytest.raises(ValueError, match="batch_size >= 1"):
        list(_connector().stream(batch_size=0))

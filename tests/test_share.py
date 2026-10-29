"""Tests for stakeholder read-only share links (``/share/{eid}?t=…``)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    return TestClient(app)


@pytest.fixture
def eid(client) -> str:
    r = client.post("/api/engagements", data={"customer": "ShareCo", "profile": "ticket"})
    return r.json()["engagement_id"]


# -- owner surface ------------------------------------------------------------
def test_create_share_returns_token_exactly_once(client, eid) -> None:
    r = client.post(f"/api/engagements/{eid}/share")
    assert r.status_code == 200
    body = r.json()
    assert body["url_path"] == f"/share/{eid}"
    assert body["token_prefix"] == body["token"][:8]

    # status never echoes the token
    status = client.get(f"/api/engagements/{eid}/share").json()
    assert status["active"] is True
    assert status["token_prefix"] == body["token"][:8]
    assert "token" not in status

    # the stored context carries the sha256, never the plaintext
    ctx = client.get(f"/api/engagements/{eid}").json()["context"]
    dumped = json.dumps(ctx, ensure_ascii=False)
    assert body["token"] not in dumped
    assert ctx["assets"]["share_access"]["token_sha256"]


def test_create_share_rotates_the_old_link(client, eid) -> None:
    first = client.post(f"/api/engagements/{eid}/share").json()["token"]
    second = client.post(f"/api/engagements/{eid}/share").json()["token"]
    assert first != second
    # the old link is dead the moment a new one exists
    assert client.get(f"/share/{eid}", params={"t": first}).status_code == 404
    assert client.get(f"/share/{eid}", params={"t": second}).status_code == 200


def test_revoke_share_is_idempotent(client, eid) -> None:
    token = client.post(f"/api/engagements/{eid}/share").json()["token"]
    assert client.delete(f"/api/engagements/{eid}/share").json()["revoked"] is True
    assert client.delete(f"/api/engagements/{eid}/share").json()["revoked"] is False
    assert client.get(f"/share/{eid}", params={"t": token}).status_code == 404
    assert client.get(f"/api/engagements/{eid}/share").json()["active"] is False


# -- stakeholder surface ------------------------------------------------------
def test_share_page_renders_readonly_summary(client, eid) -> None:
    token = client.post(f"/api/engagements/{eid}/share").json()["token"]
    r = client.get(f"/share/{eid}", params={"t": token})
    assert r.status_code == 200
    assert "ShareCo" in r.text
    assert "SLA 里程碑" in r.text
    assert "门禁现况" in r.text
    assert "客户签收" in r.text
    # the read-only page must not offer any state-machine mutation
    assert "/advance" not in r.text and "/rollback" not in r.text


def test_share_page_fails_closed(client, eid) -> None:
    client.post(f"/api/engagements/{eid}/share")
    assert client.get(f"/share/{eid}").status_code == 404  # missing token
    assert client.get(f"/share/{eid}", params={"t": "wrong-token"}).status_code == 404
    # an unknown engagement is indistinguishable from a bad token
    assert client.get("/share/eng-ghost", params={"t": "whatever"}).status_code == 404


def test_share_ack_is_evidence_not_authorization(client, eid, tmp_path) -> None:
    from fde_scope import audit

    token = client.post(f"/api/engagements/{eid}/share").json()["token"]
    r = client.post(f"/share/{eid}/ack", params={"t": token}, data={"label": "王经理"})
    assert r.status_code == 200
    assert "签收已记录" in r.text

    events = [e for e in audit.read_events(eid) if e["action"] == "share.ack"]
    assert len(events) == 1
    assert events[0]["actor"] == "stakeholder"
    assert events[0]["detail"]["label"] == "王经理"

    # the raw audit file never carries the share token (invariant 3/7)
    raw = (paths_audit_file(tmp_path)).read_text(encoding="utf-8")
    assert token not in raw

    # the engagement is still at qualification — an ack advances nothing
    assert client.get(f"/api/engagements/{eid}").json()["current_phase"] == "qualification"


def test_share_ack_with_bad_token_is_404(client, eid) -> None:
    client.post(f"/api/engagements/{eid}/share")
    r = client.post(f"/share/{eid}/ack", params={"t": "nope"}, data={"label": "x"})
    assert r.status_code == 404


# -- auth interplay -----------------------------------------------------------
def test_share_link_works_without_admin_token_but_apis_need_it(client, eid, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", "secret-admin-token")
    # owner API requires the admin token …
    assert client.post(f"/api/engagements/{eid}/share").status_code == 401
    r = client.post(f"/api/engagements/{eid}/share", headers={"X-API-Key": "secret-admin-token"})
    assert r.status_code == 200
    token = r.json()["token"]
    # … the share link does not (the stakeholder never sees the admin token)
    assert client.get(f"/share/{eid}", params={"t": token}).status_code == 200
    assert client.get(f"/share/{eid}", params={"t": token}, headers={"X-API-Key": "x"}).status_code == 200
    # and a bad share token is 404 even with a valid admin token — the two
    # credentials are independent, one does not vouch for the other
    bad = client.get(f"/share/{eid}", params={"t": "wrong"}, headers={"X-API-Key": "secret-admin-token"})
    assert bad.status_code == 404
    assert client.get(f"/share/{eid}").status_code == 404


def paths_audit_file(tmp_path: Path) -> Path:
    from fde_scope import paths

    return paths.data_root() / paths.DATA_SUBDIR / "audit.jsonl"

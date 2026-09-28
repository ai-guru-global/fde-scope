"""Tests for the append-only audit log (commercialization B4)."""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    return TestClient(app)


def _read_audit(tmp_path):
    path = tmp_path / ".fde_scope" / "audit.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_log_event_writes_jsonl(tmp_path) -> None:
    from fde_scope import audit

    audit.log_event("test.action", detail={"k": "v"})
    records = _read_audit(tmp_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["action"] == "test.action"
    assert rec["actor"] == "local"
    assert rec["detail"] == {"k": "v"}
    assert "ts" in rec and "T" in rec["ts"]  # ISO8601 timestamp


def test_log_event_default_detail(tmp_path) -> None:
    from fde_scope import audit

    audit.log_event("test.empty")
    assert _read_audit(tmp_path)[0]["detail"] == {}


def test_create_and_advance_are_audited(client, tmp_path) -> None:
    eid = client.post("/api/engagements", data={"customer": "AuditCo", "profile": "ticket"}).json()[
        "engagement_id"
    ]
    client.post(f"/api/engagements/{eid}/advance", params={"force": "true"}, data={"reason": "demo"})
    records = _read_audit(tmp_path)
    actions = [r["action"] for r in records]
    assert "engagement.create" in actions
    assert "engagement.advance" in actions
    advance = next(r for r in records if r["action"] == "engagement.advance")
    assert advance["detail"]["engagement_id"] == eid
    assert advance["detail"]["force"] is True
    assert advance["detail"]["advanced"] is True


def test_gate_evaluate_and_skill_publish_are_audited(client, tmp_path) -> None:
    eid = client.post("/api/engagements", data={"customer": "GateAudit", "profile": "ticket"}).json()[
        "engagement_id"
    ]
    client.post(f"/api/engagements/{eid}/gate/success_criteria")
    sid = client.post(
        "/api/skills", json={"title": "审计验证", "category": "research", "body_md": "x"}
    ).json()["id"]
    client.post(f"/api/skills/{sid}/publish")
    actions = [r["action"] for r in _read_audit(tmp_path)]
    assert "engagement.gate_evaluate" in actions
    assert "skill.publish" in actions


def test_audit_detail_carries_no_secrets(client, tmp_path, monkeypatch) -> None:
    """Audit detail must never contain env values / tokens."""
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", "super-secret-token")
    headers = {"Authorization": "Bearer super-secret-token"}
    eid = client.post(
        "/api/engagements", data={"customer": "SecAudit", "profile": "ticket"}, headers=headers
    ).json()["engagement_id"]
    client.post(f"/api/engagements/{eid}/advance", headers=headers)
    raw = (tmp_path / ".fde_scope" / "audit.jsonl").read_text(encoding="utf-8")
    assert "super-secret-token" not in raw


def test_audit_failure_does_not_break_request(client, tmp_path, monkeypatch) -> None:
    """A failing audit sink must not interrupt the business operation."""
    import fde_scope.audit as audit_mod

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(audit_mod, "audit_log_path", boom)
    r = client.post("/api/engagements", data={"customer": "Resilient", "profile": "ticket"})
    assert r.status_code == 200

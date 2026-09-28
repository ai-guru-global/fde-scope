"""P1 审计与证据链：operator/reason、审计导出、证据留存、归档与删除。"""

from __future__ import annotations

import hashlib
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


def _create(client, customer="AuditCo"):
    return client.post("/api/engagements", data={"customer": customer, "profile": "ticket"}).json()[
        "engagement_id"
    ]


# -- operator / reason --------------------------------------------------------
def test_force_advance_without_reason_is_422(client, tmp_path) -> None:
    eid = _create(client)
    r = client.post(f"/api/engagements/{eid}/advance", params={"force": "true"})
    assert r.status_code == 422


def test_force_advance_records_reason_and_operator(client, tmp_path) -> None:
    eid = _create(client)
    r = client.post(
        f"/api/engagements/{eid}/advance",
        params={"force": "true"},
        data={"reason": "客户要求跳过演示阶段", "operator": "allen"},
    )
    assert r.status_code == 200
    rec = next(r for r in _read_audit(tmp_path) if r["action"] == "engagement.advance")
    assert rec["detail"]["force"] is True
    assert rec["detail"]["reason"] == "客户要求跳过演示阶段"
    assert rec["detail"]["operator"] == "allen"


def test_normal_advance_reason_optional(client, tmp_path) -> None:
    eid = _create(client)
    r = client.post(f"/api/engagements/{eid}/advance", data={"operator": "allen"})
    assert r.status_code == 200
    rec = next(r for r in _read_audit(tmp_path) if r["action"] == "engagement.advance")
    assert rec["detail"]["force"] is False
    assert rec["detail"]["operator"] == "allen"
    assert "reason" not in rec["detail"]


def test_gate_evaluate_records_operator(client, tmp_path) -> None:
    eid = _create(client)
    r = client.post(f"/api/engagements/{eid}/gate/success_criteria", data={"operator": "qa-bot"})
    assert r.status_code == 200
    rec = next(r for r in _read_audit(tmp_path) if r["action"] == "engagement.gate_evaluate")
    assert rec["detail"]["operator"] == "qa-bot"


# -- audit export --------------------------------------------------------------
def test_audit_export_filters_by_engagement(client, tmp_path) -> None:
    eid1 = _create(client, "AlphaCo")
    eid2 = _create(client, "BetaCo")
    client.post(f"/api/engagements/{eid1}/advance", data={"reason": "r", "operator": "o"})
    r = client.get(f"/api/engagements/{eid1}/audit")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == len(body["events"])
    assert all(e["detail"].get("engagement_id") == eid1 for e in body["events"])
    assert any(e["detail"]["engagement_id"] != eid2 for e in body["events"])


def test_audit_export_empty_when_no_log(client) -> None:
    r = client.get("/api/engagements/eng-nope/audit")
    assert r.status_code == 200
    assert r.json() == {"engagement_id": "eng-nope", "count": 0, "events": []}


def test_audit_export_markdown_file(client, tmp_path) -> None:
    eid = _create(client)
    client.post(f"/api/engagements/{eid}/advance", data={"reason": "推进", "operator": "allen"})
    r = client.get(f"/api/engagements/{eid}/audit", params={"format": "md"})
    assert r.status_code == 200
    path = tmp_path / "reports" / f"audit_{eid}.md"
    assert r.json()["path"] == str(path)
    text = path.read_text(encoding="utf-8")
    assert "审计报告" in text and "engagement.advance" in text and "allen" in text

    r2 = client.get(f"/api/engagements/{eid}/audit/export")
    assert r2.status_code == 200
    assert r2.json()["path"] == str(path)


# -- handoff evidence ----------------------------------------------------------
def test_handoff_package_hashes_into_audit(client, tmp_path) -> None:
    eid = _create(client)
    r = client.post(f"/api/engagements/{eid}/handoff", data={"accept": "true", "operator": "pm"})
    assert r.status_code == 200
    body = r.json()
    runbook = tmp_path / "reports" / f"runbook_{eid}.md"
    package = tmp_path / "reports" / f"handoff_package_{eid}.json"
    assert body["runbook"] == str(runbook) and runbook.exists()
    assert body["package"] == str(package) and package.exists()
    assert json.loads(package.read_text(encoding="utf-8"))["customer_accepted"] is True

    records = _read_audit(tmp_path)
    pkg = next(r for r in records if r["action"] == "handoff.package")
    assert pkg["detail"]["runbook"]["sha256"] == hashlib.sha256(runbook.read_bytes()).hexdigest()
    assert pkg["detail"]["runbook"]["bytes"] == runbook.stat().st_size
    assert pkg["detail"]["operator"] == "pm"
    acc = next(r for r in records if r["action"] == "handoff.accepted")
    assert acc["detail"]["sha256"] == hashlib.sha256(package.read_bytes()).hexdigest()


# -- evidence attach / list ------------------------------------------------------
def test_evidence_attach_and_list(client, tmp_path) -> None:
    eid = _create(client)
    content = b"signed FAT scan pdf bytes"
    r = client.post(
        f"/api/engagements/{eid}/evidence",
        data={"name": "fat-signed.pdf", "operator": "customer-sponsor"},
        files={"file": ("fat-signed.pdf", content, "application/pdf")},
    )
    assert r.status_code == 200
    entry = r.json()
    digest = hashlib.sha256(content).hexdigest()
    assert entry["sha256"] == digest
    assert entry["operator"] == "customer-sponsor"
    stored = tmp_path / ".fde_scope" / "evidence" / eid / "fat-signed.pdf"
    assert stored.read_bytes() == content

    listing = client.get(f"/api/engagements/{eid}/evidence").json()
    assert listing["evidence"] == [entry]

    rec = next(r for r in _read_audit(tmp_path) if r["action"] == "evidence.attached")
    assert rec["detail"]["sha256"] == digest
    assert rec["detail"]["operator"] == "customer-sponsor"


def test_evidence_attach_from_path(client, tmp_path) -> None:
    eid = _create(client)
    src = tmp_path / "scan.pdf"
    src.write_bytes(b"sat signed")
    r = client.post(
        f"/api/engagements/{eid}/evidence",
        data={"name": "sat.pdf", "path": str(src)},
    )
    assert r.status_code == 200
    assert r.json()["sha256"] == hashlib.sha256(b"sat signed").hexdigest()


def test_evidence_requires_file_or_path(client) -> None:
    eid = _create(client)
    r = client.post(f"/api/engagements/{eid}/evidence", data={"name": "x.pdf"})
    assert r.status_code == 422


def test_evidence_unknown_engagement_404(client) -> None:
    r = client.post(
        "/api/engagements/eng-ghost/evidence",
        data={"name": "x.pdf"},
        files={"file": ("x.pdf", b"x", "application/pdf")},
    )
    assert r.status_code == 404


# -- archive / delete ------------------------------------------------------------
def test_archive_hides_from_listing(client, tmp_path) -> None:
    eid = _create(client)
    r = client.post(f"/api/engagements/{eid}/archive")
    assert r.status_code == 200
    assert eid not in [e["engagement_id"] for e in client.get("/api/engagements").json()]
    assert not (tmp_path / ".fde_scope" / "engagements" / f"{eid}.json").exists()
    assert (tmp_path / ".fde_scope" / "archive" / f"{eid}.json").exists()
    assert client.get(f"/api/engagements/{eid}").status_code == 404
    rec = next(r for r in _read_audit(tmp_path) if r["action"] == "engagement.archived")
    assert rec["detail"]["engagement_id"] == eid


def test_delete_requires_exact_confirm(client, tmp_path) -> None:
    eid = _create(client, "DeleteMe GmbH")
    assert client.request("DELETE", f"/api/engagements/{eid}", data={"confirm": "wrong"}).status_code == 400
    assert client.request("DELETE", f"/api/engagements/{eid}").status_code == 422  # confirm missing
    assert (tmp_path / ".fde_scope" / "engagements" / f"{eid}.json").exists()


def test_delete_removes_data_keeps_audit(client, tmp_path) -> None:
    eid = _create(client, "EraseCo")
    client.post(
        f"/api/engagements/{eid}/evidence",
        data={"name": "fat.pdf"},
        files={"file": ("fat.pdf", b"x", "application/pdf")},
    )
    r = client.request("DELETE", f"/api/engagements/{eid}", data={"confirm": "EraseCo"})
    assert r.status_code == 200
    assert not (tmp_path / ".fde_scope" / "engagements" / f"{eid}.json").exists()
    assert not (tmp_path / ".fde_scope" / "evidence" / eid).exists()
    # 审计日志保留（删除权针对客户数据，不针对合规轨迹）
    records = _read_audit(tmp_path)
    assert any(r["action"] == "engagement.deleted" and r["detail"]["engagement_id"] == eid for r in records)

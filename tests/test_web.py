"""Tests for the Web UI FastAPI app."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    return TestClient(app)


def test_health(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_dashboard_html(client) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "Engagement Console" in r.text


def test_profiles_api(client) -> None:
    r = client.get("/api/profiles")
    data = r.json()
    assert "ticket" in data
    assert "manufacturing" in data
    assert data["manufacturing"]["industrial"] is True


def test_phases_api_manufacturing(client) -> None:
    r = client.get("/api/phases?profile=manufacturing")
    data = r.json()
    assert data["is_industrial"] is True
    assert len(data["phases"]) == 18


def test_phases_api_ticket_excludes_industrial(client) -> None:
    r = client.get("/api/phases?profile=ticket")
    data = r.json()
    slugs = [p["slug"] for p in data["phases"]]
    assert "site_survey" not in slugs  # industrial-only dropped


def test_create_and_advance_engagement(client) -> None:
    # create
    r = client.post("/api/engagements", data={"customer": "TestCo", "profile": "ticket"})
    assert r.status_code == 200
    eid = r.json()["engagement_id"]
    assert r.json()["current_phase"] == "qualification"

    # advance (no gate on qualification → free)
    r = client.post(f"/api/engagements/{eid}/advance")
    assert r.json()["advanced"] is True

    # status reflects new phase
    r = client.get(f"/api/engagements/{eid}")
    assert r.json()["current_phase"] == "stakeholder_map"


def test_advance_blocked_returns_result(client) -> None:
    r = client.post("/api/engagements", data={"customer": "BlockedCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    # jump to success_criteria phase without sponsors/criteria
    client.post(f"/api/engagements/{eid}/context",
                json={"success_criteria": [], "stakeholders": []})
    # manually move context forward to success_criteria
    from fde_scope.engagement import Engagement, EngagementContext
    from fde_scope.web.app import _eng_path

    eng = Engagement(EngagementContext.load(_eng_path(eid)))
    eng.ctx.current_phase = "success_criteria"
    eng.ctx.save(_eng_path(eid))

    r = client.post(f"/api/engagements/{eid}/advance")
    assert r.json()["advanced"] is False
    assert r.json()["result"]["passed"] is False


def test_gates_endpoint(client) -> None:
    r = client.post("/api/engagements", data={"customer": "GateCo", "profile": "manufacturing"})
    eid = r.json()["engagement_id"]
    r = client.get(f"/api/engagements/{eid}/gates")
    gates = r.json()
    # manufacturing profile exposes industrial gates
    assert "functional_safety" in gates


def test_forge_endpoint(client, sample_csv_bytes: bytes) -> None:
    r = client.post(
        "/api/forge",
        files={"file": ("t.csv", sample_csv_bytes, "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert data["report_id"]
    assert data["html_url"].endswith(".html")


def test_kpi_endpoint_manufacturing(client) -> None:
    import json

    payload = "\n".join(json.dumps({
        "availability": 0.9, "performance": 0.95, "quality": 0.99,
        "uptime_hours": 100, "failures": 2, "repair_hours": 4,
        "good_units": 95, "started_units": 100, "defects": 5,
        "opportunities_per_unit": 1,
        "grasp_successes": 80, "grasp_attempts": 100,
        "tasks_succeeded": 90, "tasks_attempted": 100,
        "interventions": 3, "cycles": 1000,
    }) for _ in range(3))
    r = client.post(
        "/api/kpi",
        files={"file": ("s.jsonl", payload.encode(), "application/jsonl")},
        data={"profile": "manufacturing"},
    )
    assert r.status_code == 200
    kpis = r.json()["kpis"]
    assert "oee" in kpis and kpis["oee"] > 0

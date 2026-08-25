"""Tests for the Web UI FastAPI app."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture
def client(tmp_path, monkeypatch):
    # run the app out of a tmp dir so engagements/uploads/reports don't
    # pollute the repo working tree
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    return TestClient(app)


def test_health(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_overview_html(client) -> None:
    """The landing page at / shows the feature overview."""
    r = client.get("/")
    assert r.status_code == 200
    assert "FDE Scope" in r.text
    assert "SOP" in r.text  # the overview mentions the SOP


def test_console_html(client) -> None:
    """The engagement console lives at /console."""
    r = client.get("/console")
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
    client.post(f"/api/engagements/{eid}/context", json={"success_criteria": [], "stakeholders": []})
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

    payload = "\n".join(
        json.dumps(
            {
                "availability": 0.9,
                "performance": 0.95,
                "quality": 0.99,
                "uptime_hours": 100,
                "failures": 2,
                "repair_hours": 4,
                "good_units": 95,
                "started_units": 100,
                "defects": 5,
                "opportunities_per_unit": 1,
                "grasp_successes": 80,
                "grasp_attempts": 100,
                "tasks_succeeded": 90,
                "tasks_attempted": 100,
                "interventions": 3,
                "cycles": 1000,
            }
        )
        for _ in range(3)
    )
    r = client.post(
        "/api/kpi",
        files={"file": ("s.jsonl", payload.encode(), "application/jsonl")},
        data={"profile": "manufacturing"},
    )
    assert r.status_code == 200
    kpis = r.json()["kpis"]
    assert "oee" in kpis and kpis["oee"] > 0


# ---------------------------------------------------------------------------
# security + error-handling regression tests
# ---------------------------------------------------------------------------
def test_create_engagement_sanitizes_customer_in_eid(client, tmp_path) -> None:
    """A path-traversal customer name must not escape the engagements dir."""
    r = client.post("/api/engagements", data={"customer": "a/../../../escaped", "profile": "ticket"})
    assert r.status_code == 200
    eid = r.json()["engagement_id"]
    assert "/" not in eid and ".." not in eid
    # the file landed inside .fde_scope/engagements, not outside it
    eng_dir = tmp_path / ".fde_scope" / "engagements"
    assert (eng_dir / f"{eid}.json").exists()
    assert not (tmp_path / "escaped.json").exists()


def test_eng_path_rejects_traversal_eid(client) -> None:
    """_eng_path refuses ids that resolve outside the engagements dir."""
    from fastapi import HTTPException

    from fde_scope.web.app import _eng_path

    with pytest.raises(HTTPException) as exc_info:
        _eng_path("../../outside")
    assert exc_info.value.status_code == 400


def test_forge_sanitizes_upload_filename(client, tmp_path, sample_csv_bytes: bytes) -> None:
    """An upload named ../../x.csv must not escape the uploads dir."""
    r = client.post(
        "/api/forge",
        files={"file": ("../../x.csv", sample_csv_bytes, "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 200
    assert (tmp_path / ".fde_scope" / "uploads" / "x.csv").exists()
    assert not (tmp_path / "x.csv").exists()


def test_update_context_rejects_string_success_criteria(client) -> None:
    """success_criteria must be a list of strings; a bare string is 422 and
    must not corrupt the persisted engagement."""
    r = client.post("/api/engagements", data={"customer": "CritCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.post(f"/api/engagements/{eid}/context", json={"success_criteria": "not-a-list"})
    assert r.status_code == 422
    # the engagement is still intact and loadable afterwards
    r = client.get(f"/api/engagements/{eid}")
    assert r.status_code == 200


def test_list_engagements_skips_corrupt_file(client, tmp_path) -> None:
    """One corrupt engagement file must not 500 the whole listing."""
    r = client.post("/api/engagements", data={"customer": "GoodCo", "profile": "ticket"})
    assert r.status_code == 200
    bad = tmp_path / ".fde_scope" / "engagements" / "eng-corrupt.json"
    bad.write_text("{not valid json", encoding="utf-8")
    r = client.get("/api/engagements")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_advance_completed_engagement_returns_reason(client) -> None:
    """Advancing a terminal engagement returns advanced=False, not a 500."""
    r = client.post("/api/engagements", data={"customer": "DoneCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    from fde_scope.engagement import Engagement, EngagementContext
    from fde_scope.web.app import _eng_path

    eng = Engagement(EngagementContext.load(_eng_path(eid)))
    eng.ctx.current_phase = "disengage"
    eng.ctx.save(_eng_path(eid))

    r = client.post(f"/api/engagements/{eid}/advance")
    assert r.status_code == 200
    assert r.json() == {"advanced": False, "reason": "complete"}


def test_phases_unknown_profile_404(client) -> None:
    r = client.get("/api/phases?profile=nope")
    assert r.status_code == 404


def test_kpi_unknown_profile_404(client) -> None:
    r = client.post(
        "/api/kpi",
        files={"file": ("s.jsonl", b'{"a": 1}\n', "application/jsonl")},
        data={"profile": "nope"},
    )
    assert r.status_code == 404


def test_kpi_invalid_jsonl_422(client) -> None:
    r = client.post(
        "/api/kpi",
        files={"file": ("s.jsonl", b"{not json}\n", "application/jsonl")},
        data={"profile": "ticket"},
    )
    assert r.status_code == 422


def test_kpi_non_utf8_422(client) -> None:
    r = client.post(
        "/api/kpi",
        files={"file": ("s.jsonl", b"\xff\xfe\x00bad", "application/jsonl")},
        data={"profile": "ticket"},
    )
    assert r.status_code == 422


def test_forge_non_utf8_422(client) -> None:
    r = client.post(
        "/api/forge",
        files={"file": ("t.csv", b"\xff\xfe\x00bad", "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 422


def test_evaluate_unknown_gate_404(client) -> None:
    r = client.post("/api/engagements", data={"customer": "Gate404Co", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.post(f"/api/engagements/{eid}/gate/no_such_gate")
    assert r.status_code == 404


def test_detail_includes_full_context(client) -> None:
    """GET /api/engagements/{eid} must carry the full context for the
    Context tab (stakeholders / site / safety / slos / assets), not just
    the status summary."""
    r = client.post("/api/engagements", data={"customer": "CtxCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.get(f"/api/engagements/{eid}")
    assert r.status_code == 200
    data = r.json()
    assert data["context"]["customer"] == "CtxCo"
    assert "stakeholders" in data["context"]
    assert "success_criteria" in data["context"]
    assert "assets" in data["context"]


def test_console_has_context_tab_renderer(client) -> None:
    """The Context tab must render friendly cards, not raw JSON, and stay
    XSS-safe (no unescaped interpolation of user-supplied context)."""
    html = client.get("/console").text
    assert "function contextHtml(ctx)" in html
    assert "contextHtml(s.context)" in html
    # every user-supplied field rendered inside the tab goes through escapeHtml
    for needle in (
        "esc(site.location)",
        "esc(x.name)",
        "esc(x.role)",
        "esc(x.success_metric||'—')",
        "esc(c)",
    ):
        assert needle in html


# ---------------------------------------------------------------------------
# XSS / upload-limit regression tests
# ---------------------------------------------------------------------------
def test_console_escapes_user_supplied_fields(client) -> None:
    """The console JS must escape every user-supplied field before innerHTML."""
    payload = "<script>alert(1)</script>"
    r = client.post("/api/engagements", data={"customer": payload, "profile": "ticket"})
    assert r.status_code == 200
    # the API preserves the raw value (escaping is a render-layer concern) …
    assert r.json()["customer"] == payload

    html = client.get("/console").text
    # … and every user-controlled interpolation point in the console is escaped
    for needle in (
        "escapeHtml(s.customer)",
        "escapeHtml(s.current_phase)",
        "escapeHtml(s.current_zone)",
        "escapeHtml(s.engagement_id)",
        "escapeHtml(s.next_phase||'— (完成)')",
        "escapeHtml(g.name)",
        "escapeHtml(b)",
        "escapeHtml(w)",
    ):
        assert needle in html, f"console must escape {needle!r}"


def test_forge_oversized_upload_413(client, sample_csv_bytes: bytes) -> None:
    """An upload beyond the size limit is refused with 413, not processed."""
    from fde_scope.web.app import MAX_UPLOAD_BYTES

    big = sample_csv_bytes + b"x" * (MAX_UPLOAD_BYTES + 1)
    r = client.post(
        "/api/forge",
        files={"file": ("big.csv", big, "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 413


def test_kpi_oversized_upload_413(client) -> None:
    """KPI uploads share the same size limit."""
    from fde_scope.web.app import MAX_UPLOAD_BYTES

    big = b"x" * (MAX_UPLOAD_BYTES + 1)
    r = client.post(
        "/api/kpi",
        files={"file": ("big.jsonl", big, "application/jsonl")},
        data={"profile": "manufacturing"},
    )
    assert r.status_code == 413


# ---------------------------------------------------------------------------
# skills API
# ---------------------------------------------------------------------------
def test_skills_api_roundtrip(client, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    r = client.post("/api/skills", json={
        "title": "OPC UA 排查", "category": "implementation", "tags": ["opcua"],
        "body_md": "# 步骤", "phase_slug": "deploy",
    })
    assert r.status_code == 200
    sid = r.json()["id"]
    assert r.json()["status"] == "draft"
    assert client.post(f"/api/skills/{sid}/publish").status_code == 200
    got = client.get(f"/api/skills/{sid}")
    assert got.status_code == 200 and got.json()["status"] == "published"
    lst = client.get("/api/skills?category=implementation")
    assert lst.status_code == 200 and len(lst.json()) == 1
    drafts = client.get("/api/skills/drafts")
    assert drafts.status_code == 200 and len(drafts.json()) == 0  # 已发布
    exp = client.post(f"/api/skills/{sid}/export", json={"format": "agentscope"})
    assert exp.status_code == 200
    assert exp.json()["files"][0]["name"].endswith("SKILL.md")
    arch = client.post(f"/api/skills/{sid}/archive")
    assert arch.status_code == 200 and arch.json()["status"] == "archived"

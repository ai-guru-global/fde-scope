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


def test_health_reports_real_checks(client, monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    monkeypatch.delenv("FDE_SCOPE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("FDE_SCOPE_LLM_API_KEY", raising=False)
    body = client.get("/api/health").json()
    checks = body["checks"]
    assert checks["data_root"]["ok"] is True
    assert "path" in checks["data_root"]
    assert checks["reports_dir"]["ok"] is True
    assert checks["llm"] == {"ok": True, "configured": False}
    assert checks["engagements_count"] == {"ok": True, "count": 0}


def test_health_counts_engagements(client) -> None:
    client.post("/api/engagements", data={"customer": "HealthCo", "profile": "ticket"})
    body = client.get("/api/health").json()
    assert body["checks"]["engagements_count"]["count"] == 1
    assert body["status"] == "ok"


def test_health_llm_configured_via_env(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_MIMO_API_KEY", "tp-health")
    resp = client.get("/api/health")
    assert resp.json()["checks"]["llm"]["configured"] is True
    assert "tp-health" not in resp.text  # the key itself never leaves the env


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


# ---------------------------------------------------------------------------
# bilingual routes（/en/* 英文壳，与 zh 同源模板经 to_en 生成）
# ---------------------------------------------------------------------------
def test_en_overview_html(client) -> None:
    """/en/ serves the English overview shell."""
    r = client.get("/en/")
    assert r.status_code == 200
    assert '<html lang="en">' in r.text
    assert "Ontology semantic layer · TBox + ABox" in r.text
    assert "Ontology 语义层" not in r.text


def test_en_console_html(client) -> None:
    """/en/console serves the English console shell."""
    r = client.get("/en/console")
    assert r.status_code == 200
    assert '<html lang="en">' in r.text
    assert "Workbench</button>" in r.text
    assert "Skills</button>" in r.text
    assert "工作台</button>" not in r.text


def test_language_switcher_badges(client) -> None:
    """zh pages badge to /en/*; EN pages flip the badge back to zh routes."""
    zh_home = client.get("/").text
    zh_console = client.get("/console").text
    en_home = client.get("/en/").text
    en_console = client.get("/en/console").text
    assert 'href="/en/"' in zh_home
    assert 'href="/en/console"' in zh_console
    assert 'aria-label="Switch to English"' in zh_home
    assert 'aria-label="切换到中文"' in en_home
    assert 'aria-label="切换到中文"' in en_console


def test_en_glossary_english_tips(client) -> None:
    """EN pages ship the English glossary (Chinese terms kept as keys)."""
    html = client.get("/en/").text
    assert "__GLOSSARY__" not in html
    assert "Standard Operating Procedure; here, the 18-phase project lifecycle." in html


def test_glossary_tooltips_on_both_pages(client) -> None:
    """Both pages ship the ?-tooltip glossary: CSS + script + term data."""
    for path in ("/", "/console"):
        html = client.get(path).text
        assert "__GLOSSARY__" not in html  # placeholder must be replaced
        assert ".term .tip" in html  # tooltip CSS shipped
        assert "window.glossify" in html  # glossify() script shipped
        assert "Gemba walk" in html  # glossary data includes the term…
        assert "現場" in html  # …and its explanation


def test_glossary_glossifies_console_dynamic_views(client) -> None:
    """Console re-runs glossify() after JS-rendered views, not just on load."""
    html = client.get("/console").text
    assert "glossify(document.getElementById('view-workbench'))" in html
    assert "glossify(document.getElementById('view-skills'))" in html
    assert "glossify(document.getElementById('view-detail'))" in html
    assert "glossify(el)" in html  # sidebar engagement list


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
    from fde_scope.web.deps import _eng_path

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

    from fde_scope.web.deps import _eng_path

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
    from fde_scope.web.deps import _eng_path

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
    r = client.post(
        "/api/skills",
        json={
            "title": "OPC UA 排查",
            "category": "implementation",
            "tags": ["opcua"],
            "body_md": "# 步骤",
            "phase_slug": "deploy",
        },
    )
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


# ---------------------------------------------------------------------------
# journal（现场记录）
# ---------------------------------------------------------------------------
def test_journal_api_roundtrip(client) -> None:
    eid = client.post("/api/engagements", data={"customer": "Acme"}).json()["engagement_id"]
    assert client.get(f"/api/engagements/{eid}/journal").json() == []
    r = client.post(f"/api/engagements/{eid}/journal", json={"kind": "research", "note": "产线 A 调研"})
    assert r.status_code == 200
    assert r.json()["kind"] == "research"
    entries = client.get(f"/api/engagements/{eid}/journal").json()
    assert len(entries) == 1 and entries[0]["note"] == "产线 A 调研"
    # 校验：非法 kind / 空 note
    assert (
        client.post(f"/api/engagements/{eid}/journal", json={"kind": "oops", "note": "x"}).status_code == 422
    )
    assert client.post(f"/api/engagements/{eid}/journal", json={"note": "  "}).status_code == 422


def test_journal_to_skill_bridge(client) -> None:
    eid = client.post("/api/engagements", data={"customer": "BMW"}).json()["engagement_id"]
    jid = client.post(
        f"/api/engagements/{eid}/journal", json={"kind": "implementation", "note": "部署完成"}
    ).json()["id"]
    r = client.post(f"/api/engagements/{eid}/journal/{jid}/skill")
    assert r.status_code == 200
    rec = r.json()
    assert rec["category"] == "implementation"  # kind → category 映射
    assert rec["source_engagement"] == eid
    assert rec["status"] == "draft"
    # skill_id 回写 journal entry
    entries = client.get(f"/api/engagements/{eid}/journal").json()
    assert entries[0]["skill_id"] == rec["id"]
    # 重复沉淀 → 409；未知 jid → 404
    assert client.post(f"/api/engagements/{eid}/journal/{jid}/skill").status_code == 409
    assert client.post(f"/api/engagements/{eid}/journal/jn-nope/skill").status_code == 404


# ---------------------------------------------------------------------------
# workbench（工作台聚合）
# ---------------------------------------------------------------------------
def test_workbench_api_empty(client) -> None:
    data = client.get("/api/workbench").json()
    assert data["stats"] == {
        "active_projects": 0,
        "phase_distribution": {},
        "draft_skills": 0,
        "total_skills": 0,
    }
    assert data["matrix"] == []
    assert data["recent_skills"] == []


def test_workbench_api_stats_matrix_recent(client) -> None:
    client.post("/api/engagements", data={"customer": "Acme"})
    client.post("/api/engagements", data={"customer": "BMW", "profile": "manufacturing"})
    wb = client.get("/api/workbench").json()
    assert wb["stats"]["active_projects"] == 2
    assert wb["stats"]["phase_distribution"] == {"qualification": 2}
    assert len(wb["matrix"]) == 2
    assert wb["matrix"][0]["customer"] in ("Acme", "BMW")
    # 技能：草稿计入 draft_skills；发布后进入 recent_skills
    sid = client.post(
        "/api/skills", json={"title": "OPC UA 踩坑", "category": "implementation", "tags": ["opcua"]}
    ).json()["id"]
    assert client.get("/api/workbench").json()["stats"]["draft_skills"] == 1
    client.post(f"/api/skills/{sid}/publish")
    wb2 = client.get("/api/workbench").json()
    assert wb2["stats"]["draft_skills"] == 0
    assert wb2["stats"]["total_skills"] == 1
    assert wb2["recent_skills"][0]["id"] == sid


def test_console_has_workbench_and_skills_views(client) -> None:
    """控制台包含工作台/技能库视图与现场记录 tab（单页无构建）。"""
    r = client.get("/console")
    assert r.status_code == 200
    assert 'id="view-workbench"' in r.text
    assert 'id="view-skills"' in r.text
    assert ">工作台</button>" in r.text
    assert ">技能库</button>" in r.text
    assert "现场记录" in r.text
    assert "沉淀为技能" in r.text
    assert "草稿审阅队列" in r.text


# ---------------------------------------------------------------------------
# deploy plan API（角色 → 连接器 → 工具绑定）
# ---------------------------------------------------------------------------
def test_deploy_plan_binds_configured_sources(client) -> None:
    """配了源的角色拿到工具，没配的诚实标 unbound，并进入 ALLOW 规则。"""
    r = client.post(
        "/api/deploy/plan",
        json={
            "tenant": "caocao",
            "name": "曹操出行",
            "sources": {"csv": "data/t.csv", "documents": "docs/"},
            "agents": [{"name": "analyst", "role": "数据分析"}, {"name": "archivist", "role": "文件分析"}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == {
        "bound_tools": ["csv_sample", "csv_schema", "documents_sample", "documents_schema"],
        "unbound_tools": ["mes_sample", "mes_schema", "mysql_sample", "mysql_schema"],
        "agents": 2,
    }
    agents = body["manifest"]["agents"]
    assert [a["role_bucket"] for a in agents] == ["data", "files"]
    allowed = {tool for tool, _ in body["manifest"]["permissions"]["allow"]}
    assert "csv_sample" in allowed and "mes_sample" not in allowed


def test_deploy_plan_defaults_to_single_agent(client) -> None:
    """不声明 agents 时回退单 Agent（角色 = 租户名 → 不绑任何连接器）。"""
    body = client.post("/api/deploy/plan", json={"tenant": "acme"}).json()
    assert body["summary"]["agents"] == 1
    assert body["manifest"]["agents"][0]["name"] == "acme_agent"
    assert body["summary"]["bound_tools"] == []
    assert body["summary"]["unbound_tools"] == []


def test_deploy_plan_rejects_bad_agent_spec(client) -> None:
    r = client.post("/api/deploy/plan", json={"tenant": "acme", "agents": [{"role": "缺名字"}]})
    assert r.status_code == 422


def test_ontology_export_api_schema_jsonld(client) -> None:
    """内置 schema 可直接导出 JSON-LD（与 CLI ontology export 同一实现）。"""
    r = client.get("/api/ontology/export/fde-core")
    assert r.status_code == 200
    doc = r.json()
    assert "@context" in doc and "@graph" in doc


def test_ontology_stores_api_lists_workspace_stores(client) -> None:
    """store 列表端点供 console 本体库视图使用（id / ontology_ref / individuals）。"""
    from fde_scope.ontology.models import InstanceStore
    from fde_scope.ontology.store import OntologyStore

    OntologyStore().save_store(
        InstanceStore(
            id="acme-tickets",
            ontology_ref="fde-core@1.0.0",
            individuals=[{"curie": "ex:evt-1"}],
        )
    )
    r = client.get("/api/ontology/stores")
    assert r.status_code == 200
    entry = next(e for e in r.json() if e["id"] == "acme-tickets")
    assert entry == {"id": "acme-tickets", "ontology_ref": "fde-core@1.0.0", "individuals": 1}


def test_ontology_export_api_store_wraps_tbox(client) -> None:
    """实例库导出带 TBox 上下文：individuals 来自 store，classes 来自其 ontology_ref。"""
    from fde_scope.ontology.models import InstanceStore
    from fde_scope.ontology.store import OntologyStore

    store = OntologyStore()
    store.save_store(InstanceStore(id="acme-tickets", ontology_ref="fde-core@1.0.0"))
    r = client.get("/api/ontology/export/acme-tickets")
    assert r.status_code == 200
    doc = r.json()
    assert "@context" in doc and "@graph" in doc


def test_ontology_export_api_unknown_target_404(client) -> None:
    r = client.get("/api/ontology/export/does-not-exist")
    assert r.status_code == 404
    assert r.json()["detail"] == "unknown ontology export target: does-not-exist"


def test_console_has_ontology_view(client) -> None:
    """console 提供只读 ontology 视图（导航 + 容器 + 加载器 + hash 路由）。"""
    html = client.get("/console").text
    assert 'data-view="ontology"' in html
    assert 'id="view-ontology"' in html
    assert "loadOntology" in html
    assert "location.hash === '#ontology'" in html


def test_overview_has_ontology_section(client) -> None:
    """落地页有 ontology section，并链向 console 的 ontology 视图。"""
    html = client.get("/").text
    assert "Ontology 语义层" in html
    assert 'href="/console#ontology"' in html


# ---------------------------------------------------------------------------
# guided mode（引导模式：只读引导 + catalog 本地 serve）
# ---------------------------------------------------------------------------
def test_guided_endpoint_structure(client) -> None:
    r = client.post("/api/engagements", data={"customer": "GuidedCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.get(f"/api/engagements/{eid}/guided")
    assert r.status_code == 200
    body = r.json()
    assert body["phase"]["slug"] == "qualification"
    assert body["deliverables"]
    assert isinstance(body["llm_available"], bool)
    assert body["catalog_pages"] and all("url" in p and "route" in p for p in body["catalog_pages"])


def test_guided_endpoint_404(client) -> None:
    assert client.get("/api/engagements/nope/guided").status_code == 404


def test_guided_translates_blockers_into_next_steps(client) -> None:
    r = client.post("/api/engagements", data={"customer": "StepCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    # walk to success_criteria (qualification/stakeholder_map have no gates for ticket)
    for _ in range(2):
        client.post(f"/api/engagements/{eid}/advance")
    body = client.get(f"/api/engagements/{eid}/guided").json()
    assert body["phase"]["slug"] == "success_criteria"
    gate = body["gates"]["success_criteria"]
    assert gate["passed"] is False
    assert gate["next_steps"] and all(s["advice"] for s in gate["next_steps"])


def test_guided_does_not_record_gates(client) -> None:
    """Guidance is read-only: no gate_records are written by /guided."""
    r = client.post("/api/engagements", data={"customer": "ROCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    before = client.get(f"/api/engagements/{eid}").json()["context"]["gate_records"]
    client.get(f"/api/engagements/{eid}/guided")
    after = client.get(f"/api/engagements/{eid}").json()["context"]["gate_records"]
    assert before == after


def test_existing_routes_survive_guided_router(client) -> None:
    """Route-snapshot guard: the guided router must not shadow existing API."""
    from fde_scope.web.app import app

    paths = set(app.openapi()["paths"])
    for expected in (
        "/api/health",
        "/api/profiles",
        "/api/phases",
        "/api/engagements",
        "/api/engagements/{eid}",
        "/api/engagements/{eid}/gates",
        "/api/engagements/{eid}/advance",
        "/api/engagements/{eid}/gate/{slug}",
        "/api/engagements/{eid}/journal",
        "/api/engagements/{eid}/context",
        "/api/forge",
        "/api/kpi",
        "/api/deploy/plan",
        "/api/workbench",
        "/api/skills",
        "/api/engagements/{eid}/guided",
    ):
        assert expected in paths, f"missing route: {expected}"


def test_console_has_guided_tab(client) -> None:
    html = client.get("/console").text
    assert """tab('guided',this)""" in html
    assert "guidedHtml" in html
    # the original 7 tabs are untouched
    for name in ("overview", "sop", "gates", "context", "forge", "kpi", "journal"):
        assert f"""tab('{name}',this)""" in html


def test_en_console_translates_guided_tab(client) -> None:
    html = client.get("/en/console").text
    assert """tab('guided',this)">Guided</button>""" in html
    assert "What to deliver in this phase" in html


def test_catalog_portal_served_locally(client) -> None:
    from fde_scope.web.deps import catalog_site_dir

    if catalog_site_dir() is None:
        import pytest

        pytest.skip("catalog portal not built in this checkout")
    r = client.get("/catalog/index.html")
    assert r.status_code == 200
    assert "firecrawl-search" in r.text


def test_guided_catalog_urls_are_local_when_mounted(client) -> None:
    from fde_scope.web.deps import catalog_site_dir

    r = client.post("/api/engagements", data={"customer": "CatCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    body = client.get(f"/api/engagements/{eid}/guided").json()
    if catalog_site_dir() is None:
        assert body["catalog_local"] is False
        assert all(p["url"].startswith("https://github.com/") for p in body["catalog_pages"])
    else:
        assert body["catalog_local"] is True
        assert all(p["url"].startswith("/catalog/index.html#/") for p in body["catalog_pages"])


# ---------------------------------------------------------------------------
# guided mode: AI draft-context + goal plan（迭代 3/4）
# ---------------------------------------------------------------------------
_GOOD_DRAFT_JSON = (
    '{"stakeholders": [{"name": "张三", "role": "CTO", "is_sponsor": true, "success_metric": "首响<8s"},'
    '{"name": "李四", "role": "COO", "is_sponsor": true}],'
    ' "success_criteria": ["首响 <8s"]}'
)


def _fake_mimo(monkeypatch, reply=None, error=False):
    from fde_scope import llm as llm_mod

    monkeypatch.setattr(llm_mod.MiMoClient, "available", property(lambda self: True))

    def complete(self, prompt, **kwargs):
        if error:
            raise RuntimeError("boom")
        return reply

    monkeypatch.setattr(llm_mod.MiMoClient, "complete", complete)


def _mk(client, customer="DraftCo", profile="ticket"):
    return client.post("/api/engagements", data={"customer": customer, "profile": profile}).json()[
        "engagement_id"
    ]


def test_draft_context_endpoint(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, reply=_GOOD_DRAFT_JSON)
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "我们是茶饮连锁…"})
    assert r.status_code == 200
    body = r.json()
    assert body["used_llm"] is True
    assert len(body["draft"]["stakeholders"]) == 2
    assert body["current"]["stakeholders"] == []
    assert body["field_guide"]


def test_draft_context_never_persists(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, reply=_GOOD_DRAFT_JSON)
    eid = _mk(client)
    before = client.get(f"/api/engagements/{eid}").json()["context"]
    client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"})
    after = client.get(f"/api/engagements/{eid}").json()["context"]
    assert before == after


def test_draft_context_garbage_llm_output_is_200_null(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, reply="完全不是 JSON")
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"})
    assert r.status_code == 200
    assert r.json()["draft"] is None
    assert r.json()["used_llm"] is False


def test_draft_context_llm_error_is_200_null(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, error=True)
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"})
    assert r.status_code == 200
    assert r.json()["draft"] is None


def test_draft_context_rejects_blank_and_oversize(client) -> None:
    eid = _mk(client)
    assert (
        client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "   "}).status_code
        == 422
    )
    assert (
        client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": ""}).status_code
        == 422
    )
    big = "x" * 8001
    assert (
        client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": big}).status_code
        == 422
    )


def test_draft_apply_flows_through_context_and_gate(client, monkeypatch) -> None:
    """End-to-end: draft → apply via POST /context → success_criteria gate flips to pass.

    Proves AI prefill goes through the front door and gates remain the sole
    acceptance channel (invariant 1)."""
    _fake_mimo(monkeypatch, reply=_GOOD_DRAFT_JSON)
    eid = _mk(client)
    for _ in range(2):  # qualification → stakeholder_map → success_criteria
        client.post(f"/api/engagements/{eid}/advance")
    guided = client.get(f"/api/engagements/{eid}/guided").json()
    assert guided["phase"]["slug"] == "success_criteria"
    assert guided["gates"]["success_criteria"]["passed"] is False

    draft = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"}).json()[
        "draft"
    ]
    r = client.post(f"/api/engagements/{eid}/context", json=draft)
    assert r.status_code == 200

    guided = client.get(f"/api/engagements/{eid}/guided").json()
    assert guided["gates"]["success_criteria"]["passed"] is True
    assert guided["gates"]["success_criteria"]["next_steps"] == []


def test_draft_context_without_key_falls_back(client, monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"})
    assert r.status_code == 200
    body = r.json()
    assert body["draft"] is None and body["used_llm"] is False
    assert body["field_guide"]  # manual fallback still served


def test_goal_plan_rule_version_persists(client, monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    eid = _mk(client)
    gates_before = client.get(f"/api/engagements/{eid}/gates").json()
    r = client.post(f"/api/engagements/{eid}/guided/plan", json={"goal": "把首响缩到 8s 内"})
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] is True and body["used_llm"] is False
    plan = body["plan"]
    assert plan["goal"] == "把首响缩到 8s 内"
    assert {i["phase_slug"] for i in plan["items"]} >= {"qualification", "disengage"}
    # persisted into assets and echoed by GET /guided
    ctx = client.get(f"/api/engagements/{eid}").json()["context"]
    assert ctx["assets"]["guided_plan"]["goal"] == plan["goal"]
    assert client.get(f"/api/engagements/{eid}/guided").json()["plan"]["goal"] == plan["goal"]
    # planning never touches the state machine
    assert client.get(f"/api/engagements/{eid}/gates").json() == gates_before


def test_goal_plan_llm_enhanced(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, reply='{"qualification": ["定制任务A"]}')
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/plan", json={"goal": "目标"})
    body = r.json()
    assert body["used_llm"] is True
    assert any(i["title"] == "定制任务A" for i in body["plan"]["items"])


def test_goal_plan_rejects_blank(client) -> None:
    eid = _mk(client)
    assert client.post(f"/api/engagements/{eid}/guided/plan", json={"goal": "  "}).status_code == 422


def test_plan_checkbox_roundtrip_via_context(client, monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    eid = _mk(client)
    plan = client.post(f"/api/engagements/{eid}/guided/plan", json={"goal": "目标"}).json()["plan"]
    plan["items"][0]["done"] = True
    r = client.post(f"/api/engagements/{eid}/context", json={"assets": {"guided_plan": plan}})
    assert r.status_code == 200
    echoed = client.get(f"/api/engagements/{eid}/guided").json()["plan"]
    assert echoed["items"][0]["done"] is True
    assert echoed["items"][0]["id"] == plan["items"][0]["id"]  # ids stable across save


def test_console_ships_guided_ai_and_plan_ui(client) -> None:
    html = client.get("/console").text
    for needle in ("gdDraftCtx", "gdPlan", "gdRenderGuide", "AI 起草 Context", "项目目标与任务清单"):
        assert needle in html


def test_en_console_translates_guided_ai_card(client) -> None:
    html = client.get("/en/console").text
    assert "Draft context with AI" in html
    assert "Project goal & task plan" in html

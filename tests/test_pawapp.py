"""Smoke tests for the QwenPaw PawApp plugin (pawapp/backend/main.py).

``qwenpaw`` is not a dependency of fde-scope, so the PawApp SDK is stubbed
with a no-op implementation; the routes are exercised through a plain FastAPI
app. This keeps the plugin regression-checked without QwenPaw installed.
"""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

_PAWAPP_BACKEND = Path(__file__).parent.parent / "pawapp" / "backend"


def _load_pawapp_main(monkeypatch):
    """Import pawapp/backend/main.py with a stubbed qwenpaw.pawapp SDK."""

    class _StubPawApp:
        def __init__(self, **kwargs) -> None:
            pass

        def include_router(self, *args, **kwargs) -> None:
            pass

        def tool(self, *args, **kwargs):
            def deco(f):
                return f

            return deco

        def on_launch(self, f):
            return f

        def __getattr__(self, name):
            def deco(*args, **kwargs):
                def wrap(f):
                    return f

                return wrap

            return deco

    qp = types.ModuleType("qwenpaw")
    qp_pawapp = types.ModuleType("qwenpaw.pawapp")
    qp_pawapp.PawApp = _StubPawApp
    qp_pawapp.get_ctx = lambda: None
    qp.pawapp = qp_pawapp
    monkeypatch.setitem(sys.modules, "qwenpaw", qp)
    monkeypatch.setitem(sys.modules, "qwenpaw.pawapp", qp_pawapp)

    sys.path.insert(0, str(_PAWAPP_BACKEND))
    try:
        sys.modules.pop("main", None)
        return importlib.import_module("main")
    finally:
        sys.path.remove(str(_PAWAPP_BACKEND))


def _client(main_module) -> TestClient:
    app = FastAPI()
    # Same prefix the QwenPaw host really registers (see scripts/verify_pawapp_host.py);
    # mounting under a different one here would let the two drift apart.
    app.include_router(main_module.router, prefix="/api/fde-scope")
    return TestClient(app)


def test_pawapp_routes_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """health / profiles / engagement lifecycle / gates / skills all respond."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".fde_scope" / "engagements").mkdir(parents=True)
    (tmp_path / ".fde_scope" / "skills").mkdir(parents=True)

    main = _load_pawapp_main(monkeypatch)
    client = _client(main)

    assert client.get("/api/fde-scope/health").status_code == 200
    profiles = client.get("/api/fde-scope/profiles").json()
    assert len(profiles) >= 2  # ticket + manufacturing
    assert client.get("/api/fde-scope/phases").status_code == 200

    r = client.post("/api/fde-scope/engagements", data={"customer": "SmokeCo", "profile": "ticket"})
    assert r.status_code == 200, r.text
    eid = r.json()["engagement_id"]

    assert client.get(f"/api/fde-scope/engagements/{eid}").status_code == 200
    assert client.get(f"/api/fde-scope/engagements/{eid}/gates").status_code == 200
    assert client.post(f"/api/fde-scope/engagements/{eid}/advance").status_code == 200
    assert client.get("/api/fde-scope/skills").status_code == 200


def test_pawapp_deploy_plan_route_matches_the_deployer(tmp_path: Path, monkeypatch) -> None:
    """The desktop route answers from ``build_deploy_plan``, including its 422s."""
    monkeypatch.chdir(tmp_path)
    main = _load_pawapp_main(monkeypatch)
    client = _client(main)

    r = client.post(
        "/api/fde-scope/deploy/plan",
        json={
            "tenant": "northern",
            "sources": {"csv": "data/t.csv"},
            "agents": [{"name": "a", "role": "数据分析"}],
        },
    )
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]
    assert "csv_schema" in summary["bound_tools"]
    assert "mysql_schema" in summary["unbound_tools"]  # same role, source unknown
    assert client.post("/api/fde-scope/deploy/plan", json={"agents": [{"role": "x"}]}).status_code == 422


def test_pawapp_deploy_plan_tool_reads_roles_and_sources(tmp_path: Path, monkeypatch) -> None:
    """The host-agent tool must answer without AgentScope, Docker, or a model."""
    import asyncio

    monkeypatch.chdir(tmp_path)
    main = _load_pawapp_main(monkeypatch)
    out = asyncio.run(
        main.fde_deploy_plan("teaverse", "数据分析,文件分析", '{"documents": "docs/"}'),
    )
    assert out["summary"]["agents"] == 2
    assert out["summary"]["bound_tools"] == ["documents_sample", "documents_schema"]
    assert "TODO " in out["plan"]  # unbound sources stay visible, never faked
    assert "not valid JSON" in asyncio.run(main.fde_deploy_plan("x", sources_json="[")).get("error", "")


def test_pawapp_eng_path_rejects_traversal(tmp_path: Path, monkeypatch) -> None:
    """直接单测防御函数：穿越型 engagement id 抛 400（HTTP 层会被路由提前 404）。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".fde_scope" / "engagements").mkdir(parents=True)

    main = _load_pawapp_main(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        main._eng_path("../../etc/passwd")
    assert ei.value.status_code == 400


# ---------------------------------------------------------------------------
# Remaining routes: the ones the desktop app actually exposes beyond smoke
# ---------------------------------------------------------------------------
def _ready(tmp_path: Path, monkeypatch):
    """A home with the two directories the routes expect, plus a client."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".fde_scope" / "engagements").mkdir(parents=True)
    (tmp_path / ".fde_scope" / "skills").mkdir(parents=True)
    main = _load_pawapp_main(monkeypatch)
    return main, _client(main)


def _new_engagement(client: TestClient, customer: str = "Acme", profile: str = "ticket") -> str:
    r = client.post("/api/fde-scope/engagements", data={"customer": customer, "profile": profile})
    assert r.status_code == 200, r.text
    return r.json()["engagement_id"]


def test_pawapp_phases_rejects_unknown_profile(tmp_path: Path, monkeypatch) -> None:
    main, client = _ready(tmp_path, monkeypatch)
    assert client.get("/api/fde-scope/phases?profile=manufacturing").json()["is_industrial"] is True
    assert client.get("/api/fde-scope/phases?profile=nope").status_code == 404


def test_pawapp_gate_route_evaluates_and_404s_on_unknown_slug(tmp_path: Path, monkeypatch) -> None:
    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)

    # A gate can be evaluated against the context at any time. ``success_criteria``
    # applies to the ticket profile; with nothing recorded it must block.
    ok = client.post(f"/api/fde-scope/engagements/{eid}/gate/success_criteria")
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["slug"] == "success_criteria"
    assert body["passed"] is False and body["blockers"], "empty success criteria must block"

    # ``site_survey`` is a manufacturing-overlay gate: on a ticket engagement it
    # is reported as not applicable (passing) rather than silently skipped.
    overlay = client.post(f"/api/fde-scope/engagements/{eid}/gate/site_survey").json()
    assert overlay["passed"] is True

    assert client.post(f"/api/fde-scope/engagements/{eid}/gate/nope").status_code == 404


def test_pawapp_advance_reports_blockers_then_completes(tmp_path: Path, monkeypatch) -> None:
    """advance → blocked path, list view, and the terminal StopIteration path."""
    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)

    # qualification → stakeholder_map: no gate on either, so this passes.
    assert client.post(f"/api/fde-scope/engagements/{eid}/advance").json()["advanced"] is True
    # stakeholder_map → success_criteria: still ungated.
    assert client.post(f"/api/fde-scope/engagements/{eid}/advance").json()["advanced"] is True
    # success_criteria → connect is gated on success_criteria: blocked.
    blocked = client.post(f"/api/fde-scope/engagements/{eid}/advance").json()
    assert blocked["advanced"] is False
    assert blocked["result"]["blockers"]

    listed = client.get("/api/fde-scope/engagements").json()
    assert [e["engagement_id"] for e in listed] == [eid]

    # Force all the way to the end; the last advance must answer "complete".
    answer = None
    for _ in range(40):
        answer = client.post(f"/api/fde-scope/engagements/{eid}/advance?force=true").json()
        if answer.get("reason") == "complete":
            break
    assert answer is not None and answer["reason"] == "complete"


def test_pawapp_engagement_404s(tmp_path: Path, monkeypatch) -> None:
    main, client = _ready(tmp_path, monkeypatch)
    assert client.get("/api/fde-scope/engagements/missing").status_code == 404


def test_pawapp_kpi_route(tmp_path: Path, monkeypatch) -> None:
    main, client = _ready(tmp_path, monkeypatch)
    jsonl = b'{"actual": 10, "predicted": 9}\n{"actual": 12, "predicted": 10}\n'
    r = client.post(
        "/api/fde-scope/kpi",
        data={"profile": "manufacturing"},
        files={"file": ("k.jsonl", jsonl, "application/json")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sample_count"] == 2

    bad = client.post(
        "/api/fde-scope/kpi",
        data={"profile": "manufacturing"},
        files={"file": ("k.jsonl", b"not json\n", "application/json")},
    )
    assert bad.status_code == 422
    unknown = client.post(
        "/api/fde-scope/kpi",
        data={"profile": "nope"},
        files={"file": ("k.jsonl", jsonl, "application/json")},
    )
    assert unknown.status_code == 404
    undecodable = client.post(
        "/api/fde-scope/kpi",
        data={"profile": "manufacturing"},
        files={"file": ("k.jsonl", b"\xff\xfe\x00", "application/json")},
    )
    assert undecodable.status_code == 422


def test_pawapp_forge_route_writes_report(tmp_path: Path, monkeypatch) -> None:
    import csv
    import io

    main, client = _ready(tmp_path, monkeypatch)
    rows = [
        ["id", "content", "category"],
        *[[str(i), f"我要申请退款第{i}单", "退款"] for i in range(6)],
        *[[str(i), f"物流太慢了第{i}单", "物流"] for i in range(6)],
    ]
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    r = client.post(
        "/api/fde-scope/forge",
        data={"min_samples": "10", "synth_per_gap": "2"},
        files={"file": ("d.csv", buf.getvalue().encode(), "text/csv")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["real"] == 12
    assert body["report_id"]
    # Both report artifacts land in the engine's reports dir and the JSON is
    # the engine's own model_dump_json (the atomic primitive preserves content).
    from fde_scope import paths

    reports = Path(paths.reports_dir())
    html = reports / f"corpus_report_{body['report_id']}.html"
    js = reports / f"corpus_report_{body['report_id']}.json"
    assert html.is_file() and js.is_file()
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert payload["real"] == body["real"] == 12
    assert payload["eval"].keys() >= {"name", "items"}
    for artifact in (html, js):
        artifact.unlink(missing_ok=True)


def test_pawapp_forge_rejects_bad_uploads(tmp_path: Path, monkeypatch) -> None:

    main, client = _ready(tmp_path, monkeypatch)
    big = client.post(
        "/api/fde-scope/forge",
        files={"file": ("d.csv", b"x" * (main.MAX_UPLOAD_BYTES + 10), "text/csv")},
    )
    assert big.status_code == 413
    bad = client.post(
        "/api/fde-scope/forge",
        files={"file": ("d.csv", b"\xff\xfe\x00bad", "text/csv")},
    )
    assert bad.status_code == 422


def test_pawapp_skills_publish_export_and_drafts(tmp_path: Path, monkeypatch) -> None:
    from fde_scope import paths
    from fde_scope.skills.service import SkillService
    from fde_scope.skills.store import SkillStore

    main, client = _ready(tmp_path, monkeypatch)
    svc = SkillService(SkillStore(paths.skills_dir()))
    from fde_scope.skills.models import SkillCategory, SkillDraft

    rec = svc.create(
        SkillDraft(
            title="现场回滚技巧",
            category=SkillCategory.OPTIMIZATION,
            body_md="回滚前先冻结写入，再按 runbook 第 4 节执行。",
        )
    )
    sid = rec.id

    assert client.get("/api/fde-scope/skills/drafts").status_code == 200

    published = client.post(f"/api/fde-scope/skills/{sid}/publish")
    assert published.status_code == 200, published.text

    exported = client.post(f"/api/fde-scope/skills/{sid}/export", data={"fmt": "qwenpaw"})
    assert exported.status_code == 200, exported.text
    files = exported.json()["files"]
    assert files and all(f["path"].endswith(".md") for f in files)

    assert client.post("/api/fde-scope/skills/nope/publish").status_code == 404
    assert client.post("/api/fde-scope/skills/nope/export").status_code == 404
    assert client.post(f"/api/fde-scope/skills/{sid}/export", data={"fmt": "nope"}).status_code == 400


def test_pawapp_runbook_falls_back_to_template(tmp_path: Path, monkeypatch) -> None:
    """No host model in the stub context → the Jinja template, used_llm False."""
    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)

    r = client.post(f"/api/fde-scope/handoff/{eid}/runbook")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["used_llm"] is False
    assert Path(body["path"]).exists()
    assert Path(body["path"]).read_text(encoding="utf-8").strip()


def test_pawapp_runbook_uses_host_text_when_provided(tmp_path: Path, monkeypatch) -> None:
    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)

    class _Reply:
        text = "# Host-drafted runbook\n"

    class _Ctx:
        async def chat(self, _prompt: str):
            return _Reply()

    import asyncio

    out = asyncio.run(main.draft_runbook(eid, ctx=_Ctx()))
    assert out["used_llm"] is True
    assert "Host-drafted" in Path(out["path"]).read_text(encoding="utf-8")


def test_pawapp_handoff_package(tmp_path: Path, monkeypatch) -> None:
    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)
    client.post(f"/api/fde-scope/handoff/{eid}/runbook")

    r = client.post(f"/api/fde-scope/handoff/{eid}", data={"accept": "true"})
    assert r.status_code == 200, r.text
    assert r.json()


def test_pawapp_agent_tools(tmp_path: Path, monkeypatch) -> None:
    """The three host-agent tools must answer without a model or a sandbox."""
    import asyncio

    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)

    status = asyncio.run(main.fde_sop_status(eid))
    assert status["engagement_id"] == eid

    # two ungated transitions, then the success_criteria gate blocks.
    assert asyncio.run(main.fde_sop_advance(eid))["advanced"] is True
    assert asyncio.run(main.fde_sop_advance(eid))["advanced"] is True
    adv = asyncio.run(main.fde_sop_advance(eid))
    assert adv["advanced"] is False and adv["blockers"]

    forced = asyncio.run(main.fde_sop_advance(eid, force=True))
    assert forced["advanced"] is True

    bad_sources = asyncio.run(main.fde_deploy_plan("t", sources_json='["a"]'))
    assert "must be" in bad_sources["error"]


def test_pawapp_on_launch_is_callable(tmp_path: Path, monkeypatch) -> None:
    import asyncio

    main, _ = _ready(tmp_path, monkeypatch)
    asyncio.run(main._on_launch())
    assert main.plugin is main.app


def test_pawapp_load_reports_a_missing_engine(monkeypatch) -> None:
    """The env guard: a host that cannot import fde_scope gets a clear message."""
    import builtins

    real_import = builtins.__import__

    def _import(name, *args, **kwargs):
        if name == "fde_scope" or name.startswith("fde_scope."):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    qp = types.ModuleType("qwenpaw")
    qp_pawapp = types.ModuleType("qwenpaw.pawapp")
    qp_pawapp.PawApp = type("PawApp", (), {"__init__": lambda self, **kw: None})
    qp_pawapp.get_ctx = lambda: None
    qp.pawapp = qp_pawapp
    monkeypatch.setitem(sys.modules, "qwenpaw", qp)
    monkeypatch.setitem(sys.modules, "qwenpaw.pawapp", qp_pawapp)
    monkeypatch.setattr(builtins, "__import__", _import)
    monkeypatch.delitem(sys.modules, "fde_scope", raising=False)
    for name in [n for n in sys.modules if n.startswith("fde_scope.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)

    sys.path.insert(0, str(_PAWAPP_BACKEND))
    try:
        sys.modules.pop("main", None)
        with pytest.raises(ModuleNotFoundError, match="not importable"):
            importlib.import_module("main")
    finally:
        sys.path.remove(str(_PAWAPP_BACKEND))


# ---------------------------------------------------------------------------
# Edge branches: corrupt state, oversized input, host faults, terminal phase
# ---------------------------------------------------------------------------
def test_pawapp_skips_a_corrupt_engagement_file(tmp_path: Path, monkeypatch) -> None:
    """A half-written record must not take the whole list view down."""
    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)
    (tmp_path / ".fde_scope" / "engagements" / "broken.json").write_text("{not json", encoding="utf-8")

    listed = client.get("/api/fde-scope/engagements")
    assert listed.status_code == 200, listed.text
    assert [e["engagement_id"] for e in listed.json()] == [eid]


def test_pawapp_kpi_rejects_oversized_upload(tmp_path: Path, monkeypatch) -> None:
    main, client = _ready(tmp_path, monkeypatch)
    r = client.post(
        "/api/fde-scope/kpi",
        data={"profile": "manufacturing"},
        files={"file": ("k.jsonl", b"x" * (main.MAX_UPLOAD_BYTES + 10), "application/json")},
    )
    assert r.status_code == 413


def test_pawapp_publish_rejects_an_invalid_transition(tmp_path: Path, monkeypatch) -> None:
    """Publishing an already-archived skill is a 400, not a crash."""
    from fde_scope import paths
    from fde_scope.skills.models import SkillCategory, SkillDraft
    from fde_scope.skills.service import SkillService
    from fde_scope.skills.store import SkillStore

    main, client = _ready(tmp_path, monkeypatch)
    svc = SkillService(SkillStore(paths.skills_dir()))
    rec = svc.create(SkillDraft(title="归档后发布", category=SkillCategory.METHODOLOGY, body_md="x"))
    svc.archive(rec.id)
    assert client.post(f"/api/fde-scope/skills/{rec.id}/publish").status_code == 400


def test_pawapp_runbook_falls_back_when_the_host_raises(tmp_path: Path, monkeypatch) -> None:
    """An unavailable host model degrades to the template — never a 500."""
    import asyncio

    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)

    class _BrokenCtx:
        async def chat(self, _prompt: str):
            raise RuntimeError("host model unavailable")

    out = asyncio.run(main.draft_runbook(eid, ctx=_BrokenCtx()))
    assert out["used_llm"] is False
    assert Path(out["path"]).read_text(encoding="utf-8").strip()


def test_pawapp_runbook_falls_back_on_empty_host_reply(tmp_path: Path, monkeypatch) -> None:
    import asyncio

    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)

    class _Empty:
        text = "   "

    class _Ctx:
        async def chat(self, _prompt: str):
            return _Empty()

    out = asyncio.run(main.draft_runbook(eid, ctx=_Ctx()))
    assert out["used_llm"] is False


def test_pawapp_sop_advance_tool_reports_completion(tmp_path: Path, monkeypatch) -> None:
    """The terminal transition answers ``complete`` instead of raising."""
    import asyncio

    main, client = _ready(tmp_path, monkeypatch)
    eid = _new_engagement(client)
    for _ in range(40):
        out = asyncio.run(main.fde_sop_advance(eid, force=True))
        if out.get("reason") == "complete":
            break
    assert out.get("reason") == "complete"

"""Smoke tests for the QwenPaw PawApp plugin (pawapp/backend/main.py).

``qwenpaw`` is not a dependency of fde-scope, so the PawApp SDK is stubbed
with a no-op implementation; the routes are exercised through a plain FastAPI
app. This keeps the plugin regression-checked without QwenPaw installed.
"""

from __future__ import annotations

import importlib
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
            "tenant": "faw",
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
        main.fde_deploy_plan("guming", "数据分析,文件分析", '{"documents": "docs/"}'),
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

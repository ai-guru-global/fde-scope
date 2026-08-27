#!/usr/bin/env python3
"""Verify the FDE Scope PawApp against the REAL QwenPaw host pipeline.

Solidifies the manual real-host verification (2026-08-26): load ``pawapp/``
through QwenPaw's actual ``PluginLoader`` (manifest parse → backend module →
``PawApp.register(PluginApi)`` → HTTP mount at ``/api/fde-scope``), then smoke
every route over the mounted FastAPI app.

Requirements: ``pip install qwenpaw`` (the host runtime; no model / API key /
workspace configuration needed — the PawApp's defensive fallbacks cover the
missing workspace). Exits 0 on success, non-zero on any failure.

Local run:  python scripts/verify_pawapp_host.py
CI:         see the ``pawapp-host`` job in .github/workflows/ci.yml
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "pawapp"

# The plugin backend imports fde_scope; make the repo importable regardless of
# install mode (editable .pth may not apply after the loader copies files).
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


async def main() -> int:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from qwenpaw.plugins.loader import PluginLoader

    # Isolate engagement/skills/reports writes from the repo working dir.
    workdir = Path(tempfile.mkdtemp(prefix="fde-pawapp-verify-"))
    import os

    os.chdir(workdir)

    install_dir = workdir / "plugins"
    install_dir.mkdir()
    host_app = FastAPI()
    loader = PluginLoader([install_dir])
    # Host startup order: the FastAPI app is attached before plugins load.
    loader.registry.set_plugin_http_app(host_app)

    rec = await loader.load_plugin_from_path(PLUGIN_DIR)
    assert rec.manifest.id == "fde-scope", f"unexpected plugin id: {rec.manifest.id}"

    client = TestClient(host_app)

    # -- read routes ---------------------------------------------------------
    for path in (
        "/api/fde-scope/health",
        "/api/fde-scope/profiles",
        "/api/fde-scope/engagements",
        "/api/fde-scope/phases?profile=ticket",
        "/api/fde-scope/skills",
        "/api/fde-scope/skills/drafts",
    ):
        r = client.get(path)
        assert r.status_code == 200, f"GET {path} -> {r.status_code}: {r.text[:200]}"
    assert client.get("/api/fde-scope/health").json()["app"] == "fde-scope"

    # -- SOP lifecycle: create → gates → advance → handoff -------------------
    r = client.post("/api/fde-scope/engagements", data={"customer": "CIHost", "profile": "ticket"})
    assert r.status_code == 200, r.text[:300]
    eid = r.json()["engagement_id"]

    g = client.get(f"/api/fde-scope/engagements/{eid}/gates")
    assert g.status_code == 200 and "success_criteria" in g.json(), g.text[:300]

    a = client.post(f"/api/fde-scope/engagements/{eid}/advance")
    assert a.status_code == 200, a.text[:300]

    # runbook route: no workspace → ctx.chat fails → honest template fallback
    rb = client.post(f"/api/fde-scope/handoff/{eid}/runbook")
    assert rb.status_code == 200 and rb.json()["used_llm"] is False, rb.text[:300]

    h = client.post(f"/api/fde-scope/handoff/{eid}", data={"accept": "false"})
    assert h.status_code == 200, h.text[:300]

    # deploy plan: shares fde_scope.deploy.build_deploy_plan with the CLI/console
    dp = client.post(
        "/api/fde-scope/deploy/plan",
        json={
            "tenant": "cihost",
            "sources": {"csv": "data/t.csv"},
            "agents": [{"name": "analyst", "role": "数据分析"}],
        },
    )
    assert dp.status_code == 200, dp.text[:300]
    assert "csv_schema" in dp.json()["summary"]["bound_tools"], dp.text[:300]
    assert client.post("/api/fde-scope/deploy/plan", json={"agents": [{"role": "x"}]}).status_code == 422

    print(f"pawapp host verification OK: {rec.manifest.id} loaded, all routes 200")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

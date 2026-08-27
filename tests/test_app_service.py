"""Offline smoke test for the opt-in AgentScope app service (deploy/app_service).

``build_app`` assembles a real ``agentscope.app`` FastAPI service with
zero-config backends. Constructing it must not open a socket, start Docker or
call a model, so this runs offline whenever the extra is installed and skips
otherwise (mirroring the CI core matrix that doesn't install agentscope).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fde_scope.config import TenantConfig


@pytest.mark.agentscope
def test_build_app_returns_real_fastapi_offline(tmp_path: Path) -> None:
    from fde_scope.deploy import build_app

    tenant = TenantConfig(
        id="acme",
        name="Acme",
        agents=[
            {"name": "data", "role": "数据分析"},
            {"name": "files", "role": "文件分析"},
        ],
    )
    app = build_app(tenant, basedir=str(tmp_path / "ws"))

    fastapi = pytest.importorskip("fastapi")
    assert isinstance(app, fastapi.FastAPI)
    assert len(app.routes) > 0
    # workspace dir is prepared for the local manager
    assert (tmp_path / "ws").is_dir()


@pytest.mark.agentscope
def test_default_knowledge_parsers_cover_documents() -> None:
    from fde_scope.deploy.app_service import default_knowledge_parsers

    parsers = default_knowledge_parsers()
    exts: set[str] = set()
    for p in parsers:
        exts.update(e.lower() for e in p.supported_extensions())

    # documents connector's text reach must be representable in the app's RAG
    assert {".txt", ".pdf"} <= exts


def test_build_app_export_is_lazy() -> None:
    """``build_app`` is importable without agentscope; only calling it needs it."""
    from fde_scope.deploy import build_app

    assert callable(build_app)

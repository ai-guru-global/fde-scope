"""Opt-in AgentScope app service — the runtime step behind ``deploy --serve``.

This is what sits *beyond* assembly. ``build_app`` returns a real
``agentscope.app`` FastAPI service, assembled with zero-configuration backends
and fed with FDE Scope's own multi-agent blueprints and document parsers:

    storage           RedisStorage (params only; connects on startup)
    message_bus       InMemoryMessageBus  (no broker needed to build)
    workspace_manager LocalWorkspaceManager (no Docker needed to build)
    subagents         our ``SubAgentTemplate`` blueprint list
    knowledge_parsers the AgentScope rag parsers backing the documents connector

Constructing the app needs no running Redis, no Docker and no model — the
connection is only opened when the service starts — so it is fully unit-testable
offline. *Serving* it (``fde-scope deploy --serve``) is the operator's explicit
choice and does require Redis + a reachable model at run time.

Every AgentScope import is lazy, so the zero-config core is untouched by this
module being present.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fde_scope.config import AgentSpec, TenantConfig

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import FastAPI

    from .tenant_manager import TenantDeployer


def default_knowledge_parsers() -> list[Any]:
    """The AgentScope rag parsers, matched to the documents connector's reach.

    Returned as instances so ``create_app`` can ingest on-site PDFs / Word /
    Excel / Markdown straight into the tenant knowledge base.
    """
    from agentscope.rag import ExcelParser, PDFParser, PPTParser, TextParser, WordParser

    return [TextParser(), PDFParser(), WordParser(), ExcelParser(), PPTParser()]


def _resolve_specs(tenant: TenantConfig) -> list[AgentSpec]:
    """Mirror ``TenantDeployer.deploy``'s default single-agent behaviour."""
    return tenant.agents or [AgentSpec(name=f"{tenant.name}_agent", role=tenant.name)]


def build_app(
    tenant: TenantConfig,
    deployer: TenantDeployer | None = None,
    *,
    basedir: str | None = None,
    redis_host: str = "localhost",
    redis_port: int = 6379,
) -> FastAPI:
    """Assemble a real, runnable AgentScope app for ``tenant``.

    Offline-constructible: no Redis server, Docker or model is contacted until
    the returned app is served. Raises if the ``agentscope`` extra is absent
    (this is the opt-in runtime path, not the core path).
    """
    from agentscope.app import create_app
    from agentscope.app.message_bus import InMemoryMessageBus
    from agentscope.app.storage import RedisStorage
    from agentscope.app.workspace_manager import LocalWorkspaceManager

    from .tenant_manager import TenantDeployer

    deployer = deployer or TenantDeployer(agentscope_extra=True)
    specs = _resolve_specs(tenant)
    templates = deployer.build_subagent_templates(tenant, specs)

    workdir = Path(basedir or f".fde_scope/workspaces/fde_{tenant.id}")
    workdir.mkdir(parents=True, exist_ok=True)

    return create_app(
        storage=RedisStorage(host=redis_host, port=redis_port),
        message_bus=InMemoryMessageBus(),
        workspace_manager=LocalWorkspaceManager(basedir=str(workdir)),
        knowledge_parsers=default_knowledge_parsers(),
        custom_subagent_templates=templates,
        title=f"FDE Scope · {tenant.name}",
    )

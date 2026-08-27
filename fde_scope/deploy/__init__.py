"""Layer 3 — multi-tenant deployment engine.

Assembles (and, with the optional agentscope extra, starts) an isolated
tenant agent: Docker/E2B/K8s workspace for execution isolation, a per-tenant
corpus collection for data isolation, and a ``PermissionContext`` for capability
isolation. Role agents get a real ``agentscope.tool.Toolkit`` bound to the
tenant's own connectors (see :mod:`fde_scope.deploy.toolkit` / :mod:`.roles`).
All AgentScope imports are lazy so this layer never breaks the zero-config core.
"""

from .app_service import build_app
from .permission_builder import PermissionBlueprint, build_context, build_engine, default_blueprint
from .roles import canonical_role, connectors_for_role
from .sandbox_config import SandboxSpec, build_workspace
from .tenant_manager import DeployedAgent, TenantDeployer, build_deploy_plan, summarize_deploy_plan
from .toolkit import ToolBinding, build_toolkit, describe_bindings, plan_bindings

__all__ = [
    "TenantDeployer",
    "DeployedAgent",
    "build_deploy_plan",
    "summarize_deploy_plan",
    "SandboxSpec",
    "build_workspace",
    "PermissionBlueprint",
    "build_context",
    "build_engine",
    "default_blueprint",
    "ToolBinding",
    "build_toolkit",
    "describe_bindings",
    "plan_bindings",
    "canonical_role",
    "connectors_for_role",
    "build_app",
]

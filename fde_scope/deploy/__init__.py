"""Layer 3 — multi-tenant deployment engine.

Assembles (and, with the optional agentscope extra, starts) an isolated
tenant agent: Docker/E2B/K8s workspace for execution isolation, a per-tenant
corpus collection for data isolation, and a ``PermissionEngine`` for
capability isolation. All AgentScope imports are lazy so this layer never
breaks the zero-config core.
"""

from .permission_builder import PermissionBlueprint, build_engine, default_blueprint
from .sandbox_config import SandboxSpec, build_workspace
from .tenant_manager import DeployedAgent, TenantDeployer

__all__ = [
    "TenantDeployer",
    "DeployedAgent",
    "SandboxSpec",
    "build_workspace",
    "PermissionBlueprint",
    "build_engine",
    "default_blueprint",
]

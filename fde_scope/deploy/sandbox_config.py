"""Sandbox / workspace configuration for a deployed tenant agent.

AgentScope 2.0 API reality check (see docs/agentscope_api_mapping.md):
  - The unified workspace base is ``agentscope.workspace.WorkspaceBase``.
  - Concrete backends include ``DockerWorkspace``, ``E2BWorkspace``,
    ``K8sWorkspace``, ``DaytonaWorkspace`` and more.
  - There is **no** ``SandboxConfig`` class and **no** ``resource_limit``
    kwarg in 2.0 (the design doc's ``Workspace(sandbox=SandboxConfig(
    resource_limit=...))`` does not compile). Resource caps are delegated to
    the container runtime / backend constructor.

This module captures the *FDE-side* tenant sandbox spec (what the FDE wants)
and translates it to the real ``DockerWorkspace`` constructor arguments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SandboxSpec:
    """The FDE's intent for a tenant sandbox (framework-neutral)."""

    tenant_id: str
    backend: str = "docker"  # docker | e2b | k8s | local
    base_image: str = "fde-scope-agent:latest"
    resource_quota: str = "2cpu-4gb"  # advisory; honored by backend if able
    extra_pip: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    instructions: str = ""

    def as_docker_kwargs(self) -> dict[str, Any]:
        """Translate the spec into ``DockerWorkspace`` constructor kwargs.

        Only kwargs that actually exist on the 2.0 ``DockerWorkspace`` are
        emitted. ``resource_quota`` is NOT forwarded (no such param exists);
        it's recorded in the spec for the FDE's own bookkeeping and applied
        at the container-runtime level when a backend supports it.
        """
        return {
            "workspace_id": f"fde_{self.tenant_id}",
            "base_image": self.base_image,
            "extra_pip": list(self.extra_pip),
            "env": dict(self.env),
            "instructions": self.instructions,
        }

    @classmethod
    def from_quota_string(cls, tenant_id: str, quota: str = "2cpu-4gb") -> SandboxSpec:
        """Parse an advisory ``"Ncpu-Mgb"`` quota into a spec (cosmetic only)."""
        spec = cls(tenant_id=tenant_id, resource_quota=quota)
        return spec


def build_workspace(spec: SandboxSpec):
    """Construct a real AgentScope workspace for the spec.

    Lazy-imports agentscope so the core layer never needs it. Raises a clear
    error if the optional extra isn't installed.
    """
    try:
        from agentscope.workspace import DockerWorkspace, LocalWorkspace
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Tenant deployment needs the optional 'agentscope' extra: pip install 'fde-scope[agentscope]'"
        ) from exc

    if spec.backend == "docker":
        return DockerWorkspace(**spec.as_docker_kwargs())
    if spec.backend == "local":
        return LocalWorkspace(workspace_id=f"fde_{spec.tenant_id}")
    raise ValueError(f"Unsupported backend for build_workspace: {spec.backend!r}")

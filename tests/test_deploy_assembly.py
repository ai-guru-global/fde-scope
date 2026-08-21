"""Tests for the deploy layer's real (non-dry-run) assembly path.

The heavy AgentScope / Docker objects are replaced with fakes so the
``build_workspace`` → ``build_engine`` → ``_assemble_agent`` path is exercised
without the optional ``agentscope`` extra installed — including the exact
kwargs ``_assemble_agent`` passes to ``agentscope.agent.Agent``.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from fde_scope.config import TenantConfig
from fde_scope.deploy import tenant_manager
from fde_scope.deploy.sandbox_config import SandboxSpec
from fde_scope.deploy.tenant_manager import TenantDeployer


class FakeReActConfig:
    """Stands in for ``agentscope.agent.ReActConfig``."""

    def __init__(self, max_iters: int = 20) -> None:
        self.max_iters = max_iters


class FakeAgent:
    """Stands in for ``agentscope.agent.Agent`` — records constructor kwargs."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


@pytest.fixture
def fake_agentscope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a fake ``agentscope.agent`` module for the lazy import."""
    module = types.ModuleType("agentscope.agent")
    module.Agent = FakeAgent  # type: ignore[attr-defined]
    module.ReActConfig = FakeReActConfig  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agentscope.agent", module)


def test_sandbox_spec_docker_kwargs_match_real_api() -> None:
    """The kwargs we emit must be accepted by the real DockerWorkspace."""
    spec = SandboxSpec(tenant_id="acme", backend="docker", base_image="python:3.12-slim")
    kwargs = spec.as_docker_kwargs()
    # Spot-check the keys the real constructor expects (2.0.5 DockerWorkspace).
    for required in ("workspace_id", "base_image"):
        assert required in kwargs


def test_deployer_assembles_real_path(fake_agentscope: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-dry-run deploy must reach workspace/engine/agent assembly."""
    calls: list[str] = []

    def fake_build_workspace(spec: SandboxSpec) -> tuple[str, str]:
        calls.append("workspace")
        return ("workspace", spec.tenant_id)

    def fake_build_engine(blueprint: Any) -> tuple[str, str]:
        calls.append("engine")
        return ("engine", blueprint.tenant_id)

    monkeypatch.setattr(tenant_manager, "build_workspace", fake_build_workspace)
    monkeypatch.setattr(tenant_manager, "build_engine", fake_build_engine)

    deployer = TenantDeployer(agentscope_extra=True)
    tenant = TenantConfig(id="acme", name="Acme", model="qwen-max")
    deployed = deployer.deploy(tenant)  # not dry_run → real assembly path

    assert calls == ["workspace", "engine"]
    assert deployed.is_assembled is True
    assert deployed.manifest["started"] is True
    assert deployed.workspace == ("workspace", "acme")
    assert deployed.engine == ("engine", "acme")

    # _assemble_agent's faithful translation of the design-doc block.
    agent = deployed.agent
    assert isinstance(agent, FakeAgent)
    assert agent.kwargs["name"] == "Acme_agent"
    assert agent.kwargs["model"] is None  # wired from tenant.model at runtime
    assert "Acme" in agent.kwargs["system_prompt"]
    assert agent.kwargs["toolkit"] == {
        "corpus_collection": "corpus_acme",
        "ticket_api": None,
    }
    react = agent.kwargs["react_config"]
    assert isinstance(react, FakeReActConfig)
    assert react.max_iters == 20


def test_dry_run_skips_assembly(monkeypatch: pytest.MonkeyPatch) -> None:
    """dry_run must not touch build_workspace/build_engine/_assemble_agent."""

    def _forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("assembly must not run in dry-run mode")

    monkeypatch.setattr(tenant_manager, "build_workspace", _forbidden)
    monkeypatch.setattr(tenant_manager, "build_engine", _forbidden)

    deployer = TenantDeployer(agentscope_extra=True)
    tenant = TenantConfig(id="acme", name="Acme")
    deployed = deployer.deploy(tenant, dry_run=True)
    assert deployed.is_assembled is False
    assert deployed.manifest["started"] is False

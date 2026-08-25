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


def test_deployer_assembles_real_path(fake_agentscope: None, fake_agentscope_app: None, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_deployer_assembles_multi_agent_topology(
    fake_agentscope: None, fake_agentscope_app: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """每个 AgentSpec 组装一个 Agent；model 从 spec wiring；manifest 带 agents 段。"""
    monkeypatch.setattr(tenant_manager, "build_workspace", lambda spec: ("workspace", spec.tenant_id))
    monkeypatch.setattr(tenant_manager, "build_engine", lambda bp: ("engine", bp.tenant_id))
    deployer = TenantDeployer(agentscope_extra=True)
    tenant = TenantConfig(
        id="acme",
        name="Acme",
        agents=[
            {"name": "researcher", "role": "调研员"},
            {"name": "coder", "role": "实施员", "model": "qwen-max", "system_prompt": "You code."},
        ],
    )
    deployed = deployer.deploy(tenant)
    assert len(deployed.agents) == 2
    assert deployed.agent is deployed.agents[0]  # 单 Agent 兼容
    assert deployed.agents[0].kwargs["name"] == "researcher"
    assert deployed.agents[0].kwargs["model"] is None  # spec.model 缺失 → 运行时注入
    assert "调研员" in deployed.agents[0].kwargs["system_prompt"]
    assert deployed.agents[1].kwargs["model"] == "qwen-max"
    assert deployed.agents[1].kwargs["system_prompt"] == "You code."
    # manifest agents 段（dry-run 与 real 都有）
    agents = deployed.manifest["agents"]
    assert [a["name"] for a in agents] == ["researcher", "coder"]
    assert agents[1]["model"] == "qwen-max"
    assert agents[0]["toolkit"] == ["corpus_collection", "ticket_api"]


def test_deployer_default_single_agent_manifest(fake_agentscope: None, fake_agentscope_app: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """agents 缺省时沿用现有单 Agent 行为（name = {tenant.name}_agent）。"""
    monkeypatch.setattr(tenant_manager, "build_workspace", lambda spec: ("w", spec.tenant_id))
    monkeypatch.setattr(tenant_manager, "build_engine", lambda bp: ("e", bp.tenant_id))
    deployer = TenantDeployer(agentscope_extra=True)
    deployed = deployer.deploy(TenantConfig(id="acme", name="Acme"))
    assert len(deployed.agents) == 1
    assert deployed.agents[0].kwargs["name"] == "Acme_agent"
    assert deployed.manifest["agents"][0]["name"] == "Acme_agent"


def test_dry_run_manifest_has_agents_section() -> None:
    """dry-run 也携带 agents 拓扑声明（计划可校验）。"""
    deployer = TenantDeployer(agentscope_extra=False)
    deployed = deployer.deploy(
        TenantConfig(id="acme", name="Acme", agents=[{"name": "r", "role": "调研"}]),
        dry_run=True,
    )
    agents = deployed.manifest["agents"]
    assert len(agents) == 1
    assert agents[0]["name"] == "r"
    assert agents[0]["role"] == "调研"
    assert agents[0]["model"] is None  # None → wired by the runtime
    assert agents[0]["toolkit"] == ["corpus_collection", "ticket_api"]
    # 默认 system_prompt 由 _build_prompt 生成（含 role），截 120 字符
    assert "调研" in agents[0]["system_prompt"]
    assert len(agents[0]["system_prompt"]) <= 120


class FakeSubAgentTemplate:
    """Stands in for ``agentscope.app.SubAgentTemplate`` (a Pydantic blueprint)."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.type = kwargs["type"]
        self.description = kwargs["description"]


@pytest.fixture
def fake_agentscope_app(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("agentscope.app")
    module.SubAgentTemplate = FakeSubAgentTemplate  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agentscope.app", module)


def test_build_subagent_templates_uses_2_0_blueprints(
    fake_agentscope_app: None, fake_agentscope: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """每个 AgentSpec → 一个 SubAgentTemplate（type 路由键 + 占位符模板串）。"""
    monkeypatch.setattr(tenant_manager, "build_workspace", lambda spec: ("w", spec.tenant_id))
    monkeypatch.setattr(tenant_manager, "build_engine", lambda bp: ("e", bp.tenant_id))
    deployer = TenantDeployer(agentscope_extra=True)
    tenant = TenantConfig(
        id="acme",
        name="Acme",
        agents=[
            {"name": "researcher", "role": "调研员"},
            {"name": "coder", "role": "实施员", "system_prompt": "You are {member_name}."},
        ],
    )
    deployed = deployer.deploy(tenant)
    templates = deployed.subagent_templates
    assert len(templates) == 2
    assert templates[0].kwargs["type"] == "researcher"
    assert templates[0].kwargs["description"] == "调研员"
    # 默认模板串必须含 2.0 占位符（{member_name} 等）
    assert "{member_name}" in templates[0].kwargs["system_prompt_template"]
    assert templates[1].kwargs["system_prompt_template"] == "You are {member_name}."
    assert deployed.manifest["subagent_templates"] == [
        {"type": "researcher", "description": "调研员"},
        {"type": "coder", "description": "实施员"},
    ]

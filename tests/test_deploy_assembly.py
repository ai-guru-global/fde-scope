"""Tests for the deploy layer's real (non-dry-run) assembly path.

The heavy AgentScope / Docker objects are replaced with fakes so the
``build_workspace`` → ``build_context`` → ``build_toolkit`` → ``_assemble_agent``
path is exercised without the optional ``agentscope`` extra installed —
including the exact kwargs ``_assemble_agent`` passes to ``agentscope.agent.Agent``.

The three things these tests exist to pin down are the 2.0 wiring contracts that
silently break an agent when wrong: ``toolkit=`` must be the object
``build_toolkit`` returns (not a dict), and ``state=`` must carry the permission
context (a detached engine is never enforced).
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from pydantic import ValidationError

from fde_scope.config import TenantConfig
from fde_scope.deploy import tenant_manager
from fde_scope.deploy.sandbox_config import SandboxSpec
from fde_scope.deploy.tenant_manager import TenantDeployer, build_deploy_plan, summarize_deploy_plan
from fde_scope.deploy.toolkit import ToolBinding


class FakeReActConfig:
    """Stands in for ``agentscope.agent.ReActConfig``."""

    def __init__(self, max_iters: int = 20) -> None:
        self.max_iters = max_iters


class FakeAgent:
    """Stands in for ``agentscope.agent.Agent`` — records constructor kwargs."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakeChatModel:
    """Stands in for ``agentscope.model.OllamaChatModel``."""

    def __init__(self, model: str = "", **kwargs: Any) -> None:
        self.model = model


class FakeAgentState:
    """Stands in for ``agentscope.state.AgentState`` — records constructor kwargs."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


@pytest.fixture
def fake_agentscope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject fake ``agentscope.agent`` / ``.model`` / ``.state`` modules for the lazy imports."""
    module = types.ModuleType("agentscope.agent")
    module.Agent = FakeAgent  # type: ignore[attr-defined]
    module.ReActConfig = FakeReActConfig  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agentscope.agent", module)
    model_mod = types.ModuleType("agentscope.model")
    model_mod.OllamaChatModel = FakeChatModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agentscope.model", model_mod)
    state_mod = types.ModuleType("agentscope.state")
    state_mod.AgentState = FakeAgentState  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agentscope.state", state_mod)


@pytest.fixture
def fake_assembly(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stub the three real-object factories; return the ordered list of calls."""
    calls: list[str] = []

    def fake_build_workspace(spec: SandboxSpec) -> tuple[str, str]:
        calls.append("workspace")
        return ("workspace", spec.tenant_id)

    def fake_build_context(blueprint: Any, mode: str = "conservative") -> tuple[str, str]:
        calls.append("permission")
        return ("permission", blueprint.tenant_id)

    def fake_build_toolkit(
        bindings: list[ToolBinding], corpus_report: Any = None, skills_dirs: list[str] | None = None
    ) -> tuple:
        calls.append("toolkit")
        return ("toolkit", tuple(b.name for b in bindings if b.bound), tuple(skills_dirs or []))

    monkeypatch.setattr(tenant_manager, "build_workspace", fake_build_workspace)
    monkeypatch.setattr(tenant_manager, "build_context", fake_build_context)
    monkeypatch.setattr(tenant_manager, "build_toolkit", fake_build_toolkit)
    return calls


def test_sandbox_spec_docker_kwargs_match_real_api() -> None:
    """The kwargs we emit must be accepted by the real DockerWorkspace."""
    spec = SandboxSpec(tenant_id="acme", backend="docker", base_image="python:3.12-slim")
    kwargs = spec.as_docker_kwargs()
    # Spot-check the keys the real constructor expects (2.0.x DockerWorkspace).
    for required in ("workspace_id", "base_image"):
        assert required in kwargs


def test_deployer_assembles_real_path(
    fake_agentscope: None, fake_agentscope_app: None, fake_assembly: list[str]
) -> None:
    """Non-dry-run deploy must reach workspace/permission/toolkit/agent assembly."""
    deployer = TenantDeployer(agentscope_extra=True)
    tenant = TenantConfig(id="acme", name="Acme", model="qwen-max")
    deployed = deployer.deploy(tenant)  # not dry_run → real assembly path

    assert fake_assembly == ["workspace", "permission", "toolkit"]
    assert deployed.is_assembled is True
    assert deployed.manifest["started"] is True
    assert deployed.workspace == ("workspace", "acme")
    assert deployed.engine == ("permission", "acme")

    # _assemble_agent's faithful translation of the design-doc block.
    agent = deployed.agent
    assert isinstance(agent, FakeAgent)
    assert agent.kwargs["name"] == "Acme_agent"
    assert agent.kwargs["model"].model == "qwen-max"  # spec.model 缺省 → tenant.model
    assert "Acme" in agent.kwargs["system_prompt"]
    # The toolkit is whatever build_toolkit returned — never a plain dict,
    # because Agent does not validate the argument and a dict means zero tools.
    assert agent.kwargs["toolkit"][0] == "toolkit"
    assert agent.kwargs["toolkit"][1] == ()  # no corpus, unrecognized role → nothing bound
    assert agent.kwargs["toolkit"][2] == ()  # no skills_dir declared → no skills wired
    # Permissions reach the agent through its state, not a detached engine.
    assert agent.kwargs["state"].kwargs["permission_context"] == ("permission", "acme")
    react = agent.kwargs["react_config"]
    assert isinstance(react, FakeReActConfig)
    assert react.max_iters == 20


def test_dry_run_skips_assembly(monkeypatch: pytest.MonkeyPatch) -> None:
    """dry_run must not touch build_workspace/build_context/build_toolkit/_assemble_agent."""

    def _forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("assembly must not run in dry-run mode")

    monkeypatch.setattr(tenant_manager, "build_workspace", _forbidden)
    monkeypatch.setattr(tenant_manager, "build_context", _forbidden)
    monkeypatch.setattr(tenant_manager, "build_toolkit", _forbidden)

    deployer = TenantDeployer(agentscope_extra=True)
    tenant = TenantConfig(id="acme", name="Acme")
    deployed = deployer.deploy(tenant, dry_run=True)
    assert deployed.is_assembled is False
    assert deployed.manifest["started"] is False


def test_deployer_assembles_multi_agent_topology(
    fake_agentscope: None, fake_agentscope_app: None, fake_assembly: list[str]
) -> None:
    """每个 AgentSpec 组装一个 Agent；model 从 spec wiring；manifest 带 agents 段。"""
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
    assert deployed.agents[0].kwargs["model"].model == "qwen-max"  # spec.model 缺失 → tenant.model
    assert "调研员" in deployed.agents[0].kwargs["system_prompt"]
    assert deployed.agents[1].kwargs["model"].model == "qwen-max"
    assert deployed.agents[1].kwargs["system_prompt"] == "You code."
    # manifest agents 段（dry-run 与 real 都有）
    agents = deployed.manifest["agents"]
    assert [a["name"] for a in agents] == ["researcher", "coder"]
    assert agents[1]["model"] == "qwen-max"
    assert agents[0]["connectors"] == []  # "调研员" names no data source
    assert agents[0]["role_bucket"] is None
    assert agents[0]["bound"] == [] and agents[0]["unbound"] == []


def test_deployer_default_single_agent_manifest(
    fake_agentscope: None, fake_agentscope_app: None, fake_assembly: list[str]
) -> None:
    """agents 缺省时沿用现有单 Agent 行为（name = {tenant.name}_agent）。"""
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
    assert agents[0]["connectors"] == []
    assert agents[0]["tools"] == []  # no corpus, no bound sources → no capabilities
    # 默认 system_prompt 由 _build_prompt 生成（含 role），截 120 字符
    assert "调研" in agents[0]["system_prompt"]
    assert len(agents[0]["system_prompt"]) <= 120


class FakeClosable:
    def __init__(self, name: str) -> None:
        self.name = name
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_stop_closes_handles_and_flags_manifest(
    fake_agentscope: None, fake_agentscope_app: None, fake_assembly: list[str]
) -> None:
    """2.0 没有 Agent.stop——stop 关闭可关闭句柄并标记 manifest。"""
    deployer = TenantDeployer(agentscope_extra=True)
    deployed = deployer.deploy(TenantConfig(id="acme", name="Acme"))
    ws, engine = FakeClosable("ws"), FakeClosable("engine")
    deployed.workspace, deployed.engine = ws, engine
    report = deployer.stop(deployed)
    assert ws.closed is True and engine.closed is True
    assert report["closed"] == ["workspace", "engine"]
    assert deployed.manifest["started"] is False


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
    fake_agentscope_app: None, fake_agentscope: None, fake_assembly: list[str]
) -> None:
    """每个 AgentSpec → 一个 SubAgentTemplate（type 路由键 + 占位符模板串）。"""
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


# ---------------------------------------------------------------------------
# build_deploy_plan — the payload-shaped plan shared by web console + PawApp
# ---------------------------------------------------------------------------
def test_build_deploy_plan_binds_configured_sources() -> None:
    plan = build_deploy_plan(
        {
            "tenant": "caocao",
            "sources": {"csv": "data/t.csv", "documents": "docs/"},
            "agents": [{"name": "analyst", "role": "数据分析"}, {"name": "archivist", "role": "文件分析"}],
        }
    )
    assert plan["summary"]["agents"] == 2
    assert plan["summary"]["bound_tools"] == [
        "csv_sample",
        "csv_schema",
        "documents_sample",
        "documents_schema",
    ]
    # mysql belongs to the data role but nobody told it where the database is.
    assert plan["summary"]["unbound_tools"] == ["mes_sample", "mes_schema", "mysql_sample", "mysql_schema"]
    assert plan["manifest"]["tenant_id"] == "caocao"


def test_build_deploy_plan_is_always_a_plan_never_a_runtime() -> None:
    """A plan must not assemble anything, even with the extra installed."""
    plan = build_deploy_plan({"tenant": "acme"})
    assert plan["manifest"]["started"] is False
    assert "subagent_templates" not in plan["manifest"]
    # Nameless tenant defaults to its id, so the agent name stays predictable.
    assert plan["manifest"]["agents"][0]["name"] == "acme_agent"


def test_build_deploy_plan_carries_approval_mode() -> None:
    """The approval policy shown in the plan is the one the deployer will enforce."""
    plan = build_deploy_plan({"tenant": "acme", "approval_mode": "autonomous"})
    assert plan["manifest"]["approval_policy"]["mode"] == "autonomous"


def test_build_deploy_plan_rejects_bad_payload() -> None:
    with pytest.raises(ValidationError):
        build_deploy_plan({"tenant": "acme", "agents": [{"role": "缺名字"}]})


def test_summarize_deploy_plan_names_what_is_still_missing() -> None:
    plan = build_deploy_plan({"tenant": "acme", "agents": [{"name": "logs", "role": "日志分析"}]})
    text = summarize_deploy_plan(plan)
    assert "logs [logs]" in text
    assert "TODO " in text and "unbound" in text
    assert "8 waiting for a source" in text  # historian/mqtt/ros2/opcua × schema+sample

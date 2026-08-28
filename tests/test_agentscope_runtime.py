"""Runtime tests against the *real* AgentScope 2.0 library.

Everything else in the suite fakes AgentScope, which is exactly why the fake
could never catch the bugs these tests pin down: a dict passed as ``toolkit=``
constructs fine, and a detached ``PermissionEngine`` looks configured. These
tests import the actual package (``[project.optional-dependencies].agentscope``)
and exercise the objects ``deploy`` claims to build — offline, with no model,
no Redis and no Docker, because none of them are touched until the app is
*served*.

Skipped automatically (see conftest) when the extra is not installed.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from fde_scope.config import AgentSpec, CorpusConfig, TenantConfig
from fde_scope.corpus import CorpusForge
from fde_scope.deploy import TenantDeployer
from fde_scope.deploy.toolkit import bound_tools, build_toolkit, plan_bindings

pytestmark = pytest.mark.agentscope


def _invoke(toolkit: Any, name: str, args: dict[str, Any], state: Any) -> Any:
    """Run one tool call to completion and return the accumulated ToolResponse."""
    from agentscope.message import ToolCallBlock

    async def _run() -> Any:
        last = None
        call = ToolCallBlock(type="tool_call", id="probe", name=name, input=json.dumps(args))
        async for item in toolkit.call_tool(call, state):
            last = item
        return last

    return asyncio.run(_run())


def _payload(response: Any) -> dict[str, Any]:
    """Parse a successful tool response's text as JSON."""
    assert response.state.value == "success", response.content[0].text
    return json.loads(response.content[0].text)


@pytest.fixture
def corpus_report(sample_rows: list[dict]) -> Any:
    return CorpusForge(CorpusConfig(min_samples_per_category=2, synth_per_gap=0)).forge_rows(sample_rows)


@pytest.fixture
def agent_state() -> Any:
    from agentscope.state import AgentState

    return AgentState()


# ---------------------------------------------------------------------------
# the Toolkit itself
# ---------------------------------------------------------------------------
def test_toolkit_advertises_exactly_the_bound_tools(corpus_report: Any) -> None:
    """``get_tool_schemas()`` is what the model sees — it must list the bound tools."""
    from agentscope.tool import Toolkit

    tenant = TenantConfig(id="acme", name="Acme", sources={"csv": "ignored.csv"})
    bindings = plan_bindings(tenant, AgentSpec(name="a", role="数据分析"), corpus_report)
    toolkit = build_toolkit(bindings, corpus_report)
    assert isinstance(toolkit, Toolkit)

    schemas = asyncio.run(toolkit.get_tool_schemas())
    names = {s["function"]["name"] for s in schemas}
    assert names == set(bound_tools(bindings))
    # Args come from the function signature + docstring, so the model can call them.
    by_name = {s["function"]["name"]: s for s in schemas}
    assert {"query", "category", "limit"} <= set(
        by_name["corpus_search"]["function"]["parameters"]["properties"]
    )
    assert "limit" in by_name["csv_sample"]["function"]["parameters"]["properties"]
    assert by_name["corpus_coverage"]["function"]["name"] == "corpus_coverage"


def test_connector_tool_reads_the_real_file(sample_csv: Path, agent_state: Any) -> None:
    """A bound connector tool returns actual rows from the customer source."""
    tenant = TenantConfig(id="acme", name="Acme", sources={"csv": str(sample_csv)})
    toolkit = build_toolkit(plan_bindings(tenant, AgentSpec(name="a", role="数据分析")), None)

    schema = _payload(_invoke(toolkit, "csv_schema", {}, agent_state))
    assert {"content", "category"} <= {f["name"] for f in schema["fields"]}
    assert schema["row_count"] >= 1

    sample = _payload(_invoke(toolkit, "csv_sample", {"limit": 2}, agent_state))
    assert sample["count"] == 2 and sample["connector"] == "csv"
    assert "物流查询" in sample["rows"][0]["category"]


def test_corpus_tools_answer_from_the_forged_corpus(
    sample_csv: Path, corpus_report: Any, agent_state: Any
) -> None:
    """语料工具真的能检索到锻造产物，coverage 工具真的报出缺口。"""
    tenant = TenantConfig(id="acme", name="Acme", corpus_path=str(sample_csv))
    bindings = plan_bindings(tenant, AgentSpec(name="a", role="工单处理"), corpus_report)
    toolkit = build_toolkit(bindings, corpus_report)

    hits = _payload(_invoke(toolkit, "corpus_search", {"query": "退款", "limit": 3}, agent_state))
    assert 0 < hits["count"] <= 3
    assert all("退款" in item["content"] for item in hits["items"])
    assert hits["items"][0]["provenance"] in {"real", "synthetic", "golden"}

    coverage = _payload(_invoke(toolkit, "corpus_coverage", {}, agent_state))
    assert coverage["total"] == corpus_report.total
    assert coverage["category_counts"] == corpus_report.coverage.category_counts


def test_broken_source_reports_error_instead_of_crashing(tmp_path: Path, agent_state: Any) -> None:
    """现场源不可达时工具要返回 ERROR 让模型换路，而不是把装配炸掉。"""
    tenant = TenantConfig(id="acme", name="Acme", sources={"csv": str(tmp_path / "missing.csv")})
    toolkit = build_toolkit(plan_bindings(tenant, AgentSpec(name="a", role="数据分析")), None)
    response = _invoke(toolkit, "csv_schema", {}, agent_state)
    assert response.state.value == "error"
    assert "not found" in response.content[0].text


# ---------------------------------------------------------------------------
# the deployed agent: toolkit + permissions really are wired in
# ---------------------------------------------------------------------------
def _deploy(sample_csv: Path, corpus_report: Any, **overrides: Any) -> Any:
    tenant = TenantConfig(
        id="acme",
        name="Acme",
        corpus_path=str(sample_csv),
        sources={"csv": str(sample_csv)},
        agents=[{"name": "analyst", "role": "数据分析"}],
        **overrides,
    )
    return TenantDeployer().deploy(tenant, corpus_report=corpus_report)


def test_deployed_agent_has_a_working_toolkit_and_our_permission_context(
    sample_csv: Path, corpus_report: Any, agent_state: Any
) -> None:
    from agentscope.permission import PermissionContext
    from agentscope.tool import Toolkit

    deployed = _deploy(sample_csv, corpus_report)
    agent = deployed.agents[0]

    assert isinstance(agent.toolkit, Toolkit)  # not a dict: a dict means zero tools
    schemas = asyncio.run(agent.toolkit.get_tool_schemas())
    assert {s["function"]["name"] for s in schemas} == {
        "corpus_search",
        "corpus_coverage",
        "csv_schema",
        "csv_sample",
    }

    # The agent enforces the context it was handed — the one in its own state.
    assert isinstance(agent.state.permission_context, PermissionContext)
    assert agent.state.permission_context is deployed.engine
    assert agent._engine.context is agent.state.permission_context
    assert "csv_sample" in agent.state.permission_context.allow_rules

    # And the wired tool actually runs through the assembled agent's toolkit.
    payload = _payload(_invoke(agent.toolkit, "csv_sample", {"limit": 3}, agent_state))
    assert payload["count"] == 3


def test_deployed_agent_registers_exported_skills(
    sample_csv: Path, corpus_report: Any, tmp_path: Path
) -> None:
    """现场技能经官方 ``skills_or_loaders`` 进 Toolkit —— 每个技能一个目录。

    导出器产出 ``<slug>/SKILL.md``（见 skills.exporters），AgentScope 的 loader
    只接受单技能目录，所以这里用真实导出目录验证注册结果，而不是猜测 API。
    """
    from fde_scope.skills.exporters import export_skill
    from fde_scope.skills.models import SkillRecord

    skill_dir = tmp_path / "refund-escalation"
    record = SkillRecord(title="Refund escalation", category="methodology", body_md="# Steps\n1. check SLA\n")
    for f in export_skill(record, "agentscope"):
        (tmp_path / f.name).parent.mkdir(parents=True)
        (tmp_path / f.name).write_text(f.content, encoding="utf-8")

    tenant = TenantConfig(
        id="acme",
        name="Acme",
        corpus_path=str(sample_csv),
        agents=[
            {
                "name": "analyst",
                "role": "数据分析",
                "toolkit": {"skills_dirs": [str(skill_dir), str(tmp_path / "ghost")]},
            }
        ],
    )
    deployed = TenantDeployer().deploy(tenant, corpus_report=corpus_report)
    toolkit = deployed.agents[0].toolkit

    async def _skills() -> Any:
        return await toolkit._get_available_skills()

    registered = asyncio.run(_skills())
    assert list(registered) == ["refund-escalation"]  # ghost dir dropped, never faked
    instructions = asyncio.run(toolkit.get_skill_instructions()) or ""
    assert "Refund escalation" in instructions


def _agentscope_at_least(version: str) -> bool:
    """Tuple-compare the installed agentscope version against *version*."""
    import agentscope

    def _key(v: str) -> tuple[int, ...]:
        return tuple(int(p) for p in v.split(".post")[0].split(".")[:3])

    return _key(agentscope.__version__) >= _key(version)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("conservative", "ask"), ("autonomous", "deny")],
    ids=["hitl_escalates", "unattended_refuses"],
)
def test_approval_policy_decides_the_fate_of_an_unmatched_tool(
    tmp_path: Path, mode: str, expected: str
) -> None:
    """Bound reads are ALLOWed via their rules; anything else follows the
    tenant's approval policy. Deployed tools are never flagged read-only
    (build_toolkit), so upstream's 2.0.5+ read-only fast path cannot hijack
    the verdict — see test_read_only_flag_is_never_a_permission_grant."""
    from agentscope.permission import PermissionEngine
    from agentscope.tool import FunctionTool

    async def _mystery() -> str:
        """A tool no rule mentions."""
        return "nope"

    tenant = TenantConfig(
        id="acme",
        name="Acme",
        sources={"csv": "data/t.csv"},
        agents=[{"name": "analyst", "role": "数据分析"}],
        approval_policy={"mode": mode},
    )
    # Evaluate against the very context the deployed agent carries — not a copy.
    deployed = TenantDeployer().deploy(tenant)
    engine = PermissionEngine(deployed.engine)

    mystery = FunctionTool(_mystery, name="mystery_tool", description="unmatched", is_read_only=False)
    read = FunctionTool(_mystery, name="csv_sample", description="bound read", is_read_only=False)
    assert asyncio.run(engine.check_permission(read, {})).behavior.value == "allow"
    assert asyncio.run(engine.check_permission(mystery, {})).behavior.value == expected


def test_read_only_flag_is_never_a_permission_grant(tmp_path: Path) -> None:
    """The ``is_read_only`` flag alone must not grant unmatched tools.

    Upstream 2.0.5 added a read-only fast path (ALLOW before allow rules),
    so an unmatched *flagged* tool is allowed there — a documented upstream
    divergence pinned here so any future shift turns red. Our deployed
    toolkits never set the flag (build_toolkit), keeping explicit rules the
    only grant channel (remediation-plan B5)."""
    from agentscope.permission import PermissionEngine
    from agentscope.tool import FunctionTool

    async def _mystery() -> str:
        """A tool no rule mentions."""
        return "nope"

    tenant = TenantConfig(
        id="acme",
        name="Acme",
        sources={"csv": "data/t.csv"},
        agents=[{"name": "analyst", "role": "数据分析"}],
        approval_policy={"mode": "conservative"},
    )
    engine = PermissionEngine(TenantDeployer().deploy(tenant).engine)

    flagged = FunctionTool(_mystery, name="flagged_ro", description="unmatched, read-only", is_read_only=True)
    unflagged = FunctionTool(_mystery, name="flagged_rw", description="unmatched", is_read_only=False)

    assert asyncio.run(engine.check_permission(unflagged, {})).behavior.value == "ask"
    flagged_verdict = asyncio.run(engine.check_permission(flagged, {})).behavior.value
    assert flagged_verdict == ("allow" if _agentscope_at_least("2.0.5") else "ask")


# ---------------------------------------------------------------------------
# the app service (create_app) and the lazy-import contract
# ---------------------------------------------------------------------------
def test_create_app_registers_our_subagent_templates(sample_csv: Path, tmp_path: Path) -> None:
    """多 Agent 蓝图必须真的进到 ``create_app``，leader 才能按 type 路由。"""
    from fde_scope.deploy import build_app

    tenant = TenantConfig(
        id="acme",
        name="Acme",
        sources={"csv": str(sample_csv)},
        agents=[{"name": "analyst", "role": "数据分析"}, {"name": "archivist", "role": "文件分析"}],
    )
    app = build_app(tenant, basedir=str(tmp_path / "ws"))
    registered = app.state.custom_subagent_templates
    assert set(registered) == {"analyst", "archivist"}
    assert registered["analyst"].description == "数据分析"


def test_importing_the_deploy_layer_never_imports_agentscope() -> None:
    """延迟导入契约：装得上 agentscope 也不代表 core 会被它拖下水。"""
    code = (
        "import sys, fde_scope, fde_scope.deploy, fde_scope.cli;"
        "assert 'agentscope' not in sys.modules, sorted(m for m in sys.modules if m.startswith('agentscope'))[:5];"
        "print('lazy-ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "lazy-ok" in result.stdout

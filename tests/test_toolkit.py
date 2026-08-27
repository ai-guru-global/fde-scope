"""Tool-plan tests for ``deploy/toolkit`` — pure, no AgentScope import.

The framework-free half of the tool wiring: which capabilities a role agent
gets, against which physical source, and how unconfigured sources are reported.
The real ``Toolkit`` objects built from these plans are covered by
``tests/test_agentscope_runtime.py``.
"""

from __future__ import annotations

from pathlib import Path

from fde_scope.config import AgentSpec, TenantConfig
from fde_scope.corpus import CorpusItem, CorpusReport, CorpusSplit, CoverageReport
from fde_scope.deploy import TenantDeployer
from fde_scope.deploy.toolkit import (
    bound_tools,
    describe_bindings,
    plan_bindings,
    resolve_source,
    unbound_tools,
)


def _corpus_report() -> CorpusReport:
    items = [CorpusItem(id="t-1", content="申请退款，商品质量问题。", category="退款")]
    coverage = CoverageReport(category_counts={"退款": 1}, target_per_category=5, gaps=[])
    empty = CorpusSplit(name="eval", items=[])
    return CorpusReport(
        total=1,
        real=1,
        synthetic=0,
        coverage=coverage,
        train=CorpusSplit(name="train", items=items),
        eval=empty,
        test=CorpusSplit(name="test", items=[]),
    )


# ---------------------------------------------------------------------------
# source resolution
# ---------------------------------------------------------------------------
def test_resolve_source_precedence_per_agent_then_tenant_then_implicit() -> None:
    tenant = TenantConfig(
        id="acme",
        name="Acme",
        sources={"csv": "tenant.csv", "mysql": "tenant-dsn"},
        ticket_api="https://zammad.example",
    )
    spec = AgentSpec(name="a", role="数据分析", toolkit={"sources": {"csv": "override.csv"}})
    assert resolve_source(tenant, spec, "csv") == "override.csv"  # per-agent wins
    assert resolve_source(tenant, spec, "mysql") == "tenant-dsn"  # tenant default
    assert resolve_source(tenant, spec, "mes") is None  # nobody configured it


def test_resolve_source_uses_ticket_api_for_ticketing_connectors() -> None:
    tenant = TenantConfig(id="acme", name="Acme", ticket_api="https://zammad.example/api")
    spec = AgentSpec(name="a", role="工单")
    assert resolve_source(tenant, spec, "zammad") == "https://zammad.example/api"
    assert resolve_source(tenant, spec, "salesforce") == "https://zammad.example/api"


# ---------------------------------------------------------------------------
# the plan itself
# ---------------------------------------------------------------------------
def test_plan_binds_two_tools_per_configured_connector() -> None:
    tenant = TenantConfig(id="acme", name="Acme", sources={"csv": "data/t.csv"})
    bindings = plan_bindings(tenant, AgentSpec(name="a", role="数据分析"))
    assert bound_tools(bindings) == ["csv_schema", "csv_sample"]
    assert unbound_tools(bindings) == ["mysql_schema", "mysql_sample", "mes_schema", "mes_sample"]


def test_unconfigured_connector_is_unbound_with_an_actionable_note() -> None:
    tenant = TenantConfig(id="acme", name="Acme")
    bindings = plan_bindings(tenant, AgentSpec(name="a", role="日志分析"))
    assert bound_tools(bindings) == []
    historian = next(b for b in bindings if b.slug == "historian")
    assert historian.bound is False
    # The note must tell the FDE exactly how to bind it — no silent capability loss.
    assert "sources.historian" in historian.note and "--connector-source historian=" in historian.note


def test_corpus_report_adds_search_and_coverage_tools() -> None:
    tenant = TenantConfig(id="acme", name="Acme", corpus_path="out/corpus.json")
    bindings = plan_bindings(tenant, AgentSpec(name="a", role="工单处理"), _corpus_report())
    corpus_tools = [b for b in bindings if b.kind == "corpus"]
    assert [b.name for b in corpus_tools] == ["corpus_search", "corpus_coverage"]
    assert all(b.bound and b.source == "out/corpus.json" for b in corpus_tools)
    assert "1 forged items" in corpus_tools[0].note


def test_files_role_binds_documents_when_source_known(tmp_path: Path) -> None:
    tenant = TenantConfig(id="acme", name="Acme", sources={"documents": str(tmp_path)})
    bindings = plan_bindings(tenant, AgentSpec(name="a", role="文件分析"))
    assert bound_tools(bindings) == ["documents_schema", "documents_sample"]


def test_describe_bindings_is_manifest_shaped() -> None:
    tenant = TenantConfig(id="acme", name="Acme", sources={"csv": "t.csv"})
    spec = AgentSpec(name="a", role="数据分析")
    view = describe_bindings(spec, plan_bindings(tenant, spec))
    assert view["role_bucket"] == "data"
    assert {t["tool"] for t in view["tools"]} == set(view["bound"]) | set(view["unbound"])
    assert all({"tool", "kind", "connector", "source", "bound", "note"} <= set(t) for t in view["tools"])


def test_deploy_manifest_reports_plan_honestly_in_dry_run() -> None:
    """dry-run（无 agentscope）也报告同一份真相：哪些工具活着，哪些在等源。"""
    tenant = TenantConfig(
        id="acme",
        name="Acme",
        sources={"csv": "data/t.csv"},
        agents=[{"name": "analyst", "role": "数据分析"}, {"name": "archivist", "role": "文件分析"}],
    )
    agents = TenantDeployer(agentscope_extra=False).deploy(tenant, dry_run=True).manifest["agents"]
    analyst, archivist = agents
    assert analyst["connectors"] == ["csv", "mysql", "mes"]
    assert analyst["bound"] == ["csv_schema", "csv_sample"]
    assert len(analyst["unbound"]) == 4
    assert archivist["bound"] == [] and archivist["unbound"] == ["documents_schema", "documents_sample"]


def test_bound_tools_enter_the_allow_rules_not_just_the_manifest() -> None:
    """Capability and approval must stay coherent: a bound tool is an ALLOW rule.

    In DEFAULT permission mode an unmatched call is an ASK, so a role tool that
    is bound but not allowed would escalate every read to a human.
    """
    tenant = TenantConfig(
        id="acme",
        name="Acme",
        sources={"csv": "data/t.csv"},
        agents=[{"name": "analyst", "role": "数据分析"}],
    )
    manifest = TenantDeployer(agentscope_extra=False).deploy(tenant, dry_run=True).manifest
    allowed = {tool for tool, _ in manifest["permissions"]["allow"]}
    assert {"csv_schema", "csv_sample"} <= allowed
    assert "mes_sample" not in allowed  # unbound → no phantom permission

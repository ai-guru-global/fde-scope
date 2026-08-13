"""Tests for Layer 3 — deploy (assembly + manifest; no live agentscope needed)."""

from __future__ import annotations

from fde_scope.config import TenantConfig
from fde_scope.deploy import (
    PermissionBlueprint,
    SandboxSpec,
    TenantDeployer,
    default_blueprint,
)


def test_sandbox_spec_translates_to_docker_kwargs() -> None:
    spec = SandboxSpec(tenant_id="acme", backend="docker", base_image="img:1")
    kw = spec.as_docker_kwargs()
    assert kw["workspace_id"] == "fde_acme"
    assert kw["base_image"] == "img:1"
    # resource_quota is NOT a DockerWorkspace kwarg (no such param in 2.0)
    assert "resource_quota" not in kw


def test_default_blueprint_has_isolation_rules() -> None:
    bp = default_blueprint("acme")
    deny_tools = [t for t, _ in bp.deny]
    assert "access_other_tenant" in deny_tools
    assert "exec_shell" in deny_tools


def test_default_blueprint_scales_ask_with_approval_mode() -> None:
    """ApprovalPolicy.mode moves the ASK boundary: autonomous < balanced < conservative."""
    auto = default_blueprint("acme", mode="autonomous")
    balanced = default_blueprint("acme", mode="balanced")
    conservative = default_blueprint("acme", mode="conservative")
    assert auto.ask == []
    assert len(balanced.ask) < len(conservative.ask)
    # allow/deny are identical across modes — only the ASK bucket moves
    assert auto.allow == balanced.allow == conservative.allow
    assert auto.deny == balanced.deny == conservative.deny


def test_deploy_manifest_reflects_approval_policy_mode() -> None:
    """deploy() must wire the tenant's approval policy into the blueprint."""
    deployer = TenantDeployer(agentscope_extra=False)
    auto = deployer.deploy(
        TenantConfig(id="t1", name="T1", approval_policy={"mode": "autonomous"}), dry_run=True
    )
    conservative = deployer.deploy(
        TenantConfig(id="t2", name="T2", approval_policy={"mode": "conservative"}), dry_run=True
    )
    assert auto.manifest["permissions"]["ask"] == []
    assert len(conservative.manifest["permissions"]["ask"]) > 0
    assert auto.manifest["permissions"]["deny"] == conservative.manifest["permissions"]["deny"]


def test_deployer_dry_run_returns_manifest_only() -> None:
    deployer = TenantDeployer(agentscope_extra=False)
    tenant = TenantConfig(id="acme", name="Acme", model="qwen-max")
    deployed = deployer.deploy(tenant, dry_run=True)

    assert deployed.is_assembled is False
    assert deployed.manifest["tenant_id"] == "acme"
    assert deployed.manifest["sandbox"]["backend"] == "docker"
    assert deployed.manifest["corpus_collection"] == "corpus_acme"
    assert deployed.manifest["permissions"]["deny"]  # non-empty
    assert deployed.manifest["started"] is False


def test_deployer_includes_corpus_summary_when_given(sample_rows: list[dict]) -> None:
    from fde_scope.config import CorpusConfig
    from fde_scope.corpus import CorpusForge

    report = CorpusForge(CorpusConfig(min_samples_per_category=100, synth_per_gap=2)).forge_rows(sample_rows)
    deployer = TenantDeployer(agentscope_extra=False)
    tenant = TenantConfig(id="acme", name="Acme")
    deployed = deployer.deploy(tenant, corpus_report=report, dry_run=True)
    assert deployed.manifest["corpus"]["total"] == report.total


def test_permission_blueprint_describes() -> None:
    bp = PermissionBlueprint(tenant_id="x")
    text = bp.describe()
    assert "ALLOW" in text and "DENY" in text

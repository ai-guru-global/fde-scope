"""Tests for role → connector binding (deploy/roles.py) and its use in deploy."""

from __future__ import annotations

import pytest

from fde_scope.config import TenantConfig
from fde_scope.deploy.roles import canonical_role, connectors_for_role
from fde_scope.deploy.tenant_manager import TenantDeployer


@pytest.mark.parametrize(
    ("role", "bucket"),
    [
        ("data", "data"),
        ("数据分析 Agent", "data"),
        ("database analyst", "data"),
        ("日志分析", "logs"),
        ("Log Analyst", "logs"),
        ("historian", "logs"),
        ("文件分析", "files"),
        ("Document Analysis", "files"),
        ("pdf reader", "files"),
        ("调研员", None),
        ("", None),
    ],
)
def test_canonical_role(role: str, bucket: str | None) -> None:
    assert canonical_role(role) == bucket


def test_connectors_for_known_roles() -> None:
    assert connectors_for_role("数据分析") == ["csv", "mysql", "mes"]
    assert "documents" in connectors_for_role("文件分析")
    assert "historian" in connectors_for_role("日志分析")


def test_connectors_for_unknown_role_is_empty() -> None:
    assert connectors_for_role("项目经理") == []


def test_deploy_manifest_binds_files_role_to_documents() -> None:
    """A '文件分析' agent must surface the documents connector in its manifest."""
    deployer = TenantDeployer(agentscope_extra=False)
    tenant = TenantConfig(
        id="acme",
        name="Acme",
        agents=[
            {"name": "files", "role": "文件分析"},
            {"name": "data", "role": "数据分析"},
        ],
    )
    deployed = deployer.deploy(tenant, dry_run=True)
    agents = deployed.manifest["agents"]

    assert agents[0]["connectors"] == ["documents"]
    assert agents[1]["connectors"] == ["csv", "mysql", "mes"]

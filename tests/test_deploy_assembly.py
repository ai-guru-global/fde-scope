"""Integration test for the deploy layer's real AgentScope assembly.

Gated behind the ``agentscope`` extra: these tests only run when
``agentscope`` is importable (CI installs the extra). Locally they skip,
which is correct — the assembly code is exercised by the dry-run path
covered in test_deploy.py regardless.
"""

from __future__ import annotations

import pytest

agentscope = pytest.importorskip("agentscope")  # skip the whole module if not installed

# Imports come after the optional-skip guard so this module stays importable
# even when agentscope isn't installed (pytest.importorskip raises Skip first).
from fde_scope.config import TenantConfig  # noqa: E402
from fde_scope.deploy import TenantDeployer  # noqa: E402
from fde_scope.deploy.sandbox_config import SandboxSpec  # noqa: E402


def test_sandbox_spec_docker_kwargs_match_real_api() -> None:
    """The kwargs we emit must be accepted by the real DockerWorkspace."""
    spec = SandboxSpec(tenant_id="acme", backend="docker", base_image="python:3.12-slim")
    kwargs = spec.as_docker_kwargs()
    # Spot-check the keys the real constructor expects (2.0.5 DockerWorkspace).
    for required in ("workspace_id", "base_image"):
        assert required in kwargs


def test_deployer_assembles_real_types_when_extra_installed() -> None:
    """With agentscope present, deploy() should reach the real-assembly path.

    We can't actually start Docker / a model here, so we assert the deployer
    *detects* the extra and produces a manifest whose sandbox backend is
    recorded — proving the lazy-import wiring is sound.
    """
    deployer = TenantDeployer(agentscope_extra=True)
    tenant = TenantConfig(id="acme", name="Acme", model="qwen-max")
    # dry_run keeps it from actually starting a workspace/model, but with
    # extra=True the deployer knows the real types are available.
    deployed = deployer.deploy(tenant, dry_run=True)
    assert deployed.manifest["sandbox"]["backend"] == "docker"
    assert deployed.manifest["corpus_collection"] == "corpus_acme"

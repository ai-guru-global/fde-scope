"""Architecture contract guards.

Origin: docs/architecture-model/architecture-health-report.md suggestion +
risk review action B3. These tests fail when the *documented* contract drifts
from the code: the 18-phase SOP shape, the 10-gate registry, connector
registry hygiene, and the ``[full]`` install extra that README, Makefile and
pyproject.toml must all agree on.
"""

from __future__ import annotations

from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_sop_defines_exactly_18_phases() -> None:
    from fde_scope.engagement.phases import PHASES

    assert len(PHASES) == 18


def test_default_gate_registry_has_the_documented_10_gates() -> None:
    from fde_scope.engagement.engagement import _default_gate_registry

    gates = _default_gate_registry()
    assert len(gates) == 10


def test_connector_registry_hygiene() -> None:
    """Importing a concrete module registers it under its slug; the reserved
    slug ``base`` must never appear in the registry."""
    import fde_scope.connectors.csv_fallback  # noqa: F401  (registers on import)
    from fde_scope.connectors.base import DataConnector

    slugs = set(DataConnector.registry())
    assert "csv" in slugs
    assert "base" not in slugs


def test_optional_dependencies_define_the_full_extra() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"]["optional-dependencies"]
    assert {"dev", "agentscope", "mysql", "opcua", "web"} <= set(extras)
    full_ref = " ".join(extras["full"])
    for name in ("dev", "agentscope", "mysql", "opcua", "web"):
        assert f"fde-scope[{name}]" in full_ref


def test_install_docs_agree_on_full_extra() -> None:
    """README advertises `pip install -e ".[full]"`, so that extra must exist
    and `make install-full` must use it too — three sources, one truth."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert ".[full]" in readme
    assert '".[full]"' in makefile

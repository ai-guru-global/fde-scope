"""Architecture contract guards.

Origin: docs/architecture-model/architecture-health-report.md suggestion +
risk review action B3. These tests fail when the *documented* contract drifts
from the code: the 18-phase SOP shape, the 10-gate registry, connector
registry hygiene, the ``[full]`` install extra that README, Makefile and
pyproject.toml must all agree on, and the measured AgentScope window that
pyproject and docs/agentscope_api_mapping.md must quote identically.
"""

from __future__ import annotations

import re
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


def test_measured_agentscope_window_is_documented() -> None:
    """The AgentScope window in pyproject is *measured* (2.0.4 fails on
    `agentscope.rag.ExcelParser`; 2.0.5+ add a read-only fast path that would
    bypass rule grants — adapted in B5, see build_toolkit), so it is not a
    constraint to edit casually. docs/agentscope_api_mapping.md must quote
    the same specifier verbatim: re-measure → update both, or this fails."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    (requirement,) = data["project"]["optional-dependencies"]["agentscope"]
    doc = (REPO_ROOT / "docs" / "agentscope_api_mapping.md").read_text(encoding="utf-8")
    assert requirement in doc
    assert "2.0.4.post1" in doc


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _roadmap_bullets(text: str, heading_marker: str) -> list[str]:
    """Collect the ``- `` bullets of the section whose *heading* contains
    *heading_marker*, stopping at the next heading."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("#") and heading_marker in line)
    bullets: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if line.strip().startswith("- "):
            bullets.append(line.strip())
    return bullets


def _done_keyword(item: str) -> str | None:
    """Leading latin phrase of a roadmap item ('rosbag2 真实回放…' ->
    'rosbag2'); None for CJK-led items ('小米 MiMo…')."""
    m = re.match(r"([^\u4e00-\u9fff（(]+)", item)
    key = m.group(1).strip(" \t—-").lower() if m else ""
    return key or None


def test_web_route_count_claim_is_honest() -> None:
    """Both feature lists advertise the web console's route count in two
    places (intro aggregate + delivery-surface table). The advertised number
    must equal the actual route decorators in web/app.py — the count drifted
    once already (docs said 32 while the app served 33)."""
    app = _read("fde_scope/web/app.py")
    actual = len(re.findall(r"@app\.(?:get|post|put|delete|websocket)\(", app))
    zh = _read("docs/features.md")
    en = _read("docs/features-en.md")
    claimed: list[int] = [
        int(m.group(1))
        for pattern, text in (
            (r"门禁\s*/\s*(\d+)\s*路由", zh),
            (r"FastAPI 单页\s*,\s*(\d+)\s*路由", zh),
            (r"gates\s*/\s*(\d+)\s*routes", en),
            (r"FastAPI single page,\s*(\d+)\s*routes", en),
        )
        for m in [re.search(pattern, text)]
    ]
    assert len(claimed) == 4, "route-count claim not found in both feature lists"
    assert claimed == [actual] * 4


def test_feature_list_roadmaps_agree_with_readme_checkboxes() -> None:
    """README's Roadmap marks delivered work with ``[x]``; the feature lists
    (docs/features.md + docs/features-en.md) must not keep listing it as
    outstanding. Origin: rosbag2 replay was checked off in README while both
    feature lists still carried it under 'not done yet'. Also requires the
    zh/en roadmap sections to stay in sync on item count."""
    readme_roadmap = _roadmap_bullets(_read("README.md"), "Roadmap")
    zh_bullets = _roadmap_bullets(_read("docs/features.md"), "尚未完成")
    en_bullets = _roadmap_bullets(_read("docs/features-en.md"), "Not done yet")
    assert zh_bullets and len(zh_bullets) == len(en_bullets)
    zh_roadmap = "\n".join(zh_bullets).lower()
    en_roadmap = "\n".join(en_bullets).lower()
    for line in readme_roadmap:
        m = re.match(r"- \[x\] (.+)", line)
        if not m:
            continue
        keyword = _done_keyword(m.group(1))
        if keyword is None:
            continue
        assert keyword not in zh_roadmap, f"README marks {keyword!r} done; zh roadmap still lists it"
        assert keyword not in en_roadmap, f"README marks {keyword!r} done; en roadmap still lists it"

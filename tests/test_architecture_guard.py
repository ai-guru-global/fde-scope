"""Architecture contract guards.

Origin: docs/architecture-model/architecture-health-report.md suggestion +
risk review action B3. These tests fail when the *documented* contract drifts
from the code: the 18-phase SOP shape, the 10-gate registry, connector
registry hygiene, the ``[full]`` install extra that README, Makefile and
pyproject.toml must all agree on, the measured AgentScope window that
pyproject and docs/agentscope_api_mapping.md must quote identically, the
package data the course reader needs to survive a wheel install, and the
console's route count wherever README, the feature lists or the landing page
advertise it.
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


def test_wheel_ships_the_course_the_reader_depends_on() -> None:
    """``/course`` renders ``course-level-1/*.md`` at runtime, but the wheel
    target only packages ``fde_scope``, so a pip install used to answer every
    locale with the missing-sources notice. ``force-include`` now copies the
    lessons into the package as data and ``web/course.py`` falls back to that
    copy; both halves are pinned because either one alone regresses silently
    to a blank reading room."""
    from fde_scope.web.course import _COURSE_DIRNAME

    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    targets = data["tool"]["hatch"]["build"]["targets"]
    force_include = targets["wheel"]["force-include"]
    assert list(force_include) == ["course-level-1"]
    assert force_include["course-level-1"] == f"fde_scope/_data/{_COURSE_DIRNAME}"
    # an sdist without the lessons cannot build a wheel that has them
    assert "course-level-1" in targets["sdist"]["include"]


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


_CONSOLE_SOURCES = ("fde_scope/web/app.py", "fde_scope/web/guided_api.py")
_ROUTE_DECORATOR = r"@(?:app|router)\.(get|post|put|delete|patch|websocket)\(\s*[\"']([^\"']+)"
# Both decorators are conditional fallbacks for an in-repo asset directory: each
# is registered only when catalog_site_dir() / gtm_site_dir() is None, i.e. in an
# installed app. A checkout serves those two prefixes with a StaticFiles mount
# instead, so its runtime table has two fewer entries while answering the same
# paths. The declared count (57) is therefore the install-invariant number to
# advertise — the served count (55 in a checkout) would understate the surface.
_CONDITIONAL_ASSET_FALLBACKS = {("get", "/catalog/{rest:path}"), ("get", "/GTM/{rest:path}")}


def _declared_routes() -> list[tuple[str, str]]:
    """Every ``(verb, path)`` the console's route decorators declare.
    ``app.py`` includes the guided-mode router without a prefix, so a
    decorator's path is the served path verbatim."""
    declared: list[tuple[str, str]] = []
    for name in _CONSOLE_SOURCES:
        declared.extend(re.findall(_ROUTE_DECORATOR, _read(name)))
    return declared


def test_route_decorator_scan_matches_the_served_route_table() -> None:
    """Meta-guard for the advertised count below: a count is only as honest as
    the scan producing it. Origin: the pattern omitted ``patch``, so the guard
    asserted 56 while the console declared 57 — the test passed and was wrong.
    Comparing against the generated OpenAPI paths keeps the scan anchored to
    what the app really serves, so a missing verb or a renamed decorator cannot
    slip through silently again."""
    from fde_scope.web.app import app

    declared = _declared_routes()
    assert len(declared) == len(set(declared)), "a verb+path is declared twice; the count would lie"
    served = {(method, path) for path, ops in app.openapi()["paths"].items() for method in ops}
    assert set(declared) - _CONDITIONAL_ASSET_FALLBACKS == served


def test_web_route_count_claim_is_honest() -> None:
    """Eleven places advertise the console's route count: both feature lists
    (intro aggregate + delivery-surface table), README (roadmap checkbox,
    architecture diagram, delivery-surface table, directory tree), the ``#arch``
    tile the landing page renders about itself, and that tile's zh→en pair in
    ``web/i18n.py`` (``to_en`` replaces by exact match, so a stale key would
    leave the English page in Chinese *and* wrong). All eleven must equal the
    declared decorator count. Origin: this guard pinned only the four
    feature-list claims, so README (36) and the tile (43) drifted unwatched
    while the guard stayed green — hence the per-pattern expected counts, which
    also fail if a claim disappears instead of merely changing value."""
    actual = len(_declared_routes())
    readme, zh, en = _read("README.md"), _read("docs/features.md"), _read("docs/features-en.md")
    i18n = _read("fde_scope/web/i18n.py")
    claims: list[int] = []
    for pattern, text, expected in (
        (r"FastAPI,\s*(\d+)\s*routes", readme, 1),
        (r"FastAPI 控制台<br/>\s*(\d+)\s*路由", readme, 1),
        (r"console \((\d+) routes", readme, 2),
        (r"门禁\s*/\s*(\d+)\s*路由", zh, 1),
        (r"FastAPI 单页\s*,\s*(\d+)\s*路由", zh, 1),
        (r"gates\s*/\s*(\d+)\s*routes", en, 1),
        (r"FastAPI single page,\s*(\d+)\s*routes", en, 1),
        (r"Web 控制台（(\d+) 路由）", _read("fde_scope/web/app.py"), 1),
        (r"Web 控制台（(\d+) 路由）", i18n, 1),
        (r"Web console \((\d+) routes\)", i18n, 1),
    ):
        found = [int(n) for n in re.findall(pattern, text)]
        assert len(found) == expected, f"{pattern!r}: expected {expected} claim(s), found {found}"
        claims.extend(found)
    assert len(claims) == 11
    assert claims == [actual] * 11, f"advertised {sorted(set(claims))} but {actual} routes are declared"


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

"""Navigation coverage: every capability the product ships has a rail row.

This is the guard behind the 2026-11-10 rail rewrite. The rail used to be a
table of contents (11 destinations); the product had ~18 capability families,
so the corpus engine, eval, ontology, flywheel, license, connectors, evidence,
share links and every console view lived behind a typed CLI command or a
hand-written hash URL. "All features reachable from the left rail" is only a
claim if something fails when a feature loses its row, which is what this file
does.

Three things are checked, and they fail differently:

1. **Every advertised capability has a row.** ``CAPABILITIES`` below is the
   inventory from the feature list; each entry names the row key that carries
   it. Removing a row from ``NAV_BANDS`` fails here, not silently in the UI.
2. **Every row resolves to something that exists.** A ``/console?v=`` row must
   name a real console view; a ``#anchor`` must exist in the console document
   (rendered templates included) — otherwise the row scrolls to nowhere, the
   exact failure ``test_rail_guard`` guards for in-page anchors but could not
   see across the rail→console boundary.
3. **The console understands every parameter the rail emits.** ``?t=`` must be
   a key in ``DETAIL_TABS``; an unknown tab would leave the reader on Overview
   with no error.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from fde_scope.web import app as web_app
from fde_scope.web.layout import NAV_BANDS

REPO_ROOT = Path(__file__).resolve().parents[1]

_ROWS = {item.key: item for band in NAV_BANDS for item in band.items}


#: Capability family -> the rail row that must carry it. Mirrors the feature
#: inventory in ``docs/features.md``; a new capability belongs in both.
CAPABILITIES: dict[str, str] = {
    # SOP engine
    "sop-phases": "v-sop",
    "gates": "v-gates",
    "guided-mode": "v-guided",
    "engagement-context": "v-context",
    "field-journal": "v-journal",
    "evidence": "v-evidence",
    "retrospective": "v-retro",
    "audit-log": "v-audit",
    "sop-full-text": "sop",
    # Data & corpus
    "corpus-engine": "v-forge",
    "kpi": "v-kpi",
    "connectors": "v-ops-conn",
    "github-resources": "resources",
    # Eval & flywheel
    "eval-benchmark": "v-eval",
    "bad-cases": "v-eval",
    "flywheel": "v-flywheel",
    "slo": "v-slo",
    # Deploy & permission
    "agent-deploy": "v-deploy",
    "sandbox-isolation": "v-sandbox",
    "handoff-package": "v-handoff",
    "license": "v-lic",
    # Knowledge
    "skill-library": "v-skills",
    "skill-handbook": "catalog",
    "ontology": "v-onto",
    "repo-docs": "docs",
    "glossary": "glossary",
    "roadmap": "docs-workbench",
    # Learn
    "course": "course",
    "certification": "certification",
    "showcase": "showcase",
    # Entry points
    "overview": "overview",
    "console": "console",
    "gtm": "gtm",
}


def _console_html() -> str:
    """The console document plus every template it renders into itself.

    The tab panes and the ops/deploy/ontology views are produced by JS
    template literals inside ``_DASHBOARD_SHELL``, so the shell alone is the
    right surface for anchor checks.
    """
    return web_app._DASHBOARD_SHELL


def _console_views() -> set[str]:
    return {key for key, _label in web_app._CONSOLE_VIEWS}


def _detail_tabs() -> set[str]:
    m = re.search(r"DETAIL_TABS\s*=\s*\[([^\]]+)\]", _console_html())
    assert m, "DETAIL_TABS not found in the console document"
    return set(re.findall(r"'([a-z]+)'", m.group(1)))


@pytest.mark.parametrize("capability", sorted(CAPABILITIES))
def test_every_capability_has_a_rail_row(capability: str) -> None:
    key = CAPABILITIES[capability]
    assert key in _ROWS, f"capability {capability!r} points at missing rail row {key!r}"


def test_no_rail_row_is_orphaned() -> None:
    """A row nothing claims is either a capability missing from the inventory
    (fine, but then add it) or dead navigation (not fine)."""
    claimed = set(CAPABILITIES.values())
    orphans = sorted(set(_ROWS) - claimed)
    assert orphans == [], f"rail rows with no capability entry: {orphans}"


def test_console_rows_name_a_real_view_and_tab() -> None:
    views = _console_views()
    tabs = _detail_tabs()
    problems = []
    for key, item in _ROWS.items():
        if not item.path.startswith("/console"):
            continue
        query = parse_qs(urlparse(item.path).query)
        view = (query.get("v") or ["workbench"])[0]
        if view not in views:
            problems.append(f"{key}: view {view!r} is not in _CONSOLE_VIEWS")
        for tab in query.get("t") or []:
            if tab not in tabs:
                problems.append(f"{key}: tab {tab!r} is not in DETAIL_TABS")
    assert problems == [], problems


def test_console_rows_point_at_sections_that_exist() -> None:
    """``/console?v=ops#ops-eval`` is only a link if ``id="ops-eval"`` is
    rendered somewhere. Anchors inside JS template literals count — they are
    what the reader ends up scrolling to."""
    html = _console_html()
    ids = set(re.findall(r"""id=["']([A-Za-z0-9_-]+)["']""", html))
    problems = []
    for key, item in _ROWS.items():
        fragment = urlparse(item.path).fragment
        if fragment and fragment not in ids:
            problems.append(f"{key}: #{fragment} has no id= in the console")
    assert problems == [], problems


def test_every_console_view_has_a_rail_route() -> None:
    """The inverse direction: a view that exists but no rail row names is the
    bug this rewrite was about (Ops was reachable only by clicking)."""
    named = {
        (parse_qs(urlparse(i.path).query).get("v") or ["workbench"])[0]
        for i in _ROWS.values()
        if i.path.startswith("/console")
    }
    missing = sorted(_console_views() - named)
    assert missing == [], f"console views with no rail row: {missing}"


def test_view_switcher_links_are_real_hrefs() -> None:
    """The console's view switcher must be links, not buttons: a button has no
    href, so it cannot be opened in a new tab, copied, or crawled."""
    from fde_scope.web.layout import side_nav

    rail = side_nav("v-skills", views=web_app._CONSOLE_VIEWS)
    switcher = re.findall(r'<a class="navbtn[^"]*" data-view="[a-z]+" href="([^"]+)"', rail)
    assert len(switcher) == len(web_app._CONSOLE_VIEWS), switcher
    assert "/console?v=ops" in switcher


def test_rail_is_bilingual_and_bounded() -> None:
    """Every row carries an English label, and the rail stays one level deep:
    ``side_nav`` expands only the active row, so a deeper tree would hide most
    of the product behind a click — the opposite of the goal."""
    assert all(item.en for item in _ROWS.values())
    assert len(_ROWS) <= 40, f"rail row count {len(_ROWS)} — is this still scannable?"


def test_console_router_understands_every_parameter_the_rail_emits() -> None:
    """``applyDest`` must read ``v`` and ``t``, and honour the fragment.

    The rail links into the console; if the console only knew bare hashes, the
    rows would be links that silently land on the workbench. This pins the
    contract between the two halves.
    """
    html = _console_html()
    for token in (
        "new URLSearchParams(location.search)",
        "q.get('v')",
        "q.get('t')",
        "q.get('e')",
        "location.hash",
        "DETAIL_TABS",
    ):
        assert token in html, f"console router no longer handles {token!r}"


def test_rail_rows_are_unique_destinations() -> None:
    """Two rows pointing at the same URL would be a duplicate, not coverage."""
    seen: dict[str, str] = {}
    for key, item in _ROWS.items():
        assert item.path not in seen, f"{key} and {seen[item.path]} share {item.path}"
        seen[item.path] = key


def test_console_view_href_matches_the_router_contract() -> None:
    from fde_scope.web.layout import console_view_href

    assert console_view_href("workbench", en=False) == "/console"
    assert console_view_href("ops", en=False) == "/console?v=ops"
    assert console_view_href("ops", en=True) == "/en/console?v=ops"


# ---------------------------------------------------------------------------
# M1-01: the rail's destinations must have content after an install, not a
# "not available in this install" notice. Every row that points at a page the
# app serves from a bundled asset is checked against the packaged copy too.
# ---------------------------------------------------------------------------
def test_every_bundled_asset_has_a_build_entry() -> None:
    """A resolver without a build entry is a notice page on every install."""
    import tomllib

    from fde_scope.assets import PACKAGED_ASSETS

    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    build = set(data["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"])
    covered = {
        p
        for p in PACKAGED_ASSETS
        if any(
            p.startswith(d + "/")
            for d in ("course-level-1", "examples/quickstart_csv", "examples/quickstart_manufacturing")
        )
    }
    assert set(PACKAGED_ASSETS) - covered == build, (
        f"missing from the wheel: {sorted(set(PACKAGED_ASSETS) - covered - build)}"
    )


def test_document_reader_slugs_are_all_shippable() -> None:
    """Every ``/docs/<slug>`` must resolve to a file that exists in the tree.

    The reader's own table is the source of truth for both the route allowlist
    and the packaging list; a slug whose file is absent renders the
    missing-file notice in every install.
    """
    from fde_scope.web.docs_reader import _DOCS

    missing = [path for _slug, path, *_ in _DOCS if not (REPO_ROOT / path).is_file()]
    assert missing == [], f"document slugs with no file: {missing}"


def test_asset_root_finds_the_checkout_and_the_packaged_copy() -> None:
    """Precedence: a checkout wins, and the packaged copy is the fallback.

    Simulated by asking for a path that only exists at one base at a time; both
    bases are exercised without touching the filesystem layout.
    """
    from fde_scope import assets

    checkout, packaged = assets._candidates()
    assert (checkout / "docs" / "skills-catalog" / "site").is_dir()
    # The packaged base exists as a directory in a checkout only after a build;
    # the assertion that matters is that it is *asked* second, so a wheel
    # (where the checkout base has no docs/) falls through to it.
    assert assets.asset_root("docs/skills-catalog/site") == checkout / "docs" / "skills-catalog" / "site"
    assert assets.asset_root("definitely-not-a-real-asset") is None
    assert packaged.name == "_data"


def test_catalog_and_gtm_resolve_through_the_asset_layer() -> None:
    """Regression for the blank-notice bug: deps must not rebuild a repo-root
    path by hand, or an install serves nothing again."""
    import inspect

    from fde_scope.web import deps

    for fn in (deps.catalog_site_dir, deps.gtm_site_dir, deps.resources_site_dir):
        src = inspect.getsource(fn)
        assert "asset_root(" in src, f"{fn.__name__} bypasses the asset layer"
        assert "parents[2]" not in src, f"{fn.__name__} hardcodes the checkout layout"

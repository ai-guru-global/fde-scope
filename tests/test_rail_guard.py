"""Left-rail structural guards.

:func:`fde_scope.web.layout.side_nav` is now the only source of the rail: ten
documents (console, overview, SOP, course, glossary, certification, resources,
the portfolio registry and the two doc readers, in both locales) compile their
tree from it. That removes the eight hand-copied rails that used to drift, and
moves the risk into the builder, so these tests pin the contract the builder
must keep.

The load-bearing property is *the rail never lies about the document*. Every
``#anchor`` it offers has to land on an ``id=`` in the same page; a section
renamed in the body without the outline list updated produces a rail row that
scrolls nowhere, which readers experience as a broken page rather than a broken
link. The rest of the file guards the collapse behaviour: state lives in
``aria-expanded`` alone (one attribute serves assistive tech and the CSS that
hides ``.rows``), the document always ships open so a script failure cannot
hide content, and the rail-wide toggle is a button because a link there would
read as a destination.
"""

from __future__ import annotations

import re

from fde_scope.web import app as web_app
from fde_scope.web import certification, course, docs_reader, glossary, resources, showcase, sop

RAIL = re.compile(r'<nav class="snav">.*?</nav>', re.S)
_BAND = re.compile(
    r'<section class="sec(?P<active> has-active)?">'
    r'<button class="grp" type="button" aria-expanded="(?P<open>true|false)" '
    r'data-nav="(?P<key>[a-z-]+)" aria-controls="(?P<controls>[^"]+)">'
    r".*?</button>"
    r'<div class="rows" id="(?P<id>[^"]+)">',
    re.S,
)


def _pages() -> dict[str, str]:
    """Every rail-bearing document, both locales."""
    out: dict[str, str] = {}
    for loc in ("zh", "en"):
        suffix = "" if loc == "zh" else " [en]"
        out[f"/{loc}/sop{suffix}"] = sop.render(locale=loc)
        out[f"/{loc}/course{suffix}"] = course.render(locale=loc)
        out[f"/{loc}/glossary{suffix}"] = glossary.render(locale=loc)
        out[f"/{loc}/certification{suffix}"] = certification.render(locale=loc)
        out[f"/{loc}/resources{suffix}"] = resources.render(locale=loc)
        out[f"/{loc}/showcase{suffix}"] = showcase.render(locale=loc)
        out[f"/{loc}/docs/readme{suffix}"] = docs_reader.render("readme", loc)
    out["/overview"] = web_app._OVERVIEW_HTML
    out["/en/overview"] = web_app._OVERVIEW_HTML_EN
    out["/console"] = web_app._DASHBOARD_HTML
    out["/en/console"] = web_app._DASHBOARD_HTML_EN
    return out


PAGES = _pages()


def test_every_rail_anchor_resolves_to_an_id_in_its_page() -> None:
    """The drift guard the outline lists promise: a rail row is only allowed to
    point at a heading that actually exists in the same document."""
    offenders: list[str] = []
    checked = 0
    for name, html in PAGES.items():
        nav = RAIL.search(html)
        assert nav is not None, f"{name}: no rail in the rendered page"
        rest = html[: nav.start()] + html[nav.end() :]
        ids = set(re.findall(r'\bid="([^"]+)"', rest))
        for anchor in re.findall(r'<a href="#([^"]+)">', nav.group(0)):
            checked += 1
            if anchor not in ids:
                offenders.append(f"{name} -> #{anchor}")
    assert offenders == [], f"{len(offenders)} dead rail anchor(s): {offenders[:8]}"
    assert checked >= 100, f"guard lost its coverage (only {checked} anchors checked)"


def test_every_page_carries_exactly_four_bands() -> None:
    """Four bands is the navigation's shape: learners, engineers, workbench,
    external. A fifth means either a real IA change (update this test and
    DESIGN.md together) or the builder emitting the tree twice."""
    for name, html in PAGES.items():
        nav = RAIL.search(html).group(0)
        assert nav.count('<section class="sec') == 4, f"{name}: band count drifted"
        assert nav.count('<div class="navtools">') == 1, f"{name}: navtools count"


def test_bands_are_collapsible_and_ship_open() -> None:
    """``aria-expanded`` is the single source of collapse state, and the server
    always renders ``true``: a document whose scripts never run must show every
    band, because hiding content is the one failure this control cannot be
    allowed to cause."""
    for name, html in PAGES.items():
        nav = RAIL.search(html).group(0)
        bands = list(_BAND.finditer(nav))
        assert len(bands) == 4, f"{name}: only {len(bands)} collapsible band(s) parsed"
        keys, problems = set(), []
        for b in bands:
            if b["open"] != "true":
                problems.append(f"{b['key']} ships collapsed")
            if b["controls"] != b["id"]:
                problems.append(f"{b['key']}: aria-controls {b['controls']} != id {b['id']}")
            if b["key"] in keys:
                problems.append(f"duplicate data-nav {b['key']}")
            keys.add(b["key"])
        assert problems == [], f"{name}: {problems}"


def test_highlight_and_subnav_stay_inside_one_band() -> None:
    """The active row owns the outline: ``has-active`` marks its band so the JS
    can force it open, and ``.subnav`` must never appear in any other band — a
    second page-local tree would leave the reader guessing which page these
    anchors belong to. So every band gets its own slice, not just the gap
    around the active one."""
    for name, html in PAGES.items():
        nav = RAIL.search(html).group(0)
        bands = list(_BAND.finditer(nav))
        marked = [b["key"] for b in bands if b["active"]]
        leaves = re.findall(r'<a href="[^"]*" class="active">', nav)
        assert len(leaves) <= 1, f"{name}: {len(leaves)} active leaves"
        if not leaves:
            assert marked == [], f"{name}: band highlighted with no active row ({marked})"
        else:
            assert len(marked) == 1, f"{name}: active row without exactly one has-active band: {marked}"

        for idx, b in enumerate(bands):
            start = b.end()
            stop = bands[idx + 1].start() if idx + 1 < len(bands) else len(nav)
            nests = nav.count('<div class="subnav">', start, stop)
            if b["active"]:
                assert nests <= 1, f"{name}: {nests} outlines inside band {b['key']}"
            else:
                assert nests == 0, f"{name}: .subnav leaked into inactive band {b['key']}"


def test_rail_carries_no_inline_style() -> None:
    """Sizes, radii and colours live in the token ramp. One ``style=`` in a
    generated rail is how the shared system acquires per-page exceptions that
    nobody can see in the CSS."""
    for name, html in PAGES.items():
        nav = RAIL.search(html).group(0)
        assert "style=" not in nav, f"{name}: inline style reached the rail"


def test_collapse_all_is_a_button_not_a_destination() -> None:
    """The rail-wide toggle sits above the bands and must read as a control:
    a link there would be indistinguishable from a page, and clicking it would
    navigate instead of restructuring the tree."""
    for name, html in PAGES.items():
        nav = RAIL.search(html).group(0)
        tools = re.search(r'<div class="navtools">.*?</button></div>', nav, re.S)
        assert tools is not None, f"{name}: missing navtools"
        block = tools.group(0)
        assert block.startswith('<div class="navtools"><button class="tall" type="button"'), name
        assert "<a " not in block, f"{name}: navtools contains a link"
        assert 'data-collapse="' in block and 'data-expand="' in block, (
            f"{name}: navtools cannot relabel itself between states"
        )
        # The rail-wide toggle acts on four bands, so it owns no single
        # disclosure relation. ``aria-expanded`` there would let assistive tech
        # announce a state for a region that does not exist; only the per-band
        # buttons (``aria-controls`` -> ``.rows``) may carry it.
        assert "aria-expanded" not in block, f"{name}: navtools claims a disclosure it does not own"

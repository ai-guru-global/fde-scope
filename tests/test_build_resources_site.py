"""Regression tests for ``scripts/build_resources_site.py`` (the resources portal).

The portal renders the *same objects* as the in-app ``/resources`` page, so these
tests pin the two things that made the rewrite necessary rather than the
appearance itself:

* the shared layers are really used — the portal owns no palette, no radius
  outside the ladder, no sticky-bar machinery and no second definition of the
  resource card (the drift this started from was ``.chip`` existing at 2px, 6px
  and 999px on three surfaces);
* the two escape points stay on their own sides of the trust boundary — upstream
  text ships **raw** in the payload and is escaped once by the JS ``esc()``,
  while our authored copy is escaped once at build time and therefore never
  rides in the payload at all.

Assertions about CSS run on :func:`_declarations` (comments stripped) because
several of these bans are *documented* in the CSS comments; a guard that read
them would fail on its own prose.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_resources_site.py"

#: Full-width punctuation has no business appearing in translated chrome. It is
#: checked separately from the ideograph range because U+FF1A ``：`` sits outside
#: ``[一-鿿]``, so a CJK-only guard misses precisely the leak that shipped once.
_FULLWIDTH = "：｜、（）【】，。；「」"

#: Every class the portal emits, from either side of the payload boundary — the
#: contract, not a discovery: ``rel-*``/``lic-*`` in particular are spelled by
#: concatenation in the card template, so a renamed bucket is a silently
#: unbadged card rather than a runtime error. ``test_english_*`` and
#: ``test_every_class_the_page_emits_is_defined`` use it as a closed set, which is
#: what forces a new class to be declared here on purpose.
_EMITTED = (
    # card (RESOURCE_CSS)
    "rcard",
    "r-head",
    "r-url",
    "r-sum",
    "r-up",
    "r-meta",
    "r-tags",
    "r-decision",
    "r-mir",
    "r-no",
    "pill",
    "rel-core",
    "rel-adjacent",
    "rel-noise",
    "lic-permissive",
    "lic-noassertion",
    "lic-none",
    "tag",
    # shared components (COMPONENT_CSS)
    "wrap",
    "stats",
    "stat",
    "num",
    "lab",
    "sec-head",
    "n",
    "sec-note",
    "chip",
    "chip-lbl",
    "on",
    "lang",
    "tbtn",
    "ic",
    "when-light",
    "when-dark",
    "rl",
    "rbar",
    "rsearch",
    "r-count",
    "rchips",
    # portal-only (CHROME)
    "masthead",
    "mast-top",
    "brand",
    "mast-actions",
    "mir",
    "qlist",
    "qrow",
    "qnote",
    "files",
)


def _load():
    spec = importlib.util.spec_from_file_location("build_resources_site", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _declarations(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


#: Properties whose value is a colour. Scanned so a literal cannot be written at
#: the point of use; the ramp's own ``--elev`` tokens are exempt because a shadow
#: encodes height off the sheet rather than a hue and has no oklch slot.
_COLOR_PROPS = re.compile(
    r"(?<![-\w])(?:color|background|background-color|border-color|box-shadow|text-shadow|fill|stroke):\s*([^;}]+)"
)

#: The non-colour keywords a value may hold without naming a colour.
_COLOR_KEYWORDS = re.compile(r"(?:transparent|currentColor|none|inherit)[\s,)]*")


def _payload_html(html: str) -> str:
    m = re.search(r'<script id="res-data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "the JSON payload block is missing"
    return m.group(1)


def _chrome(html: str) -> str:
    """The page minus its ``<style>`` and both ``<script>`` blocks: the markup a
    reader gets with JS off. ``<style>`` has to go because the shared layers
    *document* their own bans in Chinese comments, which would otherwise read as
    a locale leak and as a phantom ``class="sec"``."""
    stripped = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    return re.sub(r"<style>.*?</style>", "", stripped, flags=re.S)


def _classes(markup: str) -> set[str]:
    """Class tokens actually written into markup.

    The card template builds its badges by concatenation
    (``'pill rel-' + esc(r.rel) + '\"'``), so a bare scan of ``class="…"``
    captures JS syntax along with the names; the token pattern drops that noise,
    and the bucket suffixes live in ``_EMITTED`` where they are stated as the
    contract they are.
    """
    out: set[str] = set()
    for match in re.finditer(r'class="([^"]+)"', markup):
        out.update(tok for tok in match.group(1).split() if re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", tok))
    return out


@pytest.fixture(scope="module")
def bs():
    return _load()


@pytest.fixture(scope="module")
def built(bs):
    """``{lang: (model, l10n, html)}`` — one build pass, shared by every test."""
    out = {}
    for lang in ("zh", "en"):
        model, l10n = bs.build_data(lang)
        out[lang] = (model, l10n, bs.build_html(model, l10n))
    return out


# ---------------------------------------------------------------------------
# the portal composes the system instead of re-deriving it
# ---------------------------------------------------------------------------


def test_portal_owns_no_palette(bs) -> None:
    """Every colour is a token, and the portal's own layer declares none at all.
    The old portal carried its own oklch ramp, so the two surfaces drifted: the
    app's badge ink became ``--accent-ink`` while the portal's stayed ``#fff``,
    which is 2.35:1 on the dark accent.

    The scan is over *property values*, not raw substrings. ``--elev`` and
    ``--elev-lg`` are the ramp's two floating layers and they necessarily carry
    ``rgba()``: a shadow encodes height off the sheet, not a hue, so it has no
    oklch slot to sit in. Banning the literal there would only push the author to
    hide it. What stays banned is a colour written at the point of use.
    """
    css = _declarations(bs.CSS)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r":\s*(?:white|black|red|blue|gray|grey|navy|silver)\b", css)
    for value in _COLOR_PROPS.findall(css):
        value = value.strip()
        assert "var(--" in value or _COLOR_KEYWORDS.fullmatch(value), value

    chrome = _declarations(bs.CHROME)
    assert "oklch(" not in chrome, "CHROME places; the ramp lives in THEME_CSS"
    for value in re.findall(r"(?<![-\w])(?:color|background|border-color):\s*([^;}]+)", chrome):
        assert "var(--" in value, value


def test_radius_stays_on_the_ladder(bs) -> None:
    """``--r0``/``--r1``/``--r2`` and nothing else — ``999px`` pills are the
    rounded-chip look this register explicitly rejects.

    ``50%`` is the one permitted non-ladder value, and it is not the same
    decision: the ladder rounds *corners*, while ``50%`` appears only on fixed
    square marks (``.dot`` and the ``.status`` lamp are 8px and 7px), where it
    draws a circle. A pill needs a wide box plus a large radius, which this
    assertion still refuses.
    """
    for value in set(re.findall(r"border-radius:([^;}]+)", _declarations(bs.CSS))):
        assert value.strip() in {"var(--r1)", "var(--r2)", "50%"}, value


def test_no_elevation_and_no_sticky_machinery(bs) -> None:
    """Layer steps + 1px hairlines carry depth; ``box-shadow`` and the console's
    ``z-index`` ladder do not. ``--nav-h`` is absent on purpose: this portal has
    no routes and no in-page anchors, so a sticky bar would spend 56px of the
    column to offer nothing — and ``scroll-margin-top`` exists only to clear it."""
    css = _declarations(bs.CSS)
    for banned in ("box-shadow", "z-index", "--nav-h", "backdrop-filter", "scroll-margin-top"):
        assert banned not in css


def test_side_stripes_are_absent(bs) -> None:
    """Selection is a fill (``.chip.on``), never a coloured edge on a card."""
    css = _declarations(bs.CSS)
    assert "border-left:" not in css and "border-right:" not in css


def test_hidden_is_declared_once_by_the_shared_reset(bs) -> None:
    """``#rl``/``#res-empty`` toggle with ``el.hidden``. The ``!important`` lives in
    the ``COMPONENT_CSS`` reset because an author-level ``display:grid`` outranks
    the UA rule; a portal that re-declared it locally would diverge again."""
    assert "[hidden]" in _declarations(bs.COMPONENT_CSS)
    assert "[hidden]" not in _declarations(bs.CHROME)
    assert "[hidden]" not in _declarations(bs.RESOURCE_CSS)
    assert _declarations(bs.CSS).count("[hidden]") == 1


def test_card_appearance_is_imported_not_copied(bs) -> None:
    """The card is one object on two surfaces, so its CSS has exactly one author."""
    assert bs.RESOURCE_CSS in bs.CSS
    assert ".rcard" in bs.RESOURCE_CSS
    assert not re.search(r"\.rcard\s*\{", bs.CHROME), "CHROME may place, never redefine"


# ---------------------------------------------------------------------------
# nothing leaves the site
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ("zh", "en"))
def test_page_has_no_outbound_links(bs, built, lang) -> None:
    """GitHub URLs render as inert ``<code>``; only mirror files link, and they
    link relatively, so the artifact opens over ``file://`` and off the network."""
    html = built[lang][2]
    assert 'href="http' not in html and 'src="http' not in html
    base = "../../mirror/" if lang == "en" else "../mirror/"
    rows = [r for r in built[lang][0]["rows"] if r["files"]]
    assert rows, "the manifest has no mirrored repository, which is itself a regression"
    for row in rows:
        for f in row["files"]:
            assert f["href"].startswith(base), f["href"]
            assert not f["href"].startswith("/") and ".." not in f["href"].split(base)[1]


def test_static_regions_survive_a_js_free_open(built) -> None:
    """Double-clicking the file must still yield the masthead, all four metrics,
    the chip row, the live count and the discovery log. JS renders ``#rl`` only."""
    html = built["zh"][2]
    chrome = _chrome(html)
    assert '<div class="rl" id="rl"></div>' in html, "the card list is JS's job, not the file's"
    for marker in ("masthead", 'class="stats"', 'id="res-q"', 'id="res-count"', "qlist", "footer"):
        assert marker in chrome
    assert chrome.count('class="stat"') == 4


def test_theme_bootstraps_before_the_css_and_the_url_wins(built) -> None:
    """``html[data-theme]`` is the contract, ``localStorage`` the memory and
    ``?theme=`` the override; ``prefers-color-scheme`` is deliberately not the
    mechanism. The IIFE has to run before ``<style>`` or the first paint is
    wrong, and it is wrapped in ``try`` because ``file://`` blocks storage."""
    html = built["zh"][2]
    head = html.split("</head>")[0]
    assert head.index("<script>") < head.index("<style>")
    boot = re.search(r"<script>\(function\(\)\{.*?\}\)\(\);</script>", head, re.S).group(0)
    assert "localStorage" in boot and "URLSearchParams" in boot and "dataset.theme" in boot
    assert "try{" in boot


# ---------------------------------------------------------------------------
# escape responsibility, by trust boundary
# ---------------------------------------------------------------------------


def test_payload_is_minimal_and_neutralized(bs, built) -> None:
    """The payload is ``{l10n, rows}`` and ``l10n`` is the card's ten labels —
    anything server-rendered that also shipped would be escaped twice to be safe
    either way. The bare ``<`` swap is what stops a summary containing
    ``</script>`` from swallowing the portal."""
    raw = _payload_html(built["zh"][2])
    assert "<" not in raw
    data = json.loads(raw)
    assert set(data) == {"l10n", "rows"}
    assert set(data["l10n"]) == set(bs._CARD_KEYS)


def test_upstream_text_is_escaped_exactly_once(bs) -> None:
    """Storage keeps the raw string; ``esc()`` is its only escape point. Escaping
    in Python too is the double-escape bug (``A & B`` → ``A &amp;amp; B``), and
    not escaping at all is the injection."""
    from fde_scope.resources.repo import load_resources

    rec = load_resources()[0]
    evil = rec.model_copy(
        update={
            "repo": "<img src=x onerror=alert(1)>",
            "url": 'a"onmouseover="alert(1)',
            "summary_en": "R&D <script>alert(2)</script>",
            "upstream_description": "<b>bold</b> & <i>italics</i>",
        }
    )
    row = bs._row(evil, "../mirror/", True)
    assert row["repo"] == "<img src=x onerror=alert(1)>", "_row must not pre-escape"
    assert "R&D" in row["summary"]

    model, l10n = (
        {
            "lang": "en",
            "stats": {"total": 1, "core": 0, "adjacent": 0, "mirrored": 0},
            "queries": [],
            "note": "",
        },
        bs._l10n("en", {"total": 1, "core": 0, "adjacent": 0, "mirrored": 0}),
    )
    model["rows"] = [row]
    html = bs.build_html(model, l10n)
    assert "<img" not in html and 'onmouseover="' not in html
    assert "&amp;amp;" not in _payload_html(html)


def test_server_rendered_copy_never_rides_in_the_payload(bs, built) -> None:
    """Authored copy is escaped once, on the server side, with
    ``html.escape(quote=True)``. If a label also shipped in the payload it would
    exist on the page twice under two escape histories — which is exactly how the
    double-escape bug arrives, so the split is asserted rather than assumed."""
    _, l10n, html = built["zh"]
    payload = _payload_html(html)
    for key in ("docTitle", "mastH1", "mastP", "qHead", "qNote", "searchPh", "empty", "footer"):
        text = l10n[key]
        assert bs._esc(text) in _chrome(html), key
        assert text not in payload, key


# ---------------------------------------------------------------------------
# controls
# ---------------------------------------------------------------------------


def test_filters_are_buttons_with_a_pressed_state(bs, built) -> None:
    """A ``<span>`` with an ``onclick`` is unreachable from the keyboard and gets
    no focus ring. ``aria-pressed`` rather than ``role="radio"``: a radio group
    obliges the widget to implement arrow-key navigation, and these are
    independent one-of-N toggles — Tab is the honest interaction.

    The mirror chip is a Boolean filter, not a third axis, so it opens *off*:
    pressed would mean "mirrored only" and hide the 792 unmirrored rows before a
    reader has seen the catalogue at all."""
    _, l10n, html = built["zh"]
    assert 'role="radio"' not in html
    assert not re.search(r"<span[^>]*onclick=", html)
    pressed = re.findall(r'<button class="chip[^"]*" type="button" aria-pressed="(\w+)"', html)
    assert len(pressed) == len(l10n["chipLic"]) + len(l10n["chipRel"]) + 1
    assert pressed.count("true") == 2, "one pressed chip per axis — the two `all` chips"
    mirror = re.search(r'<button class="chip mir" type="button" aria-pressed="(\w+)"', html)
    assert mirror and mirror.group(1) == "false", "mirrored-only starts off"


def test_the_two_axes_never_merge(bs, built) -> None:
    """Licence and relevance are orthogonal: two independent chip groups, so a
    reader can ask "permissive AND unreviewed". Combined into one row it becomes
    an unreadable product of states."""
    html = built["zh"][2]
    assert re.search(r'data-lic="permissive"', html) and re.search(r'data-lic="none"', html)
    assert re.search(r'data-rel="core"', html) and re.search(r'data-rel="noise"', html)
    assert 'class="chip mir"' in html, "the Boolean reads as a different control (dashed edge)"


def test_every_class_the_page_emits_is_defined(bs, built) -> None:
    """A card emitted with an undefined class renders as unstyled text and nobody
    notices until a reader does — this portal has no build step to fail on.

    Checked in both directions: nothing in ``_EMITTED`` lacks a rule, and nothing
    on the page lacks an entry in ``_EMITTED``. The second half is what stops the
    contract from rotting quietly when someone adds a wrapper.
    """
    css = _declarations(bs.CSS)
    assert sorted(c for c in _EMITTED if f".{c}" not in css) == []
    used = _classes(_chrome(built["zh"][2])) | _classes(bs.JS)
    assert sorted(used - set(_EMITTED)) == []


# ---------------------------------------------------------------------------
# locale discipline
# ---------------------------------------------------------------------------


def test_english_chrome_keeps_the_source_language_out(bs, built) -> None:
    """The EN page is rendered from ``render('en')``, not a machine pass, so the
    only Chinese left on it is intentional: the language anchor's own label, and
    the two upstream fields a reader may need verbatim. ``?lang`` search
    haystacks are machine-read and carry the zh summary on purpose."""
    chrome = _chrome(built["en"][2]).replace('<a class="lang" href="../index.html">中文</a>', "")
    assert re.findall(r"[一-鿿]", chrome) == []
    assert [c for c in chrome if c in _FULLWIDTH] == []


def test_english_rows_leak_only_source_language_fields(bs, built) -> None:
    """Per field, not per page: ``decision``/``summary``/``reason`` are ours and
    so are translated (``_decision_for`` maps the clause, leaving the SPDX head
    alone); ``updesc`` is upstream and ``t`` is machine-read, so both may carry
    Chinese and are the only fields allowed to."""
    allowed = {"t", "updesc"}
    rows = built["en"][0]["rows"]
    leaked = [
        (row["repo"], key, value)
        for row in rows
        for key, value in row.items()
        if key not in allowed and isinstance(value, str) and re.search(r"[一-鿿]", value)
    ]
    assert leaked == []
    assert any(row["updesc"] for row in rows), "the exception is never exercised"


def test_snapshot_note_is_mapped_or_omitted_never_leaked(bs, built) -> None:
    """``harvest.py`` authors ``snapshot.yaml``'s note in Chinese and the in-app
    page never shows it, so this portal is its only English reader. The
    translation is a closed dictionary keyed by the stored string: an unmapped
    note is dropped here (``qNote`` already says the same in both languages) and
    fails this coverage guard, which is the loud version of the bug."""
    from fde_scope.resources.repo import load_snapshot

    snap = load_snapshot()
    assert snap and snap.note
    assert snap.note in bs._SNAPSHOT_NOTE_EN, "new harvest note without an English mapping"
    for note in bs._SNAPSHOT_NOTE_EN.values():
        assert re.search(r"[一-鿿]", note) is None
    assert bs._note_for("未映射的中文说明", True) == ""
    assert bs._note_for(snap.note, False) == snap.note
    assert bs._SNAPSHOT_NOTE_EN[snap.note] in built["en"][2]
    assert snap.note not in built["en"][2]
    assert snap.note in built["zh"][2]


# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------


def test_card_vocabulary_is_the_apps_not_a_reimplementation(bs, built) -> None:
    """The in-app page's card is ``<div class="card rcard">`` with ``.r-head`` /
    ``.r-meta`` / ``.r-decision``; the portal emits the same names minus the
    console's outer ``.card`` wrapper. Legacy names from the pre-rewrite portal
    must not survive, or two definitions of one object are back.

    Matched as whole class tokens, not substrings: the payload legitimately carries
    a ``"decision"`` field, which a ``'"dec'`` scan would flag forever."""
    html = built["zh"][2]
    for cls in ("rcard", "r-head", "r-url", "r-meta", "r-tags", "r-decision"):
        assert cls in bs.JS and cls in _declarations(bs.CSS)
    legacy = {"chead", "dec", "statbar", "cardlist"}
    assert not (_classes(_chrome(html)) | _classes(bs.JS)) & legacy
    for name in legacy:
        assert f".{name}" not in _declarations(bs.CSS)


def test_truncated_is_a_word_not_a_glyph(built) -> None:
    """``· 截断`` on the EN page is a locale leak the CJK guard cannot see, so the
    marker is the translated word and the label travels in the payload."""
    en = _payload_html(built["en"][2])
    zh = _payload_html(built["zh"][2])
    data_en, data_zh = json.loads(en), json.loads(zh)
    assert data_en["l10n"]["trunc"] == "truncated"
    assert re.search(r"[一-鿿]", data_zh["l10n"]["trunc"])
    assert "✂" not in built["en"][2] and "⚠" not in built["en"][2]

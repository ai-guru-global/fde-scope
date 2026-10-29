"""The shared app shell for the long-document pages.

Overview, certification and glossary all render as the same shape: a
sticky left sidebar carrying the site menu, and a scrolling article beside
it. Kept here rather than in ``app.py`` because ``certification.py`` and
``glossary.py`` are imported *by* ``app.py`` and cannot import back.

``THEME_CSS`` is the ramp, the theme contract, the two text primitives (``code``
and ``.ic``) and the three control primitives (``.tag``, ``.lang``, ``.tbtn``).
``COMPONENT_CSS`` is the component language every surface genuinely shares: the
document reset, the metrics row, section heads, tiles, filter chips, the list
indent, the footer. ``BASE_CSS`` is ``THEME_CSS + COMPONENT_CSS`` plus the
console's own chrome (``.hero``, ``.btn``, ``.logo``, ``.mk-*``, ``.note-list``).
These three cuts exist because the generated surfaces are real readers of the ramp
and were restating it: four duplicated token blocks in three files is how the
console and the portal drifted apart in the first place. A portal takes
``THEME_CSS``, ``COMPONENT_CSS`` and ``PROSE_CSS``, then its own chrome — never
``BASE_CSS``, which would hand it a second set of ``.hero``/``.btn`` rules to
fight. ``.chip`` is why the middle layer is not simply "the console": the same
control existed three times at three radii — 2px in the app, 6px in the resources
portal, 999px in the catalog — and a portal that only received the tokens had
nowhere correct to put it. ``GTM/i18n_split.py`` imports ``THEME_CSS`` for the
same reason: the marketing board has a language link and a theme toggle, so it
must be the same link and the same toggle, not a hand-restated lookalike.

``SHELL_CSS`` adds only the shell, the sidebar menu and the scroll spy. It
reads the elevation model from ``BASE_CSS`` — surfaces are distinguished by
``--bg`` → ``--panel`` → ``--panel2`` steps plus a hairline, never by shadow.

``PROSE_CSS`` is the article typography, shared by every surface that renders a
Markdown document: the three in-app long pages and the generated portals. It is
a separate constant, not part of ``BASE_CSS``: the console injects ``BASE_CSS``
and owns the ``.md`` class for its engagement-matrix grid, so a shared prose
block had to be renamed to ``.prose`` before it could be shared at all.

``side_nav`` exists because the rail was hand-copied onto eight pages. Every
one of them re-typed the same four bands, so any change to the menu was an
eight-file edit that silently drifted — and a collapsible rail cannot be
hand-copied at all, because the collapse needs a stable id per band. The nav is
also injected *after* ``to_en()`` (``app.py`` substitutes ``__SIDE_NAV__`` on
the built document), which takes the whole menu out of the exact-substring
translation pass that previously had to carry a key for every link.
"""

from html import escape
from typing import NamedTuple


class NavItem(NamedTuple):
    key: str
    path: str
    zh: str
    en: str
    #: Only needed where ``/en`` cannot simply prefix the zh path, i.e. the
    #: static sub-sites whose English lives beside the Chinese.
    en_path: str = ""


class NavBand(NamedTuple):
    key: str
    zh: str
    en: str
    items: tuple[NavItem, ...]


#: Four shelves, in reader order: learn the method, read the reference, run the
#: workbench, then the outward-facing site. ``external`` is last and alone
#: because leaving the app is a different kind of action than scrolling it.
NAV_BANDS: tuple[NavBand, ...] = (
    NavBand(
        "learners",
        "FDE 学习者",
        "FDE learners",
        (
            NavItem("overview", "/", "功能总览", "Overview"),
            NavItem("course", "/course", "入门课程", "Intro course"),
            NavItem("glossary", "/glossary", "名词解释", "Glossary"),
            NavItem("certification", "/certification", "认证中心", "Certification"),
            NavItem("showcase", "/showcase", "作品集登记", "Portfolio registry"),
        ),
    ),
    NavBand(
        "engineers",
        "FDE 工程师",
        "FDE engineers",
        (
            NavItem("sop", "/sop", "SOP 全文", "SOP full text"),
            NavItem(
                "catalog",
                "/catalog/index.html",
                "技能手册库",
                "Skills handbook",
                "/catalog/en/index.html",
            ),
            NavItem("docs", "/docs/readme", "仓库文档", "Repo docs"),
            NavItem("resources", "/resources", "GitHub 资源", "GitHub resources"),
        ),
    ),
    NavBand(
        "workbench",
        "FDE 工作台",
        "FDE workbench",
        (NavItem("console", "/console", "Engagement 控制台", "Engagement console"),),
    ),
    NavBand(
        "external",
        "外部",
        "External",
        (NavItem("gtm", "/GTM/index.html", "GTM 官网", "GTM site", "/GTM/en/index.html"),),
    ),
)


def _href(item: NavItem, en: bool) -> str:
    if not en:
        return item.path
    return item.en_path or "/en" + item.path


def side_nav(
    active: str = "",
    *,
    en: bool = False,
    subnav: tuple = (),
    views: tuple = (),
) -> str:
    """Build the four-band rail.

    ``active`` is a :attr:`NavItem.key`; pass ``""`` when no destination owns
    the highlight (``/docs/<slug>`` only lights up for ``readme``). ``subnav``
    is the expanded anchor list for the active row — a bare ``str`` renders a
    ``.sgrp`` caption, ``(href, label)`` renders a leaf, so a third level is
    possible without a second shape. ``views`` is the console's in-page view
    switcher, which shares the leaf slot but is a button, not a link.

    The expansion always ships open: collapse state is a preference restored
    by ``NAV_JS``, not something the document should hide when scripts fail.
    """
    collapse = escape("全部收起" if not en else "Collapse all", quote=True)
    expand = escape("全部展开" if not en else "Expand all", quote=True)
    # Label first, mark last: the row shares the band headers' grid (label on
    # the gutter, mark pushed to the far edge), and the tree ships open, so the
    # mark is the "collapse everything" glyph. ``NAV_JS`` repaints it from the
    # restored preference; a document without scripts keeps every band open,
    # which is the state this markup actually represents.
    #
    # No ``aria-expanded`` here on purpose. It is not one disclosure's toggle
    # but four, and a disclosure state with no single controlled region is a
    # relation assistive tech would have to invent. The per-band buttons carry
    # the real relation (``aria-controls`` -> ``.rows``); this one is a plain
    # action that relabels itself.
    out: list[str] = [
        '<div class="navtools">'
        '<button class="tall" type="button" '
        f'data-collapse="{collapse}" data-expand="{expand}">'
        f'<span class="lbl">{collapse}</span>'
        '<svg class="ic cv" aria-hidden="true"><use href="#i-collapse"/></svg>'
        "</button></div>"
    ]
    for band in NAV_BANDS:
        keys = {item.key for item in band.items}
        has_active = active in keys
        out.append(
            f'<section class="sec{" has-active" if has_active else ""}">'
            f'<button class="grp" type="button" aria-expanded="true" '
            f'data-nav="{band.key}" aria-controls="nav-{band.key}">'
            f'<span class="lbl">{escape(band.en if en else band.zh)}</span>'
            '<svg class="ic cv" aria-hidden="true"><use href="#i-chev"/></svg>'
            "</button>"
            f'<div class="rows" id="nav-{band.key}">'
        )
        for item in band.items:
            cls = ' class="active"' if item.key == active else ""
            out.append(
                f'<a href="{escape(_href(item, en), quote=True)}"{cls}>'
                f"{escape(item.en if en else item.zh)}</a>"
            )
            if item.key != active or not (subnav or views):
                continue
            out.append('<div class="subnav">')
            for entry in subnav:
                if isinstance(entry, str):
                    out.append(f'<div class="sgrp">{escape(entry)}</div>')
                else:
                    href, label = entry
                    out.append(f'<a href="{escape(href, quote=True)}">{escape(label)}</a>')
            for i, (key, label) in enumerate(views):
                out.append(
                    f'<button class="navbtn{" active" if i == 0 else ""}" '
                    f'type="button" data-view="{key}" onclick="go(\'{key}\')">'
                    f"{escape(label)}</button>"
                )
            out.append("</div>")
        out.append("</div></section>")
    return "\n".join(out)


#: Band disclosure. ``aria-expanded`` is the single source of truth: the CSS
#: selector that hides the rows and the state an assistive tech reads are the
#: same attribute, so they cannot disagree. Storage holds *collapsed* keys, so
#: a fresh visitor sees the whole tree; the band carrying the current page is
#: forced open regardless, because a rail that hides where you are is a worse
#: rail than one that hides the rest.
NAV_JS = """
(function(){
  var nav = document.querySelector('.snav');
  if (!nav) return;
  var groups = Array.prototype.slice.call(nav.querySelectorAll('.grp'));
  if (!groups.length) return;
  var KEY = 'fde-nav-collapsed', store = {};
  try { store = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { store = {}; }
  function persist(){ try { localStorage.setItem(KEY, JSON.stringify(store)); } catch (e) {} }
  function anyOpen(){
    return groups.some(function(g){ return g.getAttribute('aria-expanded') === 'true'; });
  }
  var toggle = nav.querySelector('.tall');
  /* The master row reflects the tree without claiming a disclosure relation it
     cannot honour: it changes the glyph and the label, never ``aria-expanded``. */
  function paint(){
    if (!toggle) return;
    var open = anyOpen(), use = toggle.querySelector('use'), lbl = toggle.querySelector('.lbl');
    if (use) use.setAttribute('href', open ? '#i-collapse' : '#i-expand');
    if (lbl) lbl.textContent = open ? toggle.dataset.collapse : toggle.dataset.expand;
  }
  function set(g, open, keep){
    g.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (keep) { if (open) delete store[g.dataset.nav]; else store[g.dataset.nav] = 1; persist(); }
    paint();
  }
  groups.forEach(function(g){
    var forced = g.parentNode && g.parentNode.classList.contains('has-active');
    set(g, forced ? true : !store[g.dataset.nav], false);
    g.addEventListener('click', function(){
      set(g, g.getAttribute('aria-expanded') !== 'true', true);
    });
  });
  if (toggle) toggle.addEventListener('click', function(){
    var open = !anyOpen();
    groups.forEach(function(g){
      g.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) delete store[g.dataset.nav]; else store[g.dataset.nav] = 1;
    });
    persist(); paint();
  });
  paint();
})();
"""

#: Marks the section link whose target is currently on screen. The spy
#: below writes this class; page-level links (which carry ``active`` for
#: "you are here") are left alone.
SPY_JS = """
(function(){
  var links = document.querySelectorAll('.snav a[href^="#"]');
  if (!links.length || !('IntersectionObserver' in window)) return;
  var byId = {};
  links.forEach(function(a){
    var el = document.getElementById(a.getAttribute('href').slice(1));
    if (el) byId[el.id] = a;
  });
  var spy = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if (!e.isIntersecting) return;
      links.forEach(function(a){ a.classList.remove('on'); });
      if (byId[e.target.id]) byId[e.target.id].classList.add('on');
    });
  }, {rootMargin: '-8% 0px -70% 0px'});
  Object.keys(byId).forEach(function(id){ spy.observe(document.getElementById(id)); });
})();
"""

#: What every shell page drops in before ``</body>``. The spy is inert on a
#: page whose rail has no in-page anchors (the console switches views with
#: buttons), so one constant serves all seven long-document pages, and
#: ``app.py`` gives the console ``NAV_JS`` alone.
SHELL_JS = NAV_JS + SPY_JS

#: Workbench ramp. Structural discipline, not a font swap: the type stays
#: ``-apple-system`` + CJK (zero webfonts is a hard requirement for an
#: air-gapped install), while elevation, density, radius and state colors
#: follow a layer model. Three rules below are load-bearing and were
#: measured (WCAG relative luminance straight from OKLCH), not eyeballed:
#:
#: * Each state is a **dot / ink / fill triad**. One hue cannot be both
#:   legible at 12px and vivid as a marker — the ink role carries text
#:   (≥4.5:1 on every layer and on its own fill), the dot role carries
#:   8-16px marks (≥3:1 on ``--layer-02``, the tightest surface a mark
#:   sits on: 0.575/0.595/0.615 in light).
#: * **Selection is fill + ink, never fill + accent.** ``--accent`` on
#:   ``--layer-accent`` measures 4.00:1 light / 3.96:1 dark — under AA at
#:   body size in both themes — so a selected surface takes ``--fg``
#:   (13.5:1 / 8.49:1) and accent stays on marks, badges and rules only.
#: * **The selection step is the same size in both themes.** ``--layer-accent``
#:   is one quiet move off the surface it sits on (light ``--panel`` 1.0 →
#:   0.908; dark ``--bg2`` 0.269 → 0.40) plus hue. It first measured 0.48/0.134
#:   in dark, which is four steps and full chroma: the same "you are here"
#:   signal read as a tint in light and a spotlight in dark, so the two themes
#:   were not the same design. Dark's hover is ``--layer-02`` (0.345), so
#:   selection has to clear that floor — 0.40 with C 0.11 is the lowest step
#:   that beats both hover and the neutral ``--layer-03`` without shouting.
#: * **Accent-as-text uses ``--accent-text``, never ``--accent``, below the large
#:   text bar.** Plain ``--accent`` clears 4.5:1 on ``--bg`` and ``--layer-01`` but
#:   fails on the raised surfaces text actually lands on: 4.28 light on
#:   ``--layer-02``, 3.32 dark on ``--layer-03``, and 3.73–4.14 on its own
#:   ``--accent-dim`` wash. ``--accent-text`` is the step that clears 4.5:1 on every
#:   neutral layer in its theme (5.01–6.15 light, 4.91–8.41 dark). ``--accent-2`` and
#:   ``--accent-3`` are the button *fill* ramp and must not be reused as text.
#:   WCAG 1.4.11's 3:1 bar applies at ≥24px bold, so ``--accent`` survives on the
#:   one display figure that carries it (``.kpi .v`` at ``--fs-num``/700) and
#:   nowhere else; the overview's ``.stat .num`` is 20px and takes ``--fg``.
#:   On an ``--accent-dim`` wash even ``--accent-text`` fails (4.36 light on
#:   ``--layer-02``), so a tinted label takes ``--fg`` and lets the wash carry
#:   the hue. On a filled ``--accent`` surface the ink is ``--accent-ink``
#:   (5.12 light / 6.41 dark); white is 2.35 in dark and never correct.
#: * The border ladder is ``--border`` (subtle) → ``--border-strong``
#:   (component boundary: fields, toasts — ≥3:1 per 1.4.11) →
#:   ``--border-ink`` (emphasis: hover, selected, ghost button).
#:   Anything lighter than 0.62 L in light cannot mark a field.
#: * **A case transform may not reach copy that quotes an identifier.**
#:   ``.stat .lab`` was uppercase until measured against the real labels, which
#:   quote live tokens (``可执行 gate`` rendered ``GATE``, ``4 zones`` rendered
#:   ``ZONES``): the transform invents acronyms the product never uses. Metric
#:   labels are sentence case, as in Carbon; uppercase stays on surfaces whose
#:   text is a pure label — ``.eyebrow``, ``.ztag``, ``.sec-head .n``.
THEME_CSS = """/* Hallmark · design-system: DESIGN.md (Workbench) · ramp + theme contract + text
   and control primitives; COMPONENT_CSS layers the shared components on top and
   BASE_CSS the console's own chrome, while a generated page composes its own
   sheet from these constants plus the page chrome it authors locally. */
:root{
--bg:oklch(0.967 0.004 258);--bg2:oklch(1 0 0);--panel:oklch(1 0 0);--panel2:oklch(0.931 0.004 258);
--layer-01:oklch(1 0 0);--layer-02:oklch(0.931 0.004 258);--layer-03:oklch(0.87 0.004 258);
--fg:oklch(0.21 0.006 258);--muted:oklch(0.44 0.006 258);--faint:oklch(0.5 0.006 258);
--border:oklch(0.902 0.004 258);--border-strong:oklch(0.62 0.006 258);--border-ink:oklch(0.52 0.006 258);
--accent:oklch(0.545 0.243 262);--accent-2:oklch(0.509 0.236 262);--accent-3:oklch(0.454 0.221 262);--accent-ink:oklch(0.99 0.002 258);--accent-dim:oklch(0.545 0.243 262/0.1);
--accent-text:oklch(0.509 0.236 262);
--layer-accent:oklch(0.908 0.044 260);--layer-accent-hover:oklch(0.86 0.06 260);
--good:oklch(0.429 0.117 148);--good-dot:oklch(0.575 0.166 148);--good-fill:oklch(0.93 0.05 152);
--warn:oklch(0.439 0.09 86);--warn-dot:oklch(0.595 0.132 85);--warn-fill:oklch(0.955 0.07 95);
--bad:oklch(0.46 0.171 26);--bad-dot:oklch(0.615 0.209 22);--bad-fill:oklch(0.925 0.045 18);
--code:oklch(0.955 0.004 258);
/* Elevation exists for the two layers that actually float over the page: the
   toast and the modal. Everything that merely sits in the layout is separated by
   a hairline, never by a shadow. They are tokens rather than per-rule literals
   because the dark ramp needs roughly twice the black of the light one for the
   same perceived lift — a hard-coded ``rgba(0,0,0,.35)`` reads as dirt on white
   and vanishes on charcoal, so the value has to be a property of the theme.
   ``--z-sticky``/``--z-toast`` are the semantic scale: a sticky bar must never
   out-rank a toast, and both numbers had to stop being page-local (the console
   said 60, the catalogue said 20) before a generated surface could disagree. */
--elev:0 8px 24px rgba(0,0,0,.16);--elev-lg:0 24px 64px rgba(0,0,0,.22);
--z-sticky:60;--z-toast:70;
--r0:0;--r1:2px;--r2:4px;
--fs-body:.9375rem;--fs-sm:.875rem;--fs-xs:.75rem;--fs-h4:1rem;--fs-h3:1.125rem;--fs-h2:1.25rem;--fs-num:1.7rem;--fs-display:2rem;
/* Three tracking jobs, not five magic numbers. ``--track-kicker`` is the
   uppercase mono eyebrow; ``--track-label`` is the uppercase mono micro-label
   (table headers, counters, the language toggle); ``--track-tight`` is the
   optical correction on display and heading type. Sentence-case labels carry 0
   tracking in either language: widening a bold 14px Chinese or English label
   buys nothing and breaks Chinese the most. */
--track-kicker:.14em;--track-label:.08em;--track-tight:-.01em;
--sp1:4px;--sp2:8px;--sp3:16px;--sp4:24px;--sp5:32px;--sp6:48px;
--ease:cubic-bezier(0.2,0,0.38,0.9);--dur:110ms;
--font:-apple-system,"SF Pro Text","Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
--mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;color-scheme:light}
html[data-theme="dark"]{
--bg:oklch(0.2 0.004 258);--bg2:oklch(0.269 0.004 258);--panel:oklch(0.269 0.004 258);--panel2:oklch(0.345 0.004 258);
--layer-01:oklch(0.269 0.004 258);--layer-02:oklch(0.345 0.004 258);--layer-03:oklch(0.439 0.004 258);
--fg:oklch(0.967 0.004 258);--muted:oklch(0.827 0.004 258);--faint:oklch(0.72 0.005 258);
--border:oklch(0.39 0.004 258);--border-strong:oklch(0.55 0.005 258);--border-ink:oklch(0.66 0.005 258);
--accent:oklch(0.736 0.136 261);--accent-2:oklch(0.828 0.086 260);--accent-3:oklch(0.68 0.15 261);--accent-ink:oklch(0.28 0.14 263);--accent-dim:oklch(0.736 0.136 261/0.14);
--accent-text:oklch(0.736 0.136 261);
--layer-accent:oklch(0.40 0.11 262);--layer-accent-hover:oklch(0.45 0.115 262);
--good:oklch(0.77 0.13 152);--good-dot:oklch(0.7 0.14 152);--good-fill:oklch(0.31 0.06 152);
--warn:oklch(0.87 0.11 86);--warn-dot:oklch(0.84 0.13 85);--warn-fill:oklch(0.36 0.07 85);
--bad:oklch(0.8 0.14 26);--bad-dot:oklch(0.73 0.16 22);--bad-fill:oklch(0.32 0.08 22);
--code:oklch(0.145 0.004 258);
--elev:0 8px 24px rgba(0,0,0,.5);--elev-lg:0 24px 64px rgba(0,0,0,.62);
color-scheme:dark}
/* CJK is a monospaced-by-nature script: every Han glyph already occupies an em
   square, so any positive tracking reads as a broken word and any negative
   tracking collides the ideographs. Both directions go to 0 for zh, and the
   uppercase kickers lose their Latin spacing crutch entirely — which is why the
   kickers are the one place the zh UI should prefer a shorter Chinese label over
   a spaced one. ``html:lang(zh)`` is (0,1,1) against ``:root`` (0,1,0) on the
   same element, so the flip wins and cascades to the whole subtree; the theme
   block sets no tracking, so light and dark can't drift apart here. */
html:lang(zh){--track-kicker:0;--track-label:0;--track-tight:0}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:var(--r1)}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition-duration:0.01ms!important;scroll-behavior:auto!important}}
/* Theme primitives rather than components: a surface that carries the ramp swaps
   these two classes to branch on the applied theme, so it never has to read
   ``prefers-color-scheme`` (which is not the app's mechanism and would let the OS
   override a choice the reader made in the UI). They live here, not below,
   because a generated portal needs the theme contract without the console's
   component language. */
.when-dark{display:none}
html[data-theme="dark"] .when-light{display:none}
html[data-theme="dark"] .when-dark{display:inline}
/* One inline-code chip for every surface that renders text, authored here
   because both the app and the generated portals need it. Each page used to copy
   its own and none agreed: the auth cards took ``.85em`` on ``--code``, the
   console ``.82em`` on ``--layer-02``, the prose article ``--fs-xs``, the resource
   rows ``.8em`` — which on a 12px meta line rendered a GitHub URL at 9.6px.
   ``max()`` keeps the chip a step below its own text in prose and floors it at
   ``--fs-xs`` in dense rows, so a machine string is never the smallest thing on
   the page. */
code{font-family:var(--mono);font-weight:500;font-size:max(.85em,var(--fs-xs));
background:var(--code);border:1px solid var(--border);border-radius:var(--r1);
padding:1px 5px;overflow-wrap:anywhere}
/* The icon box is a size and a stroke contract, not a component, so it belongs
   with the chip: any surface carrying the ramp can drop an inline ``<svg>`` in
   and get 16px line art that inherits the surrounding color. */
.ic,.ic-xs{fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;flex:none}
.ic{width:16px;height:16px}.ic-xs{width:13px;height:13px}
/* Three control primitives rather than components: a tag, a language link and a
   square icon button. They travel with the ramp because the app and the generated
   portals place them in different chrome (the side-foot and the article header vs
   the app bar) but must not disagree about what one looks like — the old system
   had the portal's ``.lang`` at 999px while the console's was at 2px, which is
   the same control rendered as two different objects. Placement stays with the
   page; only the appearance is canonical here.

   No pills anywhere: 999px was the single most "generated" thing in the old
   system. ``.tag``'s ink is ``--fg`` rather than ``--accent``, because on its own
   wash the accent measures 3.73:1 on ``--layer-02`` and 4.14:1 on ``--bg``, and
   even the text step ``--accent-text`` fails there (4.36:1). The wash carries the
   hue; the ink carries the readability. */
.tag{font:600 var(--fs-xs)/1.5 var(--mono);color:var(--fg);background:var(--accent-dim);
padding:4px 8px;border-radius:var(--r1);white-space:nowrap}
.lang{font:600 var(--fs-xs)/1 var(--mono);letter-spacing:var(--track-label);color:var(--muted);
border:1px solid var(--border-ink);border-radius:var(--r1);padding:8px 10px;
transition:color var(--dur) var(--ease),background-color var(--dur) var(--ease)}
.lang:hover{color:var(--fg);background:var(--panel2)}
.tbtn{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:var(--r1);
border:1px solid var(--border-ink);background:transparent;color:var(--muted);cursor:pointer;
transition:color var(--dur) var(--ease),background-color var(--dur) var(--ease)}
.tbtn:hover{color:var(--fg);background:var(--panel2)}
/* Two static marks: a status dot and a secondary-text step. They live here rather
   than in the console because the lab table on ``/course`` and the gate list in
   the console report the same fact — passed, failed, waiting, not-yet-evaluated —
   and one system cannot afford two vocabularies for it. Emoji is not a substitute:
   ✅❌✋⏳💡 render in whatever font the OS happens to pick, inherit no ink from the
   ramp, and reach a screen reader as a glyph name rather than as state. The dot is
   a graphic, so its fills are the 3:1 ``--*-dot`` steps rather than ``--*-fill``
   (the fill steps are washes behind text and read as mud at 8px); the undecorated
   ``--faint`` default is the "no verdict yet" arm. ``--faint`` is allowed there
   because the dot carries no reading text — it is the one role lightness is for. */
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--faint);vertical-align:1px}
.d-ok{background:var(--good-dot)}
.d-warn{background:var(--warn-dot)}
.d-bad{background:var(--bad-dot)}
.hint{color:var(--muted);font-size:var(--fs-xs)}
/* One canonical field for every surface — console, long-document pages and the
   generated portals all render the same control, so it travels with the ramp
   rather than with the console's components. The well is ``--code`` (an inset
   layer, so a field reads as editable before it is focused), the boundary is
   ``--border-strong`` because a control edge is a graphic and must clear 3:1,
   and the corner is ``--r1``. ``width:100%`` is the productive default; a page
   narrows it for a specific slot, which is placement and stays local. Checkboxes
   and radios opt out below rather than at every call site.
   No ``outline:none`` anywhere in this rule: the site focus ring must survive, or
   a keyboard user gets a 1px border as their only confirmation. */
input,select,textarea{background:var(--code);border:1px solid var(--border-strong);color:var(--fg);
padding:8px 12px;border-radius:var(--r1);font:400 var(--fs-sm)/1.5 var(--font);width:100%;
transition:border-color var(--dur) var(--ease)}
input[type=checkbox],input[type=radio]{width:auto;flex:none;padding:0;margin:0}
input:focus,select:focus,textarea:focus{border-color:var(--accent)}
input::placeholder,textarea::placeholder{color:var(--muted)}
textarea{resize:vertical;line-height:1.5}
"""

#: The component language every surface shares, on top of the ramp: the document
#: reset, the metrics row, section heads, tiles, filter chips, the inherited list
#: indent and the footer. A generated portal composes ``THEME_CSS + COMPONENT_CSS
#: + PROSE_CSS`` and then adds only the chrome it truly owns — its masthead, its
#: zone bands, its article shell — and ``app.py`` plus every in-app page inject
#: ``BASE_CSS``, which is this block plus the console's own chrome. The split
#: point is use, not origin: a component is shared when two surfaces render the
#: same object and were disagreeing about it (``.chip`` existed at 2px, 6px and
#: 999px), and stays console-only when the portal's version is a different
#: thing (``.hero`` is a gradient banner there and a type block here).
COMPONENT_CSS = (
    THEME_CSS
    + """
*{box-sizing:border-box}
html,body{overflow-x:clip}
body{margin:0;font:400 var(--fs-body)/1.7 var(--font);background:var(--bg);color:var(--fg)}
a{color:var(--accent-text);text-decoration:none}
/* Every filtered list on every surface hides by setting ``el.hidden``, and the
   filtered containers are flex or grid — an author-level ``display:flex``
   outranks the UA's ``[hidden]{display:none}`` regardless of specificity, so the
   attribute would be ignored and the hidden cards would stay on the page. This
   lives in the shared reset rather than at each call site because it is a
   property of the hiding mechanism, not of any one card. */
[hidden]{display:none!important}
/* metrics read label-then-value, the way a workbench states a field: the
   number is not a hero, it is the value of the named dimension. */
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--border);
border:1px solid var(--border);border-radius:var(--r1);overflow:hidden}
.stat{background:var(--bg2);display:flex;flex-direction:column;padding:var(--sp3)}
.stat .lab{order:-1;margin:0 0 var(--sp1);color:var(--muted);
font-size:var(--fs-xs);letter-spacing:var(--track-label)}
.stat .num{font-size:var(--fs-h2);font-weight:650;line-height:1.2;letter-spacing:var(--track-tight);color:var(--fg)}
/* The anchor rhythm lives in ``SHELL_CSS`` on ``.main section``, not here on the
   bare element: as a global it also reached the rail's ``<section class="sec">``
   bands, where 48px of top padding opened a hole between the collapse control
   and the first shelf. A band is a row, not a chapter. */
.sec-head{display:flex;align-items:center;gap:var(--sp2);padding-bottom:var(--sp2);
border-bottom:1px solid var(--fg);margin-bottom:var(--sp2)}
.sec-head .ic{color:var(--accent)}
.sec-head h2{margin:0;font-size:var(--fs-h2);font-weight:650;letter-spacing:var(--track-tight);
text-wrap:balance;min-width:0;overflow-wrap:anywhere}
.sec-head .n{font:600 var(--fs-xs)/1 var(--mono);color:var(--muted);margin-left:auto;letter-spacing:var(--track-label)}
.sec-note{font-size:var(--fs-sm);color:var(--muted);margin:0 0 var(--sp3);line-height:1.7;max-width:820px}
/* One inherited list indent for every surface. The UA's 40px is sized for a prose
   column and pushes a bullet past its own label inside a dense card or table cell,
   which is why call sites kept hand-writing ``18px``/``1.1rem``/``22px`` and none of
   them agreed. 24px is the same step ``--sp4`` uses everywhere else, and it matches
   ``.prose``'s 1.5em at body size, so a list in a document and a list in a console
   card finally line up. ``.prose`` and ``.md`` keep their own rules and win on
   specificity. */
ul,ol{padding-left:var(--sp4)}
.grid{display:grid;gap:var(--sp2)}
.cols-4{grid-template-columns:repeat(4,minmax(0,1fr))}
.cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}
.cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}
.tile{background:var(--panel);border:1px solid var(--border);border-radius:var(--r1);
padding:var(--sp3);min-width:0;transition:border-color var(--dur) var(--ease),background-color var(--dur) var(--ease)}
.tile:hover{border-color:var(--border-ink);background:var(--layer-02)}
.tile>.ic{color:var(--muted);margin-bottom:var(--sp2)}
.tile .name{font-weight:600;font-size:var(--fs-body);margin-bottom:var(--sp1);
overflow-wrap:anywhere;min-width:0;display:flex;align-items:center;gap:var(--sp2);flex-wrap:wrap}
.tile.mono .name{font:600 var(--fs-sm)/1.55 var(--mono)}
.tile .desc{color:var(--muted);font-size:var(--fs-sm);line-height:1.6}
.tile .desc a{white-space:nowrap}
/* Filter chips are controls, not capsules: a 2px corner, a ``--border-strong``
   boundary and a ``--layer-01`` fill, so an unselected chip reads as pressable
   rather than as a label. 999px is the banned pill. The resting ink is
   ``--muted``, not ``--faint``, which fails AA at this size, and the selected
   state is a filled ``--accent`` carrying ``--accent-ink`` (5.12 light /
   6.41 dark) — never white, which measures 2.35:1 in dark. This is the shared
   layer's reason to exist: the same control was authored at 2px here, 6px in
   the resources portal and 999px in the catalog, and only the last of the three
   was mistaken for a design decision. */
.chip{font:600 var(--fs-xs)/1.5 var(--mono);padding:4px 11px;border-radius:var(--r1);
cursor:pointer;user-select:none;border:1px solid var(--border-strong);
background:var(--layer-01);color:var(--muted);transition:background-color var(--dur) var(--ease),
border-color var(--dur) var(--ease),color var(--dur) var(--ease)}
.chip:hover{border-color:var(--border-ink);color:var(--fg)}
.chip.on{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.chip-lbl{font:600 var(--fs-xs)/1.5 var(--mono);color:var(--muted);align-self:center;margin-right:var(--sp1)}
footer{margin-top:var(--sp6);padding:var(--sp4) 0 var(--sp2);border-top:1px solid var(--border);
color:var(--muted);font-size:var(--fs-sm);display:flex;justify-content:space-between;gap:var(--sp2);flex-wrap:wrap}
"""
)

#: The console's own chrome on top of the shared components: the hero, the two
#: button variants, the wordmark, the status marks and the reference-prose list.
#: Nothing here is a token, and none of it is a portal's vocabulary — the
#: catalog's masthead is a band with its own metrics row, not a centred gradient
#: banner, which is exactly why the two sets are not merged into one block.
BASE_CSS = (
    COMPONENT_CSS
    + """
/* Marks are graphics, not text: 3:1 is the bar and ``--accent`` clears it on
   every layer, so these keep the saturated accent that links had to give up. */
.mk-g{color:var(--accent)}.mk-w{color:var(--warn)}
.logo{font-size:var(--fs-h4);font-weight:650;letter-spacing:var(--track-tight)}
.logo span{color:var(--accent-text)}
.hero{padding:var(--sp2) 0 var(--sp5);max-width:800px}
.hero .eyebrow{font:600 var(--fs-xs)/1.5 var(--mono);letter-spacing:var(--track-kicker);text-transform:uppercase;color:var(--muted);margin:0 0 var(--sp3)}
.hero h2{font-size:var(--fs-display);font-weight:650;letter-spacing:var(--track-tight);line-height:1.2;
margin:0 0 var(--sp2);text-wrap:balance;overflow-wrap:anywhere;min-width:0}
.hero p{color:var(--muted);font-size:var(--fs-body);margin:0;max-width:68ch}
.hero .cta{margin-top:var(--sp4);display:flex;gap:var(--sp2);flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:var(--sp2);
background:var(--accent);color:var(--accent-ink);border:1px solid transparent;
padding:9px 16px;border-radius:var(--r1);font-weight:600;font-size:var(--fs-sm);font-family:inherit;
text-decoration:none;cursor:pointer;transition:background-color var(--dur) var(--ease)}
.btn:hover{background:var(--accent-2)}
.btn:active{background:var(--accent-3)}
.btn.ghost{background:transparent;border-color:var(--border-ink);color:var(--fg)}
.btn.ghost:hover{background:var(--panel2);border-color:var(--fg)}
/* Reference prose — the notice lists, the acceptance criteria. A step down and one
   tone lighter than the control text around it, so the bullets carry the scan. */
.note-list{margin:var(--sp1) 0 0;font-size:var(--fs-sm);line-height:1.8;color:var(--muted)}
"""
)

#: The centred single-panel page: the six "this asset is not in your install"
#: notices (three portals × two locales) and the stakeholder sign-off receipt in
#: ``share.py``. The island was copy-pasted six times and two of the copies had
#: drifted — the resources notice closed its ``h1`` at 2px while the others used
#: 12px, so the heading sat on the first paragraph there and nowhere else.
#: Single-sourcing it is how that class of drift stops recurring, and putting it
#: here rather than in ``app.py`` is what lets the receipt page take the same sheet
#: instead of authoring a third centred panel.
#: The panel is ``.notice``, not ``.card``: the console's ``.card`` is a dense
#: ``--layer-01`` panel at ``--r1`` inside a working grid, while this is a centred
#: ``--panel`` sheet at ``--r2``. One name cannot mean both.
NOTICE_CSS = (
    BASE_CSS
    + """
.main{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:var(--sp6) var(--sp4)}
.notice{background:var(--panel);border:1px solid var(--border);border-radius:var(--r2);
padding:var(--sp4);max-width:600px}
.notice .brand{display:flex;align-items:center;gap:var(--sp2);flex-wrap:wrap;margin-bottom:var(--sp3)}
.notice h1{margin:0 0 var(--sp2);font-size:var(--fs-h2);font-weight:650;letter-spacing:var(--track-tight)}
.notice p{margin:0 0 var(--sp2);color:var(--muted);font-size:var(--fs-body)}
.notice .cta{margin:var(--sp4) 0 0;display:flex;gap:var(--sp2);flex-wrap:wrap}
"""
)

SHELL_CSS = """
.shell{display:grid;grid-template-columns:250px minmax(0,1fr);align-items:start}
.side{position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column;
padding:var(--sp4) var(--sp3) 0;border-right:1px solid var(--border);background:var(--bg2)}
/* The rail is one gutter wide: brand, every row and the foot block all bleed to
   the rail edges and start their content at ``--sp3``, so the whole column has
   exactly one label edge at x=16. The brand used to sit 8px further in than the
   rows beneath it, which is the kind of misalignment nobody can name but
   everybody sees. */
.side .brand{display:flex;flex-direction:column;align-items:flex-start;gap:var(--sp2);
margin:0 calc(-1 * var(--sp3));padding:0 var(--sp3) var(--sp3);border-bottom:1px solid var(--border)}
/* the rail is 250px: tags that fit a full-width header must wrap here */
.side .brand .tag{white-space:normal;line-height:1.5;text-align:left}
.snav{display:flex;flex-direction:column;margin:0 calc(-1 * var(--sp3));padding-bottom:var(--sp3)}
/* Full-bleed rows, at every level. Indenting the *box* instead (the old
   ``padding-left`` on ``.subnav``) made each level's hover and selection fill a
   different width from the row above it, so the rail read as three unaligned
   lists. A slab always spans the rail; only where its label starts says which
   level it is. */
.snav .navtools{border-bottom:1px solid var(--border)}
/* The rail-wide control obeys the same two-column grid as the bands it acts on:
   label at the gutter, mark at the right edge. It used to sit alone at the right
   over its own dead space, aligned with nothing, where it read as a caption
   rather than a button. It deliberately carries no ``aria-expanded``: it is not
   one disclosure's toggle but all four, and a disclosure relation with no
   controlled region is a state an assistive tech would invent. */
.snav .tall{display:flex;align-items:center;gap:var(--sp2);width:100%;text-align:left;
background:transparent;border:0;cursor:pointer;font-family:inherit;
font-weight:600;font-size:var(--fs-xs);line-height:1.3;letter-spacing:var(--track-label);
text-transform:uppercase;color:var(--muted);padding:6px var(--sp3);
transition:color var(--dur) var(--ease),background-color var(--dur) var(--ease)}
.snav .tall:hover{color:var(--fg);background:var(--layer-02)}
.snav .tall .lbl{min-width:0;overflow-wrap:anywhere}
/* 16px, not the tree's 14: the mark is two chevrons in a 16-unit viewBox, and
   at 14 the pair closes into what reads as an asterisk. It is the only glyph on
   the row, so it has to be legible on its own. */
.snav .tall .cv{margin-left:auto;flex:none;width:16px;height:16px}
/* Four shelves rather than one long list. The division is a full-width hairline
   *above* each band, never a coloured stripe down its side; the first band is
   divided from the control row by the rule under ``.navtools``. */
.snav .sec{display:flex;flex-direction:column}
.snav .sec+.sec{border-top:1px solid var(--border);margin-top:var(--sp2);padding-top:var(--sp1)}
/* Contiguous rows: the separation between items is the fill, so a gap would be
   whitespace paid for twice. 30px rows against the 18px label is the density a
   workbench rail is read at. */
.snav .rows{display:flex;flex-direction:column}
/* A rail item is a rail item whether the router emitted a link or a button:
   the console switches its views with <button class="navbtn">, and the two
   must not grow separate selection languages. The button branch carries only
   what the UA defaults force on it (chrome border, a font that is not the
   page's) — and one of those defaults has to be *undone*: Blink sets
   ``justify-content:center`` on ``<button>``, which is inert while the element
   is ``inline-block`` but becomes live the moment the shared rule above makes it
   a flex container. It then centres the stub-and-label group, so every button
   row's text starts at a different column, one that moves with the label's
   width — the longest item in a list drifts furthest left, and the tree stops
   having a left edge. Links have no such default, which is why the mismatch
   only ever appeared where a button sat beside an anchor. */
.snav a,.snav .navbtn{display:flex;align-items:center;gap:var(--sp2);color:var(--muted);
font-size:var(--fs-sm);line-height:1.3;text-align:left;padding:6px var(--sp3);
border-radius:var(--r0);overflow-wrap:anywhere;
transition:color var(--dur) var(--ease),background-color var(--dur) var(--ease)}
.snav .navbtn{width:100%;justify-content:flex-start;background:transparent;border:0;
cursor:pointer;font-family:inherit}
.snav a:hover,.snav .navbtn:hover{color:var(--fg);background:var(--layer-02)}
/* The ring is pulled inside the row because the row is flush with a scrolling
   container: ``outline-offset:2px`` on a full-bleed slab is clipped at both
   edges, which would hide the focus indicator on exactly the surface that
   needs it. */
.snav a:focus-visible,.snav .navbtn:focus-visible,.snav .tall:focus-visible,
.snav .grp:focus-visible{outline-offset:-2px}
/* Selected navigation is a filled row, not a stripe, and the fill belongs to
   the page level only: ``.rows > a`` is a destination, while the outline under
   it names sections *within* that destination, and two stacked slabs read as one
   block. A 2px coloured border-left was the banned affordance;
   ``--layer-accent`` carries the same "this is where you are" signal at the row
   level, and the ink stays ``--fg`` because ``--accent`` on that fill measures
   4.00:1 light / 3.96:1 dark — short of AA for a 14px label in both themes.
   Accent is reserved for the mark, never the text. */
.snav .rows > a.active,.snav .rows > .navbtn.active{color:var(--fg);background:var(--layer-accent);
font-weight:600}
/* A band is a disclosure, not a heading: Carbon's tree puts the chevron on the
   group itself, so the label that names the shelf is also the thing you press to
   close it. Hierarchy comes from a full weight step (700 vs 400) and full-strength
   ink, not from the old 10px faint mono eyebrow — illegible in Chinese and it put
   the caption *below* its own children. It is a real ``<button>``: the UA default
   chrome, centred content and system font all have to go. Same row box as the
   items beneath, so the hover fill is one shape, twice. */
.snav .grp{display:flex;align-items:center;gap:var(--sp2);width:100%;text-align:left;
background:transparent;border:0;cursor:pointer;font-family:inherit;
font-weight:700;font-size:var(--fs-sm);line-height:1.3;letter-spacing:var(--track-label);
text-transform:uppercase;color:var(--fg);padding:6px var(--sp3);border-radius:var(--r0);
transition:color var(--dur) var(--ease),background-color var(--dur) var(--ease)}
.snav .grp:hover{background:var(--layer-02)}
/* Chinese wraps at any glyph; a band name must never push the chevron off the
   rail, so the label takes the shrink and the mark is exempt. */
.snav .grp .lbl{min-width:0;overflow-wrap:anywhere}
/* 16px, the same box as the master control's mark above: the four band chevrons
   and ``.tall``'s glyph share one right edge, so a size difference between them
   reads as a column that will not line up rather than as two kinds of control. */
.snav .grp .cv{margin-left:auto;flex:none;width:16px;height:16px;color:var(--muted);
transition:transform var(--dur) var(--ease)}
/* The motion is on the affordance, never the content: ``display:none`` collapses
   the rows at once, which is what assistive tech expects, while the rotating
   chevron is the only animated thing. The base glyph points right and the open
   state turns it down, so a closed shelf and an open one are never the same
   picture. The global reduced-motion rule already clamps ``--dur``. */
.snav .grp[aria-expanded="true"] .cv{transform:rotate(90deg)}
.snav .grp[aria-expanded="false"]+.rows{display:none}
/* the rail is a tree: only the active destination expands into its own
   anchors. A flat list of every section on the site read as a 17-row wall. */
.snav .subnav{display:flex;flex-direction:column;margin:var(--sp1) 0 var(--sp2)}
/* One row box for every row in the rail: 30px at the same 6px padding as the
   page level, because a 2px shorter leaf makes the whole column visibly uneven
   while the indent is doing the level work anyway. */
.snav .subnav a,.snav .subnav .navbtn{font-weight:400;padding:6px var(--sp3) 6px
calc(var(--sp3) + var(--sp2))}
.snav .subnav a:hover,.snav .subnav .navbtn:hover{color:var(--fg);background:var(--layer-02)}
/* One level down is one 8px step of *label*, and the step is drawn as a branch
   stub rather than whitespace: the 8px rule starts where the indent starts, and
   the label continues 8px after it, so the indent is an object you can align
   two of them against. A floating 4px square was the previous answer and it
   joined nothing. The current section takes the stub in ``--accent`` at 2px
   (a graphic, so it clears 3:1 on the filled row above and on ``--bg2``),
   plus ink and weight; the row above it keeps the fill.
   ``background:transparent`` is load-bearing, not a no-op: the row rules above
   would otherwise leave an unfilled leaf indistinguishable from a hovered one. */
.snav .subnav a::before,.snav .subnav .navbtn::before{content:"";width:8px;height:1px;flex:none;
background:var(--border-strong)}
.snav .subnav a.on,.snav .subnav .navbtn.active{color:var(--fg);font-weight:600;background:transparent}
.snav .subnav a.on::before,.snav .subnav .navbtn.active::before{height:2px;background:var(--accent)}
/* Third level: a destination that is itself long groups its anchors. It sits at
   the stub column — the parent of the branches beneath it — and carries the
   same weight/tone discipline as ``.grp``: one tone down, one step smaller. */
.snav .subnav .sgrp{font-weight:700;font-size:var(--fs-xs);line-height:1.3;letter-spacing:var(--track-label);
text-transform:uppercase;color:var(--muted);padding:var(--sp3) var(--sp3) var(--sp1)
calc(var(--sp3) + var(--sp2))}
.snav .subnav .sgrp:first-child{padding-top:var(--sp1)}
/* pinned to the sidebar's foot: the nav outgrows a short viewport, and the
   locale/theme controls must stay reachable without scrolling it. The
   container has no bottom padding so this opaque block covers the edge, and it
   bleeds like the rows so its controls line up on the same gutter. */
.side-foot{position:sticky;bottom:0;margin:auto calc(-1 * var(--sp3)) 0;
display:flex;align-items:center;gap:var(--sp2);
padding:var(--sp3) var(--sp3) var(--sp4);border-top:1px solid var(--border);background:var(--bg2)}
/* the rail scrolls under this block, so the fold would otherwise cut a link
   in half; fade the last sliver instead of slicing it */
.side-foot::before{content:"";position:absolute;left:0;right:0;bottom:100%;height:22px;
background:linear-gradient(to top,var(--bg2),transparent);pointer-events:none}
.main{min-width:0}
.main .wrap{max-width:1080px;margin:0 auto;padding:var(--sp5) 30px var(--sp6)}
/* Document sections get their air from the shell, not the element: the 48px is
   the space a jump to ``#anchor`` needs above a heading, so it belongs to the
   column that holds anchors and pairs with the scroll-margin below it. Scoped to
   ``.main`` it can no longer reach the rail's bands, which are rows. */
.main section{padding-top:var(--sp6);scroll-margin-top:var(--sp2)}
@media(max-width:960px){
.shell{grid-template-columns:1fr}
.side{position:static;height:auto;border-right:0;border-bottom:1px solid var(--border);
padding:var(--sp4) var(--sp4) var(--sp3)}
.side .brand{flex-direction:row;align-items:center;gap:12px;flex-wrap:wrap;
margin:0 0 var(--sp2);padding:0 0 var(--sp2)}
/* Narrow is not "flatten". The four bands stay four bands — collapsing them into
   one wrapped wall is what made the rail unreadable. Each band keeps its rule and
   its disclosure, and only the rows *inside* a band run horizontally.
   The bleed is undone here because a wrapped row is a chip, not a slab: a
   full-bleed chip that wraps would be 100% wide and stack into the flat wall
   again, so rows go back to shrink-wrapped boxes with a radius and the
   indentation is dropped with the column it was measured against. */
.snav{margin:0}
.snav .navtools{border-bottom:0;padding-bottom:var(--sp1)}
.snav .tall{width:auto;padding:5px 10px;border-radius:var(--r1)}
.snav .tall .cv{margin-left:0}
.snav a,.snav .navbtn,.snav .grp{width:auto;padding:5px 10px;border-radius:var(--r1)}
.snav .rows{flex-direction:row;flex-wrap:wrap;gap:var(--sp1)}
.snav .sec+.sec{margin-top:var(--sp2);padding-top:var(--sp1)}
.snav .subnav{width:100%;flex-direction:row;flex-wrap:wrap;gap:var(--sp1);margin:var(--sp1) 0 0}
.snav .subnav .sgrp{width:100%;padding:var(--sp2) 10px var(--sp1)}
.snav .subnav a,.snav .subnav .navbtn{padding:5px 10px}
/* wrapped, there is no indentation left to hang hierarchy on, so the leaf
   goes back to the fill and drops its branch stub */
.snav .subnav a::before,.snav .subnav .navbtn::before{display:none}
.snav .subnav a.on,.snav .subnav .navbtn.active{background:var(--layer-accent)}
.side-foot{position:static;margin-top:10px;padding:var(--sp2) 0 0}
.side-foot::before{display:none}
.main .wrap{padding:var(--sp4) var(--sp4) 40px}
}
"""

#: The long-document article: one authored block for every surface that renders
#: a Markdown document (``/sop``, ``/course``, ``/docs/read/<slug>``). Each of
#: them carried a hand-copied version of these rules, and that is how they
#: drifted — the SOP kept an anchor scroll-margin the course lost, all three
#: still wrote radius 5px/9px and ``--panel2`` table chrome while the rest of
#: the ramp had moved to 0/2/4 and the layer tokens.
#:
#: The container is ``.prose``, not ``.md``. ``.md`` is the engagement
#: console's matrix/detail grid, and the console injects ``BASE_CSS`` as well,
#: so any ``.md``-scoped rule shared upward would have leaked ``max-width`` and
#: ``font-size`` into the console's layout. Two meanings for one class name was
#: the other half of the drift problem, and it is why this is a separate
#: constant rather than part of ``BASE_CSS``.
PROSE_CSS = """
.prose{max-width:860px;font-size:var(--fs-body);line-height:1.78;color:var(--fg)}
.prose>*:first-child{margin-top:0}
/* Prose headings sit on the same 16px cadence as the ``--fs-*`` ramp (18px and
   16px, the productive heading steps a document actually needs) but are local
   to the article, so they stay literal instead of becoming tokens the rest of
   the app never uses. */
.prose h3,.prose h4,.prose h5,.prose h6{margin:1.7em 0 .55em;font-weight:650;
letter-spacing:var(--track-tight);line-height:1.35;overflow-wrap:anywhere;text-wrap:balance}
/* an anchor jump must not bury the heading under the fold of the viewport */
.prose h3[id]{scroll-margin-top:var(--sp3)}
.prose h3{font-size:var(--fs-h3);padding-bottom:var(--sp2);border-bottom:1px solid var(--border)}
.prose h4{font-size:var(--fs-h4)}
.prose h5,.prose h6{font-size:var(--fs-body);color:var(--muted)}
.prose p{margin:.7em 0}
.prose ul,.prose ol{margin:.6em 0;padding-left:1.5em}
.prose li{margin:.28em 0}
.prose li>ul,.prose li>ol{margin:.28em 0}
.prose a{overflow-wrap:anywhere}
.prose strong{font-weight:650}
/* Inline code in an article is the canonical ``code`` chip from ``THEME_CSS`` and
   nothing more — it scales one step below the prose rather than pinning
   ``--fs-xs``, which is what a 15px line wants. Inside a ``pre`` the chip chrome
   comes off entirely. */
.prose pre{background:var(--code);border:1px solid var(--border);border-radius:var(--r1);
padding:var(--sp3);margin:.95em 0;overflow-x:auto}
.prose pre code{background:none;border:0;padding:0;font-size:var(--fs-xs);
line-height:1.68;overflow-wrap:normal}
/* A quote is a raised block, not a stripe: the 3px accent border-left this
   replaced is the banned affordance, and it coloured the one boundary that
   carries no state. It sits on ``--layer-01``, one step *below* the page note's
   ``--layer-02``, because on the SOP the two boxes are adjacent and identical
   surfaces made quoted source text look like more app chrome. ``--muted`` on
   ``--layer-01`` clears 6.3:1 in both themes (the layer moves away from the ink
   in each), so the de-emphasis survives AA. */
.prose blockquote{margin:var(--sp3) 0;padding:var(--sp2) var(--sp3);
background:var(--layer-01);border:1px solid var(--border);border-radius:var(--r1);color:var(--muted)}
.prose blockquote>*:first-child{margin-top:0}
.prose blockquote>*:last-child{margin-bottom:0}
.prose hr{border:0;border-top:1px solid var(--border);margin:var(--sp4) 0}
.prose table{display:block;max-width:100%;overflow-x:auto;border-collapse:collapse;
margin:.95em 0;font-size:var(--fs-sm)}
.prose th,.prose td{border:1px solid var(--border);padding:var(--sp2) 10px;
text-align:left;vertical-align:top}
.prose th{background:var(--layer-02);font-weight:600;white-space:nowrap}
/* no zebra. The old tint was color-mix(--panel2 42%), a second formula per
   theme that had to be re-checked every time the ramp moved; the header row
   already steps up a layer and every cell carries a hairline, so the grid is
   legible without the stripe. */
.prose img{max-width:100%;border:1px solid var(--border);border-radius:var(--r2);margin:.6em 0}
@media(max-width:640px){.prose{font-size:var(--fs-sm)}}
"""

"""The full-SOP reading room (``/sop``, ``/en/sop``).

The methodology is authored as Markdown in ``docs/fde_sop_full.md`` at the repo
root. That file is the source of truth and is read here — never copied into the
package — so an edit reaches this page on the next restart with nothing to keep
in sync. A wheel install has no ``docs/`` and gets an in-page notice instead of
a broken route.

Rendered from paired literals, like ``course.py``, ``glossary.py`` and
``certification.py`` (their docstrings explain why the ``to_en`` pass is wrong
for whole pages of content): the chrome is translated here, while the document
is Chinese-authored and is served as authored on both locales — the English
page says so in a notice rather than pushing the prose through the substring
translator. The rail's section labels come from the document itself, so they
are Chinese on both locales too; the two headings that carry a parenthetical
are shortened for the 250px rail (``工业 Overlay（…）`` → ``工业 Overlay``), a
mechanical cut at the full-width paren, not a hand-kept list.

Markdown is rendered with ``html: False``: the document contains angle brackets
(``PL < PLr``, ``Gate.check(ctx) -> GateResult``) that must stay visible, so raw
HTML is escaped. Two deliberate corrections happen after rendering — ``<br>``
(the only in-cell line break a GFM table has) is restored outside code blocks,
and headings are demoted one level so the outline runs section (h3) → subsection
(h4). The document's own ``# `` title moves into the page hero, and each ``##``
section is given an ``id`` (``s01``…) so the rail can anchor into the page.

The rail's section list comes from the markdown token stream (never scraped
back out of rendered HTML), and the English rail carries paired literals for
the seven section titles — the document itself stays Chinese on both locales.
"""

from __future__ import annotations

import re
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML

from .layout import BASE_CSS, PROSE_CSS, SHELL_CSS, SHELL_JS, side_nav

_SOP_DIRNAME = "docs"
_SOP_FILENAME = "fde_sop_full.md"

_H1 = re.compile(r"^#\s+(.*?)\s*$", re.M)
#: The capture group is load-bearing: ``re.split`` drops the separators
#: otherwise, which would silently delete every fenced block.
_PRE = re.compile(r"(<pre\b.*?</pre>)", re.S)

#: English rail labels for the document's ``##`` sections, keyed by the zh
#: heading as authored. A section the table does not know falls back to its
#: zh title instead of lying with a wrong translation.
_RAIL_EN: dict[str, str] = {
    "为什么不是 5 步": "Why not 5 steps",
    "4 Zones": "4 Zones",
    "18 阶段详解": "The 18 phases in detail",
    "工业 Overlay（manufacturing/robotics profile 启用）": "Industrial overlay (manufacturing/robotics profile)",
    "12 大反模式（gate 直接守卫）": "The 12 anti-patterns (guarded by gates)",
    "工程化映射": "Engineering mapping",
    "来源（真实依据）": "Sources (real provenance)",
}


class _SopRenderer(RendererHTML):
    """Anchor every ``##`` section and demote every heading one level.

    A subclass, not ``renderer.rules[...] = fn``: ``RendererHTML`` builds
    ``rules`` from the instance's own bound methods, so overriding is the path
    the library documents — and it keeps the map's ``MethodType`` values.
    """

    def heading_open(self, tokens, idx, options, env):  # noqa: ANN001 - markdown-it rule signature
        token = tokens[idx]
        if token.tag == "h2":
            env["h2"] = env.get("h2", 0) + 1
            token.attrSet("id", f"s{env['h2']:02d}")
        return self._demoted(tokens, idx, options, env)

    def heading_close(self, tokens, idx, options, env):  # noqa: ANN001 - markdown-it rule signature
        return self._demoted(tokens, idx, options, env)

    def _demoted(self, tokens, idx, options, env):  # noqa: ANN001 - markdown-it rule signature
        tokens[idx].tag = f"h{min(int(tokens[idx].tag[1:]) + 1, 6)}"
        return self.renderToken(tokens, idx, options, env)


_MD = MarkdownIt("commonmark", {"html": False}, renderer_cls=_SopRenderer).enable(["table", "strikethrough"])


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2] / _SOP_DIRNAME / _SOP_FILENAME


def _rail_label(heading: str) -> str:
    """The rail's short form of a section heading (see the module docstring)."""
    return heading.split("（", 1)[0].strip() or heading


def _rail_subnav(sections: list[tuple[str, str]], en: bool) -> tuple[str, ...]:
    """The ``##`` outline as :func:`~.layout.side_nav` leaf entries.

    An EN heading the table does not know keeps its zh title: a wrong
    translation on the rail is worse than an untranslated one, because the
    reader has no way to tell which is which.
    """
    return tuple(
        (
            f"#{anchor}",
            _RAIL_EN.get(heading, _rail_label(heading)) if en else _rail_label(heading),
        )
        for anchor, heading in sections
    )


def _sections_from_tokens(md_text: str) -> list[tuple[str, str]]:
    """The ``##`` outline as ``(anchor, title)``, read from the markdown token
    stream — the ids match exactly what the renderer assigns (``s01``…), and
    nothing is scraped back out of rendered HTML."""
    sections: list[tuple[str, str]] = []
    pending = False
    counter = 0
    for tok in _MD.parse(_H1.sub("", md_text, count=1), {"h2": 0}):
        if tok.type == "heading_open" and tok.tag == "h2":
            counter += 1
            pending = True
            continue
        if pending and tok.type == "inline":
            sections.append((f"s{counter:02d}", tok.content.strip()))
            pending = False
    return sections


def _render_body(md_text: str) -> str:
    """Drop the document's ``# `` title — the hero carries it — and render the rest."""
    html = _MD.render(_H1.sub("", md_text, count=1), {"h2": 0})
    # `<br>` is escaped along with the rest of the raw HTML, but a GFM table
    # cell has no other line break — restore it, code blocks excluded.
    parts = _PRE.split(html)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")
    return "".join(parts)


_STYLE = (
    BASE_CSS
    + PROSE_CSS
    + """
.sop-note{display:flex;gap:var(--sp2);align-items:flex-start;
background:var(--layer-02);border:1px solid var(--border);border-radius:var(--r2);
padding:var(--sp3);margin:var(--sp3) 0 0;font-size:var(--fs-sm);color:var(--muted);
max-width:860px;line-height:1.7}
.sop-note .ic{color:var(--accent);margin-top:2px}
.sop-note strong{color:var(--fg)}
/* the source line is provenance, not decoration: it carries the document's path
   and hash, so it gets ``--muted`` (6.3:1 and up on every layer) rather than
   ``--faint``, which falls under AA at 12px. */
.src{font:500 var(--fs-xs)/1.7 var(--mono);color:var(--muted);margin:var(--sp2) 0 0;
overflow-wrap:anywhere}
.snav .subnav a{overflow-wrap:anywhere}
/* The note and the source line above the document both close their own bottom
   margin, so the article opens its own gap. 22px was off the grid; --sp4 is
   the nearest step. */
.prose{padding-top:var(--sp4)}
"""
    + SHELL_CSS
)

_THEME_SCRIPT = """
function toggleTheme(){
  var h = document.documentElement;
  var n = h.dataset.theme === 'light' ? 'dark' : 'light';
  h.dataset.theme = n;
  try { localStorage.setItem('fde-theme', n); } catch(e) {}
}
"""


def render(locale: str = "zh", root: Path | None = None) -> str:
    """The full SOP as one page. ``locale`` is ``"zh"`` or ``"en"``.

    ``root`` overrides the path of the Markdown *file* (tests use it to
    exercise the missing-file notice), not a directory as in ``course.py``.
    """
    if locale not in ("zh", "en"):
        raise ValueError(f"unsupported locale: {locale!r}")
    en = locale == "en"

    def p(zh: str, eng: str) -> str:
        return eng if en else zh

    source = root if root is not None else _default_root()
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = None

    # The hero title is a paired literal, not the document's H1: the zh
    # literal is byte-identical to that H1 (the drift test keeps it so),
    # but the en page must show English chrome.
    title = p("FDE 完整 SOP — 4 Zones / 18 阶段", "FDE full SOP — 4 zones / 18 phases")
    if text is None:
        body: str | None = None
        sections: list[tuple[str, str]] = []
    else:
        body = _render_body(text)
        sections = _sections_from_tokens(text) if text is not None else []

    lang = "en" if en else "zh"
    other = "/sop" if en else "/en/sop"
    lang_label = "中文" if en else "EN"
    base = "/en" if en else ""

    out: list[str] = []
    add = out.append
    add(
        f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{p("完整 SOP · FDE Scope", "Full SOP · FDE Scope")}</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{_STYLE}</style>
</head>
<body>
__ICON_SPRITE__
<div class="shell">
<aside class="side">
<div class="brand">
<div class="logo">FDE <span>Scope</span></div>
<span class="tag">{p("完整 SOP · 4 Zones / 18 阶段", "full SOP · 4 zones / 18 phases")}</span>
</div>
<nav class="snav">
{side_nav("sop", en=en, subnav=_rail_subnav(sections, en))}
</nav>
<div class="side-foot">
<a class="lang" href="{other}">{lang_label}</a>
<button class="tbtn" onclick="toggleTheme()" aria-label="{
            p("切换深浅主题", "Toggle light/dark theme")
        }" title="{p("切换深浅主题", "Toggle light/dark theme")}">
<svg class="ic when-light" aria-hidden="true"><use href="#i-moon"/></svg>
<svg class="ic when-dark" aria-hidden="true"><use href="#i-sun"/></svg>
</button>
</div>
</aside>
<main class="main"><div class="wrap">
<div class="hero">
<p class="eyebrow">{p("完整 SOP · 方法论原文", "Full SOP · the methodology, as authored")}</p>
<h2>{title}</h2>
<p>{
            p(
                "18 个阶段、10 道合规 gate、12 大反模式：FDE 从 Gemba walk 到签字移交的完整链路，"
                "来自仓库里的那份 Markdown 原文。",
                "Eighteen phases, ten compliance gates and twelve anti-patterns: the whole FDE chain "
                "from the first Gemba walk to signed handoff, from the Markdown document in the "
                "repository.",
            )
        }</p>
</div>
<p class="src">{p("来源：", "Source: ")}{_SOP_DIRNAME}/{_SOP_FILENAME}</p>"""
    )

    if body is not None:
        add(
            f"""<div class="sop-note">
<svg class="ic" aria-hidden="true"><use href="#i-rocket"/></svg>
<p>{
                p(
                    "本文档是方法论全文；实际的阶段推进、门禁校验与留痕在 Engagement 控制台完成 —— ",
                    "This document is the methodology; actual phase advancement, gate checks and "
                    "audit trails happen in the engagement console — ",
                )
            }<a href="{base}/console">{p("打开控制台 →", "open the console →")}</a></p>
</div>""",
        )

    if body is not None and en:
        add(
            """<div class="sop-note">
<svg class="ic" aria-hidden="true"><use href="#i-bulb"/></svg>
<p>The SOP is authored in Chinese and is served as authored. This page translates the
rail, the notices and the page chrome — not the document text, and not the section
labels in the rail.</p>
</div>"""
        )

    if body is not None:
        # the body is Chinese on both locales
        body_lang = ' lang="zh-Hans"' if en else ""
        add(f'<div class="prose"{body_lang}>{body}</div>')
    else:
        add(
            f"""<div class="sop-note">
<svg class="ic" aria-hidden="true"><use href="#i-alert"/></svg>
<p>{
                p(
                    "这台机器上读不到 SOP 原文：仓库里没有 "
                    f"<code>{_SOP_DIRNAME}/{_SOP_FILENAME}</code>（从 wheel 安装时就是这种情况）。"
                    f"全文在仓库的 <code>{_SOP_DIRNAME}/{_SOP_FILENAME}</code>，"
                    "克隆仓库后重启本页即可在这里阅读。",
                    "The SOP document is not on this machine: there is no "
                    f"<code>{_SOP_DIRNAME}/{_SOP_FILENAME}</code> at the repo root (a wheel install "
                    f"has none). It lives in the repository at "
                    f"<code>{_SOP_DIRNAME}/{_SOP_FILENAME}</code>; clone it and reopen this page to "
                    "read it here.",
                )
            }</p>
</div>"""
        )

    add(
        f"""
<footer>
<span>{p("FDE Scope · 完整 SOP", "FDE Scope · Full SOP")}</span>
<span>{
            p(
                "Markdown 文档为准，本页是它的阅读视图",
                "The Markdown document is authoritative; this page is its reading view",
            )
        }</span>
</footer>

</div>
</main>
</div>
<script>{_THEME_SCRIPT}</script>
<script>{SHELL_JS}</script>
</body>
</html>
"""
    )
    return "".join(out)

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
"""

from __future__ import annotations

import re
from pathlib import Path

from markdown_it import MarkdownIt

from .layout import BASE_CSS, SHELL_CSS, SHELL_JS

_SOP_DIRNAME = "docs"
_SOP_FILENAME = "fde_sop_full.md"

_H1 = re.compile(r"^#\s+(.*?)\s*$", re.M)
#: The capture group is load-bearing: ``re.split`` drops the separators
#: otherwise, which would silently delete every fenced block.
_PRE = re.compile(r"(<pre\b.*?</pre>)", re.S)
#: Section anchors as the rail reads them: the demoted ``##`` headings.
_H3 = re.compile(r'<h3 id="(s\d{2})">(.*?)</h3>')

_MD = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])


def _heading_open(tokens, idx, options, env):  # noqa: ANN001 - markdown-it rule signature
    """Anchor every ``##`` section and demote every heading one level."""
    token = tokens[idx]
    if token.tag == "h2":
        env["h2"] = env.get("h2", 0) + 1
        token.attrSet("id", f"s{env['h2']:02d}")
    token.tag = f"h{min(int(token.tag[1:]) + 1, 6)}"
    return _MD.renderer.renderToken(tokens, idx, options, env)


def _heading_close(tokens, idx, options, env):  # noqa: ANN001 - markdown-it rule signature
    token = tokens[idx]
    token.tag = f"h{min(int(token.tag[1:]) + 1, 6)}"
    return _MD.renderer.renderToken(tokens, idx, options, env)


_MD.renderer.rules["heading_open"] = _heading_open
_MD.renderer.rules["heading_close"] = _heading_close


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2] / _SOP_DIRNAME / _SOP_FILENAME


def _rail_label(heading: str) -> str:
    """The rail's short form of a section heading (see the module docstring)."""
    return heading.split("（", 1)[0].strip() or heading


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
    + """
.sop-note{display:flex;gap:10px;align-items:flex-start;background:var(--panel2);border:1px solid var(--border);
border-radius:9px;padding:12px 14px;margin:18px 0 0;font-size:.84rem;color:var(--muted);max-width:860px;line-height:1.7}
.sop-note .ic{color:var(--accent);margin-top:2px}
.sop-note strong{color:var(--fg)}
.src{font:500 .74rem/1.7 var(--mono);color:var(--faint);margin:7px 0 0;overflow-wrap:anywhere}
.snav .subnav a{overflow-wrap:anywhere}
.md{max-width:860px;font-size:.92rem;line-height:1.78;color:var(--fg);padding-top:22px}
.md>*:first-child{margin-top:0}
.md h3,.md h4,.md h5,.md h6{margin:1.7em 0 .55em;font-weight:650;letter-spacing:-.008em;line-height:1.35;overflow-wrap:anywhere}
.md h3[id]{scroll-margin-top:20px}
.md h3{font-size:1.13rem;padding-bottom:7px;border-bottom:1px solid var(--border)}
.md h4{font-size:1rem}
.md h5,.md h6{font-size:.93rem;color:var(--muted)}
.md p{margin:.7em 0}
.md ul,.md ol{margin:.6em 0;padding-left:1.5em}
.md li{margin:.28em 0}
.md li>ul,.md li>ol{margin:.28em 0}
.md a{overflow-wrap:anywhere}
.md strong{font-weight:650}
.md code{font:.82em/1.6 var(--mono);background:var(--code);border:1px solid var(--border);border-radius:5px;
padding:1px 5px;overflow-wrap:anywhere}
.md pre{background:var(--code);border:1px solid var(--border);border-radius:9px;padding:13px 15px;margin:.95em 0;
overflow-x:auto}
.md pre code{background:none;border:0;padding:0;font-size:.79rem;line-height:1.68;overflow-wrap:normal}
.md blockquote{margin:.95em 0;padding:2px 0 2px 14px;border-left:3px solid var(--accent);color:var(--muted)}
.md blockquote p{margin:.4em 0}
.md hr{border:0;border-top:1px solid var(--border);margin:1.7em 0}
.md table{display:block;max-width:100%;overflow-x:auto;border-collapse:collapse;margin:.95em 0;font-size:.84rem}
.md th,.md td{border:1px solid var(--border);padding:7px 10px;text-align:left;vertical-align:top}
.md th{background:var(--panel2);font-weight:600;white-space:nowrap}
.md tbody tr:nth-child(even) td{background:color-mix(in oklab,var(--panel2) 42%,transparent)}
@media(max-width:640px){.md{font-size:.88rem}}
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
        sections = _H3.findall(body)

    lang = "en" if en else "zh"
    other = "/sop" if en else "/en/sop"
    lang_label = "中文" if en else "EN"
    base = "/en" if en else ""
    catalog = "/catalog/en/index.html" if en else "/catalog/index.html"

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
<svg width="0" height="0" style="position:absolute" aria-hidden="true">__ICON_SPRITE__</svg>
<div class="shell">
<aside class="side">
<div class="brand">
<div class="logo">FDE <span>Scope</span></div>
<span class="tag">{p("完整 SOP · 4 Zones / 18 阶段", "full SOP · 4 zones / 18 phases")}</span>
</div>
<nav class="snav">
<div class="grp">{p("FDE 学习者", "FDE learners")}</div>
<a href="{base}/">{p("功能总览", "Overview")}</a>
<a href="{base}/course">{p("入门课程", "Intro course")}</a>
<a href="{base}/glossary">{p("名词解释", "Glossary")}</a>
<a href="{base}/certification">{p("认证中心", "Certification")}</a>
<div class="grp">{p("FDE 工程师", "FDE engineers")}</div>
<a href="{base}/sop" class="active">{p("SOP 全文", "SOP full text")}</a>"""
    )
    if sections:
        add('<div class="subnav">')
        for anchor, heading in sections:
            add(f'<a href="#{anchor}">{_rail_label(heading)}</a>')
        add("</div>")
    add(
        f"""<a href="{catalog}">{p("技能手册库", "Skills handbook")}</a>
<a href="{base}/docs/readme">{p("仓库文档", "Repo docs")}</a>
<div class="grp">{p("FDE 工作台", "FDE workbench")}</div>
<a href="{base}/console">{p("Engagement 控制台", "Engagement console")}</a>
<div class="grp">{p("外部", "External")}</div>
<a href="{"/GTM/en/index.html" if en else "/GTM/index.html"}">{p("GTM 官网", "GTM site")}</a>
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
        add(f'<div class="md"{body_lang}>{body}</div>')
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

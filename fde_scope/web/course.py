"""The Level-1 course reading room (``/course``, ``/en/course``).

The lessons are authored as Markdown in ``course-level-1/`` at the repo root.
That directory is the source of truth and is read here — never copied into the
package — so a lesson edit reaches this page on the next restart with nothing
to keep in sync. A wheel install has no ``course-level-1/`` and gets an
in-page notice instead of a broken route.

Rendered from paired literals, like ``glossary.py`` and ``certification.py``
(their docstrings explain why the ``to_en`` pass is wrong for whole pages of
content): the chrome and the twenty-five chapter titles are translated here,
while the lesson bodies are Chinese-authored and are served as authored on
both locales — the English page says so in a notice, rather than pushing 5,000
lines of prose through the substring translator, which would translate a few
navigation fragments and silently leave the rest.

Markdown is rendered with ``html: False``: the lessons use angle-bracket
placeholders (``<id>``, ``<skill-id>``, ``<N 条脏数据>``) that must stay
visible, so raw HTML is escaped. Before rendering, every link and image is
rewritten to an in-app target — chapter cross-references become ``#doc-``
anchors, repo citations point at the local reader pages, and anything
unresolvable is stripped to its label — with code fences left byte-identical
(their template examples are full of markdown links). Two corrections happen
after rendering: ``<br>`` (the only in-cell line break a GFM table has) is
restored outside code blocks, and headings are demoted one level so the
document outline runs chapter (h2) → lesson section (h3).

This module also hosts the shared link-rewrite machinery — the fence walker,
path normalisation and the markdown link regexes — that ``docs_reader.py``
builds on: ``docs_reader`` imports this module, so the utilities cannot live
there without a cycle.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt

from .layout import BASE_CSS, SHELL_CSS, SHELL_JS

_COURSE_DIRNAME = "course-level-1"

#: (anchor key, filename, zh title, en title, zh rail label, en rail label).
#: Titles are pinned to each file's ``# `` heading by ``tests/test_web.py``.
_CHAPTERS: list[tuple[str, str, str, str, str, str]] = [
    (
        "readme",
        "README.md",
        "小白 FDE 炼金术 · Level 1",
        "Beginner FDE Alchemy · Level 1",
        "总览",
        "Overview",
    ),
    (
        "00",
        "00-FDE方法论历史与原理.md",
        "00 · FDE 方法论、历史与原理",
        "00 · FDE methodology, history and principles",
        "00 方法论",
        "00 Method",
    ),
    (
        "01",
        "01-课程设计说明书.md",
        "01 · 课程设计说明书",
        "01 · Course design brief",
        "01 设计说明",
        "01 Design",
    ),
    (
        "02",
        "02-逐日教学大纲.md",
        "02 · 逐日教学大纲（Day 1 – Day 8）",
        "02 · Day-by-day syllabus (Day 1 – Day 8)",
        "02 教学大纲",
        "02 Syllabus",
    ),
    (
        "03",
        "03-评估体系与通关门禁.md",
        "03 · 评估体系与通关门禁",
        "03 · Assessment system and gates",
        "03 评估门禁",
        "03 Assessment",
    ),
    (
        "04",
        "04-交付实施手册.md",
        "04 · 交付实施手册",
        "04 · Delivery handbook",
        "04 交付手册",
        "04 Delivery",
    ),
    (
        "05",
        "05-讲师手册.md",
        "05 · 讲师手册（Facilitator Guide）",
        "05 · Facilitator guide",
        "05 讲师手册",
        "05 Facilitator",
    ),
    (
        "06",
        "06-学员手册与作业包.md",
        "06 · 学员手册与作业包",
        "06 · Learner handbook and homework pack",
        "06 学员手册",
        "06 Learner",
    ),
    (
        "07",
        "07-实战剧本与案例库.md",
        "07 · 实战剧本与案例库",
        "07 · Scenario scripts and case library",
        "07 剧本案例",
        "07 Scenarios",
    ),
    (
        "08",
        "08-运营手册.md",
        "08 · 运营手册",
        "08 · Operations handbook",
        "08 运营手册",
        "08 Operations",
    ),
    (
        "09",
        "09-运营指标与复盘.md",
        "09 · 运营指标与复盘",
        "09 · Operations metrics and retrospectives",
        "09 指标复盘",
        "09 Metrics",
    ),
    (
        "10",
        "10-变现路径与结营包.md",
        "10 · 变现路径与结营包",
        "10 · Monetisation paths and graduation kit",
        "10 变现结营",
        "10 Monetisation",
    ),
    (
        "11",
        "11-工具与环境准备.md",
        "11 · 工具与环境准备",
        "11 · Tools and environment setup",
        "11 工具环境",
        "11 Tooling",
    ),
    (
        "12",
        "12-附录-术语表与模板库.md",
        "12 · 附录：术语表与模板库",
        "12 · Appendix: glossary and template library",
        "12 附录",
        "12 Appendix",
    ),
    (
        "13",
        "13-GTM页面与竞品对比.md",
        "13 · GTM 页面与竞品对比",
        "13 · Go-to-market page and competitor comparison",
        "13 GTM 对比",
        "13 GTM",
    ),
    (
        "14",
        "14-课后纵深与影子项目.md",
        "14 · 课后纵深与影子项目",
        "14 · Post-course depth and shadow projects",
        "14 课后纵深",
        "14 Beyond class",
    ),
    (
        "15",
        "15-公信力与结果度量.md",
        "15 · 公信力与结果度量",
        "15 · Credibility and results measurement",
        "15 公信力",
        "15 Credibility",
    ),
    (
        "16",
        "16-D1逐节教案.md",
        "16 · D1 逐节教案：入门日",
        "16 · D1 lesson plan: orientation day",
        "16 D1 入门",
        "16 D1 Basics",
    ),
    (
        "17",
        "17-D2逐节教案.md",
        "17 · D2 逐节教案：定边界",
        "17 · D2 lesson plan: setting the boundary",
        "17 D2 定边界",
        "17 D2 Boundary",
    ),
    (
        "18",
        "18-D3逐节教案.md",
        "18 · D3 逐节教案：接数据（先看再装）",
        "18 · D3 lesson plan: data intake (look before you load)",
        "18 D3 接数据",
        "18 D3 Intake",
    ),
    (
        "19",
        "19-D4逐节教案.md",
        "19 · D4 逐节教案：造语料（把矿石炼成金属）",
        "19 · D4 lesson plan: corpus forging (ore into metal)",
        "19 D4 造语料",
        "19 D4 Forge",
    ),
    (
        "20",
        "20-D5逐节教案.md",
        "20 · D5 逐节教案：验证与评估（用证据说话）",
        "20 · D5 lesson plan: validation and evaluation (let the evidence speak)",
        "20 D5 评估",
        "20 D5 Eval",
    ),
    (
        "21",
        "21-D6逐节教案.md",
        "21 · D6 逐节教案：运维化（让东西稳得住）",
        "21 · D6 lesson plan: operationalising (make it hold)",
        "21 D6 运维",
        "21 D6 Ops",
    ),
    (
        "22",
        "22-D7逐节教案.md",
        "22 · D7 逐节教案：交接与沉淀（交得出去，带得走）",
        "22 · D7 lesson plan: handover and distillation (hand it over, carry it away)",
        "22 D7 交接",
        "22 D7 Handover",
    ),
    (
        "23",
        "23-D8逐节教案.md",
        "23 · D8 逐节教案：变现日（把 7 件产出换成职业资产）",
        "23 · D8 lesson plan: monetisation day (turn 7 artefacts into career assets)",
        "23 D8 变现",
        "23 D8 Monetise",
    ),
]

#: Rail grouping: (zh caption, en caption, chapter keys). Each group is a
#: contiguous run of ``_CHAPTERS`` order — the scroll spy walks the page top
#: to bottom, so interleaving two groups would make the rail's highlight
#: zigzag between blocks. Mirrors ``course-level-1/README.md`` §5.
_GROUPS: list[tuple[str, str, list[str]]] = [
    ("总览与底稿", "Overview & foundation", ["readme", "00"]),
    ("课程设计", "Course design", ["01", "02", "03"]),
    ("交付", "Delivery", ["04", "05", "06", "07"]),
    (
        "运营 · 变现 · 支撑",
        "Operations, monetisation & support",
        ["08", "09", "10", "11", "12", "13", "14", "15"],
    ),
    (
        "逐节教案（D1–D8）",
        "Lesson plans (D1–D8)",
        ["16", "17", "18", "19", "20", "21", "22", "23"],
    ),
]

#: key → (zh rail label, en rail label); the rail renders through ``_GROUPS``.
_CHAPTER_RAIL: dict[str, tuple[str, str]] = {
    key: (rail_zh, rail_en) for key, _fn, _zh, _eng, rail_zh, rail_en in _CHAPTERS
}

_H1 = re.compile(r"^#\s+.*(?:\n|$)", re.M)
_TASK_ITEM = re.compile(r"^(\s*)- \[ \] ", re.M)
#: The capture group is load-bearing: ``re.split`` drops the separators
#: otherwise, which would silently delete every fenced block.
_PRE = re.compile(r"(<pre\b.*?</pre>)", re.S)

_MD = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])

_FENCE_OPEN = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_FENCE_CLOSE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*$")
_MD_IMAGE = re.compile(r"!\[([^\]\n]*)\]\(([^)\s]+)\)")
_MD_LINK = re.compile(r"(?<!!)\[([^\]\n]*)\]\(([^)\s]+)\)")
_AUTOLINK = re.compile(r"<(https?://[^>]+)>")


def _fenced_indices(lines: list[str]) -> set[int]:
    """Indices of lines inside a code fence, the fence markers included.

    Reduced CommonMark rule: a fence opens on ``` / ~~~ (≤3 spaces indent)
    and closes on a bare run of the same character at least as long — one
    kind cannot close the other and an opener's info string is ignored.
    """
    fenced: set[int] = set()
    ch, n = "", 0
    for i, line in enumerate(lines):
        if ch:
            m = _FENCE_CLOSE.match(line)
            if m and m.group(1)[0] == ch and len(m.group(1)) >= n:
                ch = ""
            fenced.add(i)
        elif m := _FENCE_OPEN.match(line):
            fenced.add(i)
            ch, n = m.group(1)[0], len(m.group(1))
    return fenced


def rewrite_outside_fences(md_text: str, rewrite: Callable[[str], str]) -> str:
    """Apply ``rewrite`` to the runs of lines between code fences.

    Fence lines are kept byte-identical and global line numbers survive, so
    callers can keep line-indexed side tables (heading anchors) intact. This
    module's lesson preprocessing and ``docs_reader.py``'s document
    preprocessing both go through it: the corpora's fenced template examples
    are full of markdown links that must pass through untouched.
    """
    lines = md_text.split("\n")
    fenced = _fenced_indices(lines)
    out: list[str] = []
    chunk: list[str] = []

    def flush() -> None:
        if chunk:
            out.append(rewrite("\n".join(chunk)))
            chunk.clear()

    for i, line in enumerate(lines):
        if i in fenced:
            flush()
            out.append(line)
        else:
            chunk.append(line)
    flush()
    return "\n".join(out)


def _normalize(base: str, path: str) -> str:
    """Resolve ``path`` against the source document's repo-relative directory."""
    parts = [seg for seg in base.split("/") if seg]
    for seg in path.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)


def _heading_open(tokens, idx, options, env):  # noqa: ANN001 - markdown-it rule signature
    """Demote every lesson heading one level (see the module docstring)."""
    token = tokens[idx]
    token.tag = f"h{min(int(token.tag[1:]) + 1, 6)}"
    return _MD.renderer.renderToken(tokens, idx, options, env)


_MD.renderer.rules["heading_open"] = _heading_open
_MD.renderer.rules["heading_close"] = _heading_open


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2] / _COURSE_DIRNAME


#: every in-app target a lesson link can have. Chapter files become this
#: page's own ``#doc-`` anchors; the rest point at local pages. A path that
#: resolves to neither (``AGENTS.md``, tests/, …) strips to its label.
_COURSE_FILES = {f"{_COURSE_DIRNAME}/{name}": f"#doc-{key}" for key, name, *_ in _CHAPTERS}
_LOCAL_TARGETS = {
    "README.md": "/docs/readme",
    "docs/fde_sop_full.md": "/sop",
    "docs/fde-research.md": "/docs/fde-research",
    "docs/fde_playbook.md": "/docs/fde_playbook",
    "docs/features-en.md": "/docs/features-en",
    "examples/README.md": "/docs/examples",
    "course-level-1/en/README.md": "/docs/course-en",
}
_PAGE_ANCHORS = {f"doc-{key}" for key, *_ in _CHAPTERS}


def _resolve_course_href(href: str, base: str) -> str | None:
    """One lesson link → its in-app target, or ``None`` (the label is
    stripped). Lesson bodies render with ``base = _COURSE_DIRNAME``."""
    if href.startswith("#"):
        return href if href[1:] in _PAGE_ANCHORS else None
    if href.startswith("/"):
        return href
    if href.startswith(("http://", "https://", "mailto:")):
        return None
    path = unquote(_normalize(base, href.partition("#")[0]))
    return _COURSE_FILES.get(path) or _LOCAL_TARGETS.get(path)


def _preprocess_links(md_text: str) -> str:
    """Rewrite the lessons' links/images to their in-app form (or strip them
    to the bare label), outside code fences. Fences pass through
    byte-identical — the appendix template library is full of markdown-link
    examples that must not be touched."""
    base = _COURSE_DIRNAME

    def apply(text: str) -> str:
        def repl_image(m: re.Match[str]) -> str:
            target = _resolve_course_href(m.group(2).partition("#")[0], base)
            return f"![{m.group(1)}]({target})" if target else ""

        def repl_link(m: re.Match[str]) -> str:
            target = _resolve_course_href(m.group(2), base)
            return f"[{m.group(1)}]({target})" if target else m.group(1)

        text = _MD_IMAGE.sub(repl_image, text)
        text = _MD_LINK.sub(repl_link, text)
        return _AUTOLINK.sub(r"\1", text)

    return rewrite_outside_fences(md_text, apply)


def _render_body(md_text: str) -> str:
    """One lesson: drop its own ``# `` heading, box its task items, rewrite
    its links, render."""
    body = _H1.sub("", md_text, count=1)
    body = _TASK_ITEM.sub(r"\1- ☐ ", body)
    body = _preprocess_links(body)
    html = _MD.render(body)
    # `<br>` is escaped along with the rest of the raw HTML, but a GFM table
    # cell has no other line break — restore it, code blocks excluded.
    parts = _PRE.split(html)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")
    return "".join(parts)


_STYLE = (
    BASE_CSS
    + """
.course-note{display:flex;gap:10px;align-items:flex-start;background:var(--panel2);border:1px solid var(--border);
border-radius:9px;padding:12px 14px;margin:20px 0 0;font-size:.84rem;color:var(--muted);max-width:820px;line-height:1.7}
.course-note .ic{color:var(--accent);margin-top:2px}
.course-note strong{color:var(--fg)}
.stats{margin-top:24px}
.chap{padding-top:46px}
.src{font:500 .74rem/1.7 var(--mono);color:var(--faint);margin:7px 0 0;overflow-wrap:anywhere}
.md{max-width:860px;font-size:.92rem;line-height:1.78;color:var(--fg)}
.md>*:first-child{margin-top:0}
.md h3,.md h4,.md h5,.md h6{margin:1.7em 0 .55em;font-weight:650;letter-spacing:-.008em;line-height:1.35;overflow-wrap:anywhere}
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
@media(max-width:960px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.md{font-size:.88rem}}
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
    """The course as one long page. ``locale`` is ``"zh"`` or ``"en"``.

    ``root`` overrides the ``course-level-1/`` directory (tests use it to
    exercise the missing-directory and unreadable-file notices).
    """
    if locale not in ("zh", "en"):
        raise ValueError(f"unsupported locale: {locale!r}")
    en = locale == "en"

    def p(zh: str, eng: str) -> str:
        return eng if en else zh

    directory = root if root is not None else _default_root()
    bodies: list[tuple[tuple[str, str, str, str, str, str], str | None]] = []
    for chapter in _CHAPTERS:
        filename = chapter[1]
        try:
            text = (directory / filename).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            bodies.append((chapter, None))
        else:
            bodies.append((chapter, _render_body(text)))

    served = [(chapter, body) for chapter, body in bodies if body is not None]
    joined = "".join(body for _, body in served)
    stats = (
        (len(served), p("篇文档", "documents")),
        (joined.count("<h3"), p("个小节", "sections")),
        (joined.count("<pre"), p("段代码", "code samples")),
        (joined.count("☐"), p("项练习", "practice items")),
    )

    lang = "en" if en else "zh"
    other = "/course" if en else "/en/course"
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
<title>{p("入门课程 · FDE Scope", "Intro course · FDE Scope")}</title>
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
<span class="tag">{p("入门课程 · Level 1", "intro course · level 1")}</span>
</div>
<nav class="snav">
<div class="grp">{p("FDE 学习者", "FDE learners")}</div>
<a href="{base}/">{p("功能总览", "Overview")}</a>
<a href="{base}/course" class="active">{p("入门课程", "Intro course")}</a>
<div class="subnav">"""
    )
    for cap_zh, cap_en, keys in _GROUPS:
        add(f'<div class="sgrp">{cap_en if en else cap_zh}</div>')
        for key in keys:
            rail_zh, rail_en = _CHAPTER_RAIL[key]
            add(f'<a href="#doc-{key}">{rail_en if en else rail_zh}</a>')
    add(
        f"""</div>
<a href="{base}/glossary">{p("名词解释", "Glossary")}</a>
<a href="{base}/certification">{p("认证中心", "Certification")}</a>
<div class="grp">{p("FDE 工程师", "FDE engineers")}</div>
<a href="{base}/sop">{p("SOP 全文", "SOP full text")}</a>
<a href="{"/catalog/en/index.html" if en else "/catalog/index.html"}">{p("技能手册库", "Skills handbook")}</a>
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
<p class="eyebrow">{p("入门课程 · Level 1 · 一天入门 · 七天变现", "Intro course · Level 1")}</p>
<h2>{
            p(
                "小白 FDE 炼金术：一天入门，七天变现",
                "Beginner FDE alchemy: one day to get started, seven days to monetise",
            )
        }</h2>
<p>{
            p(
                "把 4 个区、18 个阶段的完整交付链路，压缩成 8 天能亲手走完的一遍：第 1 天装上世界观与工具箱，"
                "第 2–8 天每天过一道门禁、交出一件拿得出手的产出。建议总投入约 22 小时"
                "（D1 全天 6 小时，D2–D8 每天约 2.25 小时），全程零 API key 可跑通。",
                "The whole four-zone, eighteen-phase delivery chain, compressed into eight days "
                "you walk yourself: day 1 installs the worldview and the toolbox; days 2–8 clear "
                "one gate a day and hand over one presentable artefact. Suggested effort is about "
                "22 hours (6 h on day 1, then about 2.25 h a day), and nothing on the path needs "
                "an API key.",
            )
        }</p>
</div>
<div class="course-note">
<svg class="ic" aria-hidden="true"><use href="#i-bulb"/></svg>
<p>{
            p(
                "<strong>「变现」指什么</strong>：把能力变成可展示、可检验、可对客交付的产出"
                "（作品集 + 话术 + 一条亲手跑通的链路）——<strong>不承诺就业、不承诺收入</strong>；"
                "所有客户案例均为虚构演示数据。",
                "<strong>What “monetise” means here</strong>: turning capability into presentable, "
                "checkable, customer-deliverable output (a portfolio, a script, and one chain you "
                "ran yourself) — <strong>not a promise of employment or income</strong>. Every "
                "customer case is fictional demo data.",
            )
        }</p>
</div>
<div class="course-note">
<svg class="ic" aria-hidden="true"><use href="#i-book"/></svg>
<p>{
            p(
                "整门课就是这一页：25 篇文档按顺序排在下面，左侧章节栏随滚动高亮，每章末尾的"
                "文件名指向仓库里的源文件（<code>course-level-1/</code>）。",
                "These lessons are authored in Chinese and are served as authored; this page "
                "translates the chapter titles, the rail and the chrome, not the lesson text. "
                "Each chapter names its source file under <code>course-level-1/</code>.",
            )
        }</p>
</div>
<div class="stats">"""
    )
    for num, label in stats:
        add(f'<div class="stat"><div class="num">{num}</div><div class="lab">{label}</div></div>')
    add("""</div>""")

    for chapter, body in bodies:
        key, filename, zh_title, en_title, *_ = chapter
        number = "README" if key == "readme" else key
        add(
            f"""
<section class="chap" id="doc-{key}">
<div class="sec-head">
<svg class="ic" aria-hidden="true"><use href="#i-book"/></svg>
<h2>{en_title if en else zh_title}</h2>
<span class="n">{number}</span>
</div>
<p class="src">{_COURSE_DIRNAME}/{filename}</p>"""
        )
        if body is None:
            add(
                f"""<div class="course-note">
<svg class="ic" aria-hidden="true"><use href="#i-alert"/></svg>
<p>{
                    p(
                        f"这一章读不到：仓库里没有 <code>{_COURSE_DIRNAME}/{filename}</code>"
                        "（或是文件编码不是 UTF-8）。",
                        f"This chapter is unavailable: <code>{_COURSE_DIRNAME}/{filename}</code> "
                        "is missing from this checkout (or is not UTF-8).",
                    )
                }</p>
</div>
</section>"""
            )
            continue
        lang = ' lang="zh-Hans"' if en else ""  # the body is Chinese on both locales
        add(f'<div class="md"{lang}>{body}</div>\n</section>')

    if not served:
        add(
            f"""
<div class="course-note">
<svg class="ic" aria-hidden="true"><use href="#i-alert"/></svg>
<p>{
                p(
                    "这台机器上读不到课程文件：仓库根目录下没有 "
                    f"<code>{_COURSE_DIRNAME}/</code> 目录（从 wheel 安装时就是这种情况）。"
                    "课程全文在仓库里，<code>course-level-1/</code> 目录下 25 篇 Markdown，"
                    "克隆仓库后重启本页即可在这里阅读。",
                    "The course files are not on this machine: there is no "
                    f"<code>{_COURSE_DIRNAME}/</code> directory at the repo root (a wheel install "
                    f"has none). The lessons are 25 Markdown files in <code>{_COURSE_DIRNAME}/</code> "
                    "in the repository; clone it and reopen this page to read them here.",
                )
            }</p>
</div>"""
        )

    add(
        f"""
<footer>
<span>{p("FDE Scope · 入门课程 Level 1", "FDE Scope · Intro course, Level 1")}</span>
<span>{
            p(
                "课程正文为准，本页是它的阅读视图",
                "The Markdown lessons are authoritative; this page is their reading view",
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

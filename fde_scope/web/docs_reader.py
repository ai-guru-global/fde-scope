"""Reader pages for the repository's own documents (``/docs/{slug}``, ``/en/docs/{slug}``).

This is the local replacement for every in-document link that used to leave
the app: the README's screenshots, the SOP/playbook citations from the course,
the architecture/ontology cross-references and the legal files all render here
instead of pointing at GitHub. The table below is the allowlist — a slug that
is not in it does not exist as a route (the app 404s before render).

Rendered from paired literals like ``course.py``/``sop.py`` (no ``to_en``
substring pass): the chrome is translated, the document is served as authored
on both locales and the English page says so in a notice.

Links inside the documents are rewritten, never dropped silently:

- in-document ``#anchors`` resolve against the headings' GitHub-style slugs
  (lowercase, punctuation stripped, spaces → hyphens — CJK kept), with the
  README's explicit ``<a id="…"></a>`` markers attached to the following
  heading so its hand-written TOC still lands;
- repo-relative paths resolve to a sibling reader slug, the SOP page, a
  course chapter anchor, the mounted catalog portal or the GTM page;
- ``docs/images/*.png`` that exist in the repo become app URLs served by
  ``app.py`` (screenshots are content; badge images pointing at external
  services are removed outright);
- everything else — GitHub URLs, other repo files, mailto — is stripped to
  its label text, so a page can never carry an external jump.

Markdown is rendered with ``html: False`` (raw HTML is escaped), headings are
demoted one level, and the document's own ``# `` title moves into the page
hero. A wheel install has no ``docs/``; those installs get an in-page notice
instead of a broken route.

The fence walker, path normalisation and markdown link regexes live in
``course.py`` (which this module imports — the other direction would be a
cycle) and are shared with the course's link rewrite.
"""

from __future__ import annotations

import re
from pathlib import Path

from markdown_it import MarkdownIt

from .course import (
    _AUTOLINK,
    _CHAPTERS,
    _MD_IMAGE,
    _MD_LINK,
    _fenced_indices,
    _normalize,
    rewrite_outside_fences,
)
from .layout import BASE_CSS, SHELL_CSS, SHELL_JS

REPO_IMAGES = ("overview.png", "console.png")

#: slug → (repo-relative path, zh hero title, en hero title). ``SLUGS`` drives
#: the app's route validation; ``_PATH_TO_SLUG`` drives link rewriting.
_DOCS: tuple[tuple[str, str, str, str], ...] = (
    ("readme", "README.md", "项目总览 README", "Project README"),
    (
        "fde-research",
        "docs/fde-research.md",
        "FDE 前线部署工程研究",
        "FDE forward-deployed engineering research",
    ),
    ("fde_playbook", "docs/fde_playbook.md", "FDE 现场操作手册", "FDE field playbook"),
    ("features", "docs/features.md", "功能清单", "Feature list"),
    ("features-en", "docs/features-en.md", "功能清单（英文）", "Feature list (English)"),
    ("user-guide", "docs/user-guide.md", "用户指南", "User guide"),
    ("api-reference", "docs/api-reference.md", "API 参考", "API reference"),
    ("onboarding-customer", "docs/onboarding-customer.md", "客户现场 Onboarding", "Customer onboarding"),
    ("architecture", "docs/architecture.md", "架构文档", "Architecture"),
    ("ontology", "docs/ontology.md", "Ontology 语义层", "Ontology layer"),
    (
        "agentscope_api_mapping",
        "docs/agentscope_api_mapping.md",
        "AgentScope API 对照",
        "AgentScope API mapping",
    ),
    (
        "manufacturing_scenario",
        "docs/manufacturing_scenario.md",
        "具身机器人工厂场景",
        "Embodied robot factory scenario",
    ),
    ("llm_integration", "docs/llm_integration.md", "LLM 接入", "LLM integration"),
    ("qwenpaw_integration", "docs/qwenpaw_integration.md", "QwenPaw 集成", "QwenPaw integration"),
    ("skills", "docs/skills.md", "技能沉淀系统", "Skills capture"),
    ("code_review_checklist", "docs/code_review_checklist.md", "代码评审清单", "Code review checklist"),
    ("examples", "examples/README.md", "示例 · CSV 冷启动", "Examples · CSV cold start"),
    (
        "course-en",
        "course-level-1/en/README.md",
        "Level 1 课程英文快速上手",
        "Level 1 course English quickstart",
    ),
    ("license", "LICENSE", "许可证（MIT）", "License (MIT)"),
    ("notice", "NOTICE", "第三方声明", "Notices"),
)

SLUGS: tuple[str, ...] = tuple(slug for slug, *_ in _DOCS)
_PATH_TO_SLUG: dict[str, str] = {path: slug for slug, path, *_ in _DOCS}
_COURSE_BY_FILE: dict[str, str] = {f"course-level-1/{name}": key for key, name, *_ in _CHAPTERS}

_H1 = re.compile(r"^#\s+(.*?)\s*$", re.M)
_ATX_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_EXPLICIT_ANCHOR = re.compile(r'^<a id="([^"]+)"></a>\s*$')
_PRE = re.compile(r"(<pre\b.*?</pre>)", re.S)

_MD = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])


def _slug(text: str) -> str:
    """GitHub's heading-slug rule, close enough for these documents: drop
    punctuation (CJK included punctuation is dropped, CJK words kept), spaces
    to hyphens, lowercase."""
    return "".join(
        ch if ch.isalnum() or ch in "-_" else "-" if ch.isspace() else "" for ch in text.strip().lower()
    )


def _heading_open(tokens, idx, options, env):  # noqa: ANN001 - markdown-it rule signature
    """Anchor every heading with its slug (or the explicit ``<a id>`` that
    preceded it) and demote it one level."""
    token = tokens[idx]
    if token.map:
        hid = env.get("extra_ids", {}).get(token.map[0]) or _slug(tokens[idx + 1].content)
        if hid:
            token.attrSet("id", hid)
    token.tag = f"h{min(int(token.tag[1:]) + 1, 6)}"
    return _MD.renderer.renderToken(tokens, idx, options, env)


def _heading_close(tokens, idx, options, env):  # noqa: ANN001 - markdown-it rule signature
    token = tokens[idx]
    token.tag = f"h{min(int(token.tag[1:]) + 1, 6)}"
    return _MD.renderer.renderToken(tokens, idx, options, env)


_MD.renderer.rules["heading_open"] = _heading_open
_MD.renderer.rules["heading_close"] = _heading_close


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


def image_path(name: str, root: Path | None = None) -> Path | None:
    """Absolute path of an allowlisted repo image under ``docs/images/``, or None.

    ``name`` comes straight from a URL segment; the allowlist is the only
    resolution channel, so nothing outside ``docs/images/{REPO_IMAGES}`` can
    be served.
    """
    if name not in REPO_IMAGES:
        return None
    p = (root if root is not None else _default_root()) / "docs" / "images" / name
    return p if p.is_file() else None


def _repo_target(path: str) -> str | None:
    """A repo-relative path → the in-app page that carries it, or ``None``
    (the label is then stripped)."""
    if path == "docs/fde_sop_full.md":
        return "/sop"
    key = _COURSE_BY_FILE.get(path)
    if key is not None:
        return f"/course#doc-{key}"
    slug = _PATH_TO_SLUG.get(path)
    if slug is not None:
        return f"/docs/{slug}"
    if path == "docs/skills-catalog/README.md":
        return "/catalog/index.html"
    if path == "GTM/index.html":
        return "/GTM/index.html"
    name = path.removeprefix("docs/images/")
    if path.startswith("docs/images/") and name in REPO_IMAGES:
        return f"/docs/images/{name}"
    return None


def _resolve_href(href: str, base: str, anchors: set[str]) -> str | None:
    if href.startswith("#"):
        return href if href[1:] in anchors else None
    if href.startswith("/"):
        return href
    if href.startswith(("http://", "https://", "mailto:")):
        return None
    path, _, frag = href.partition("#")
    target = _repo_target(_normalize(base, path))
    if target is None:
        return None
    if frag and target.startswith("/docs/"):
        target = f"{target}#{frag}"
    return target


def _preprocess(md_text: str, base: str) -> tuple[str, dict[int, str]]:
    """Rewrite every link/image to its in-app form (or its bare label) and
    lift the README's explicit ``<a id>`` markers onto the heading that
    follows them. Line numbers survive: markers become blank lines and code
    fences are left byte-identical."""
    lines = md_text.split("\n")
    fenced = _fenced_indices(lines)
    extra: dict[int, str] = {}
    for i, line in enumerate(lines):
        if i in fenced:
            continue
        m = _EXPLICIT_ANCHOR.fullmatch(line.strip())
        if not m:
            continue
        lines[i] = ""
        for j in range(i + 1, min(i + 3, len(lines))):
            if lines[j].strip():
                if _ATX_LINE.match(lines[j]):
                    extra[j] = m.group(1)
                break

    anchors = set(extra.values())
    for i, line in enumerate(lines):
        if i in fenced:
            continue
        m = _ATX_LINE.match(line)
        if m:
            hid = extra.get(i) or _slug(m.group(2))
            if hid:
                anchors.add(hid)

    def repl_image(m: re.Match[str]) -> str:
        src, _, _frag = m.group(2).partition("#")
        target = _resolve_href(src, base, anchors)
        if target and target.startswith("/docs/images/"):
            return f"![{m.group(1)}]({target})"
        return ""

    def repl_link(m: re.Match[str]) -> str:
        target = _resolve_href(m.group(2), base, anchors)
        return f"[{m.group(1)}]({target})" if target else m.group(1)

    def apply(text: str) -> str:
        text = _MD_IMAGE.sub(repl_image, text)
        text = _MD_LINK.sub(repl_link, text)
        return _AUTOLINK.sub(r"\1", text)

    return rewrite_outside_fences("\n".join(lines), apply), extra


def _render_body(md_text: str, base: str) -> str:
    """Drop the document's ``# `` title — the hero carries it — and render
    the rest, restoring ``<br>`` outside code blocks."""
    text, extra = _preprocess(_H1.sub("", md_text, count=1), base)
    html = _MD.render(text, {"extra_ids": extra})
    parts = _PRE.split(html)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")
    return "".join(parts)


_STYLE = (
    BASE_CSS
    + """
.doc-note{display:flex;gap:10px;align-items:flex-start;background:var(--panel2);border:1px solid var(--border);
border-radius:9px;padding:12px 14px;margin:18px 0 0;font-size:.84rem;color:var(--muted);max-width:860px;line-height:1.7}
.doc-note .ic{color:var(--accent);margin-top:2px}
.doc-note strong{color:var(--fg)}
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
.md img{max-width:100%;border:1px solid var(--border);border-radius:9px;margin:.6em 0}
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


def render(slug: str, locale: str = "zh", root: Path | None = None) -> str:
    """One repository document as a page. ``locale`` is ``"zh"`` or ``"en"``;
    ``root`` overrides the repo root (tests use it to exercise the
    missing-file notice)."""
    if locale not in ("zh", "en"):
        raise ValueError(f"unsupported locale: {locale!r}")
    if slug not in SLUGS:
        raise ValueError(f"unknown document slug: {slug!r}")
    en = locale == "en"

    def p(zh: str, eng: str) -> str:
        return eng if en else zh

    relpath, zh_title, en_title = next((path, zh, eng) for s, path, zh, eng in _DOCS if s == slug)
    source = (root if root is not None else _default_root()) / relpath
    try:
        text = source.read_text(encoding="utf-8")
        body: str | None = _render_body(text, relpath.rsplit("/", 1)[0] if "/" in relpath else "")
    except (OSError, UnicodeDecodeError):
        body = None

    lang = "en" if en else "zh"
    other = f"/en/docs/{slug}" if not en else f"/docs/{slug}"
    lang_label = "中文" if en else "EN"
    base = "/en" if en else ""
    catalog = "/catalog/en/index.html" if en else "/catalog/index.html"
    gtm = "/GTM/en/index.html" if en else "/GTM/index.html"
    title = p(zh_title, en_title)

    out: list[str] = []
    add = out.append
    add(
        f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · FDE Scope</title>
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
<span class="tag">{p("仓库文档 · 原文阅读", "repo docs · as authored")}</span>
</div>
<nav class="snav">
<div class="grp">{p("FDE 学习者", "FDE learners")}</div>
<a href="{base}/">{p("功能总览", "Overview")}</a>
<a href="{base}/course">{p("入门课程", "Intro course")}</a>
<a href="{base}/glossary">{p("名词解释", "Glossary")}</a>
<a href="{base}/certification">{p("认证中心", "Certification")}</a>
<div class="grp">{p("FDE 工程师", "FDE engineers")}</div>
<a href="{base}/sop">{p("SOP 全文", "SOP full text")}</a>
<a href="{catalog}">{p("技能手册库", "Skills handbook")}</a>
<a href="{base}/docs/readme" class="active">{p("仓库文档", "Repo docs")}</a>
<div class="grp">{p("FDE 工作台", "FDE workbench")}</div>
<a href="{base}/console">{p("Engagement 控制台", "Engagement console")}</a>
<div class="grp">{p("外部", "External")}</div>
<a href="{gtm}">{p("GTM 官网", "GTM site")}</a>
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
<p class="eyebrow">{p("仓库文档 · 原文阅读", "Repository docs · as authored")}</p>
<h2>{title}</h2>
<p>{
            p(
                "本页是仓库文档的本地阅读视图：正文按作者原样呈现（中文文档不做翻译），"
                "文档内链接已全部改写为站内链接。",
                "A local reading view of the repository's documents: the body is served as authored "
                "(Chinese documents are not translated) and every in-document link is rewritten to "
                "stay inside this app.",
            )
        }</p>
</div>
<p class="src">{p("来源：", "Source: ")}{relpath}</p>"""
    )

    if body is not None and en:
        add(
            """<div class="doc-note">
<svg class="ic" aria-hidden="true"><use href="#i-bulb"/></svg>
<p>This document is served as authored. This page translates the chrome — not
the document text.</p>
</div>"""
        )

    if body is not None:
        body_lang = ' lang="zh-Hans"' if en else ""
        add(f'<div class="md"{body_lang}>{body}</div>')
    else:
        add(
            f"""<div class="doc-note">
<svg class="ic" aria-hidden="true"><use href="#i-alert"/></svg>
<p>{
                p(
                    f"这台机器上读不到 <code>{relpath}</code>（从 wheel 安装时仓库文档不随包分发）。"
                    "克隆仓库后重启本页即可在这里阅读全文。",
                    f"The document <code>{relpath}</code> is not on this machine (a wheel install "
                    "does not carry the repository's docs). Clone the repository and reopen this "
                    "page to read it here.",
                )
            }</p>
</div>"""
        )

    add(
        f"""
<footer>
<span>{p("FDE Scope · 仓库文档", "FDE Scope · Repo docs")}</span>
<span>{p("仓库文件为准，本页是它的阅读视图", "The repository file is authoritative; this page is its reading view")}</span>
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

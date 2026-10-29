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

from .course import COURSE_FILES
from .layout import BASE_CSS, PROSE_CSS, SHELL_CSS, SHELL_JS, side_nav
from .mdrender import (
    AUTOLINK,
    MD_IMAGE,
    MD_LINK,
    DemotingRenderer,
    demoting_markdown,
    fenced_indices,
    normalize_path,
    rewrite_outside_fences,
)

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
_COURSE_BY_FILE: dict[str, str] = COURSE_FILES

_H1 = re.compile(r"^#\s+(.*?)\s*$", re.M)
_ATX_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_EXPLICIT_ANCHOR = re.compile(r'^<a id="([^"]+)"></a>\s*$')
_PRE = re.compile(r"(<pre\b.*?</pre>)", re.S)


class _DocsRenderer(DemotingRenderer):
    """Anchor every heading with its slug (or the explicit ``<a id>`` that
    preceded it), then let the shared rule demote it one level."""

    def heading_open(self, tokens, idx, options, env):  # noqa: ANN001 - markdown-it rule signature
        token = tokens[idx]
        if token.map:
            hid = env.get("extra_ids", {}).get(token.map[0]) or _slug(tokens[idx + 1].content)
            if hid:
                token.attrSet("id", hid)
        return super().heading_open(tokens, idx, options, env)


def _slug(text: str) -> str:
    """GitHub's heading-slug rule, close enough for these documents: drop
    punctuation (CJK included punctuation is dropped, CJK words kept), spaces
    to hyphens, lowercase."""
    return "".join(
        ch if ch.isalnum() or ch in "-_" else "-" if ch.isspace() else "" for ch in text.strip().lower()
    )


_MD = demoting_markdown(_DocsRenderer)


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_images() -> tuple[str, ...]:
    """Every image that actually exists under ``docs/images/``, sorted.

    Derived from the directory instead of hand-maintained, so adding a picture
    does not require touching code (and cannot 404 against a stale tuple). A
    wheel install has no ``docs/`` and gets an empty tuple — ``image_path``
    then serves nothing, which is correct.
    """
    d = _default_root() / "docs" / "images"
    if not d.is_dir():
        return ()
    return tuple(sorted(p.name for p in d.iterdir() if p.is_file()))


def image_path(name: str, root: Path | None = None) -> Path | None:
    """Absolute path of an allowlisted repo image under ``docs/images/``, or None.

    ``name`` comes straight from a URL segment; the directory-derived allowlist
    is the only resolution channel, so nothing outside ``docs/images/`` can be
    served and no path component in ``name`` is ever honoured.
    """
    if name not in _repo_images():
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
    if path.startswith("docs/images/") and name in _repo_images():
        return f"/docs/images/{name}"
    return None


#: Absolute in-app paths a document may link to. Anything else degrades to
#: its label text, same as an external URL — a hand-written ``/admin`` in a
#: markdown file must not silently become a link the app 404s (or worse,
#: serves) later.
_STATIC_HREFS = frozenset(
    {
        "/",
        "/en/",
        "/console",
        "/en/console",
        "/course",
        "/en/course",
        "/glossary",
        "/en/glossary",
        "/certification",
        "/en/certification",
        "/sop",
        "/en/sop",
        "/api/health",
    }
)
_HREF_PREFIXES = ("/docs/", "/en/docs/", "/catalog/", "/GTM/", "/static/")


def _resolve_href(href: str, base: str, anchors: set[str]) -> str | None:
    if href.startswith("#"):
        return href if href[1:] in anchors else None
    if href.startswith("/"):
        if href in _STATIC_HREFS or href.startswith(_HREF_PREFIXES):
            return href
        return None
    if href.startswith(("http://", "https://", "mailto:")):
        return None
    path, _, frag = href.partition("#")
    target = _repo_target(normalize_path(base, path))
    if target is None:
        return None
    if frag and target.startswith("/docs/"):
        target = f"{target}#{frag}"
    return target


def _preprocess(md_text: str, base: str) -> tuple[str, dict[int, str], list[tuple[int, str, str]]]:
    """Rewrite every link/image to its in-app form (or its bare label), lift
    the README's explicit ``<a id>`` markers onto the heading that follows
    them, and collect the ``##``/``###`` outline for the TOC. Line numbers
    survive: markers become blank lines and code fences are left
    byte-identical."""
    lines = md_text.split("\n")
    fenced = fenced_indices(lines)
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
    toc: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        if i in fenced:
            continue
        m = _ATX_LINE.match(line)
        if m:
            hid = extra.get(i) or _slug(m.group(2))
            if hid:
                anchors.add(hid)
                if m.group(1) in ("##", "###"):
                    # title text as authored, minus inline links (labels only)
                    title = MD_LINK.sub(r"\1", m.group(2)).strip()
                    toc.append((len(m.group(1)), hid, title))

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
        text = MD_IMAGE.sub(repl_image, text)
        text = MD_LINK.sub(repl_link, text)
        return AUTOLINK.sub(r"\1", text)

    return rewrite_outside_fences("\n".join(lines), apply), extra, toc


def _render_body(md_text: str, base: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Drop the document's ``# `` title — the hero carries it — and render
    the rest, restoring ``<br>`` outside code blocks. Returns the HTML and
    the heading outline for the page TOC."""
    text, extra, toc = _preprocess(_H1.sub("", md_text, count=1), base)
    html = _MD.render(text, {"extra_ids": extra})
    parts = _PRE.split(html)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")
    return "".join(parts), toc


def _toc_html(toc: list[tuple[int, str, str]], locale: str) -> str:
    """A collapsible on-this-page list built from the heading tokens — never
    scraped back out of rendered HTML."""
    if len(toc) < 2:
        return ""
    import html as _html

    items = "".join(
        f'<li class="l{lvl}"><a href="#{_html.escape(hid)}">{_html.escape(title)}</a></li>'
        for lvl, hid, title in toc
    )
    label = "On this page" if locale == "en" else "本页目录"
    return f'<details class="toc"><summary>{label}</summary><ul class="toc-list">{items}</ul></details>'


_STYLE = (
    BASE_CSS
    + PROSE_CSS
    + """
.doc-note{display:flex;gap:var(--sp2);align-items:flex-start;
background:var(--layer-02);border:1px solid var(--border);border-radius:var(--r2);
padding:var(--sp3);margin:var(--sp3) 0 0;font-size:var(--fs-sm);color:var(--muted);
max-width:860px;line-height:1.7}
.doc-note .ic{color:var(--accent);margin-top:2px}
.doc-note strong{color:var(--fg)}
.src{font:500 var(--fs-xs)/1.7 var(--mono);color:var(--muted);margin:var(--sp2) 0 0;
overflow-wrap:anywhere}
/* The contents box is a disclosure, so it reads as one raised layer with the
   summary as its header row. Two columns at 24px: at 860px a single column
   makes the h4 sub-entries wander, and three crams the labels. */
.toc{margin:var(--sp3) 0 0;border:1px solid var(--border);border-radius:var(--r2);
background:var(--layer-02);max-width:860px}
.toc summary{cursor:pointer;padding:var(--sp2) var(--sp3);font-weight:600;
font-size:var(--fs-sm);color:var(--fg)}
.toc-list{margin:0;padding:var(--sp1) var(--sp3) var(--sp2);list-style:none;
columns:2;column-gap:var(--sp4)}
.toc-list li{margin:.22em 0;break-inside:avoid;font-size:var(--fs-sm)}
.toc-list li.l4{padding-left:var(--sp3)}
.toc-list a{color:var(--muted);text-decoration:none}
.toc-list a:hover{color:var(--accent-text)}
.snav .subnav a{overflow-wrap:anywhere}
/* the article opens its own gap: the source line and the contents box above it
   both close their own bottom margins */
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
    body: str | None
    toc: list[tuple[int, str, str]] = []
    try:
        text = source.read_text(encoding="utf-8")
        body, toc = _render_body(text, relpath.rsplit("/", 1)[0] if "/" in relpath else "")
    except (OSError, UnicodeDecodeError):
        body = None

    lang = "en" if en else "zh"
    other = f"/en/docs/{slug}" if not en else f"/docs/{slug}"
    lang_label = "中文" if en else "EN"
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
__ICON_SPRITE__
<div class="shell">
<aside class="side">
<div class="brand">
<div class="logo">FDE <span>Scope</span></div>
<span class="tag">{p("仓库文档 · 原文阅读", "repo docs · as authored")}</span>
</div>
<nav class="snav">
{side_nav("docs" if slug == "readme" else "", en=en)}
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
        add(_toc_html(toc, locale))
        add(f'<div class="prose"{body_lang}>{body}</div>')
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

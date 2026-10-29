"""The GitHub 资源 page (``/resources``, ``/en/resources``).

One searchable index of every repository harvested off GitHub for the
forward-deployed-engineer topic (``fde_scope/resources/data/resources.yaml``),
rendered from the package's own YAML so an installed wheel answers the full
catalog too. Like the glossary this page is a read-only static shell: no
engagement data, hence public (see ``auth.PUBLIC_PATHS``).

Two orthogonal axes are shown as independent filter chips, never merged
(``models.py`` keeps ``NONE`` and ``NOASSERTION`` as distinct sentinels):

* **license** — can we redistribute the body text verbatim?
* **relevance** — is it worth reading at all?

Hard constraints this module must honour (``tests/test_web.py``):

* No anchor leaves the app. Upstream GitHub URLs are rendered as inert
  ``<code>`` text, never ``<a href>`` — the rail test asserts
  ``'href="http' not in page``.
* Every byte of upstream-sourced text (``upstream_description``, repo names)
  is untrusted input that lands on our page, so it is passed through
  ``html.escape(..., quote=True)`` — the same treatment the certification
  provenance block gets.

The per-repo summary is *our own* bilingual prose (always redistributable);
the mirror count is metadata only — the verbatim bodies live on disk under
``docs/github-resources/mirror`` and are reached with ``rg``/an editor, not a
click here.
"""

from __future__ import annotations

import html

from ..resources.models import LICENSE_NONE, ResourceRecord, is_permissive
from ..resources.repo import load_resources
from .layout import BASE_CSS, SHELL_CSS, SHELL_JS, side_nav

_REL_ORDER = {"core": 0, "adjacent": 1, "noise": 2}

#: The ``license_decision_applied`` field is authored by ``harvest._decision``
#: from a fixed clause vocabulary, so the English page translates the clause
#: rather than shipping the Chinese string. The guard
#: (``tests/test_resources_guard.py``) asserts every stored clause is covered
#: here, so a new clause fails loudly instead of leaking CJK onto /en.
_DECISION_CLAUSES_EN = {
    "许可宽松，但相关性为 noise，不镜像正文": "permissive licence, but relevance unreviewed — body not mirrored",
    "宽松许可，正文可逐字镜像": "permissive licence — body mirrored verbatim",
    "上游声明无许可，正文一律不复制": "upstream declares no licence — body never copied",
    "许可不可辨识，仅元数据，正文不复制": "licence unrecognised — metadata only, body not copied",
    "许可非宽松（copyleft 等），仅元数据，正文不复制": "non-permissive licence (copyleft etc.) — metadata only, body not copied",
}


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _decision_line(license_decision_applied: str, en: bool) -> str:
    """The stored (Chinese) decision string verbatim for zh; the same clause
    rendered in English for en. ``SPDX → clause`` is split once so the SPDX
    token stays untouched."""
    if not en:
        return license_decision_applied
    head, sep, clause = license_decision_applied.partition(" → ")
    translated = _DECISION_CLAUSES_EN.get(clause)
    return f"{head} → {translated}" if sep and translated else license_decision_applied


def _lic_bucket(license_spdx: str) -> str:
    if is_permissive(license_spdx):
        return "permissive"
    if license_spdx == LICENSE_NONE:
        return "none"
    return "noassertion"


def _record_cards(records: list[ResourceRecord], p, en: bool) -> str:
    """One card per record, core → adjacent → noise then stars desc.

    ``p(zh, en)`` picks the locale string and ``en`` says which locale was
    picked, so a card can prefer its own-language summary without probing the
    helper. Every field sourced from GitHub is escaped before it reaches the
    page.
    """
    ordered = sorted(records, key=lambda r: (_REL_ORDER.get(r.relevance, 3), -r.stars, r.slug))
    cards: list[str] = []
    for rec in ordered:
        lic = _lic_bucket(rec.license_spdx)
        summary = rec.summary_en or rec.summary_zh
        body_lines: list[str] = []
        if rec.summary_zh and rec.summary_en:
            chosen = rec.summary_en if en else rec.summary_zh
            body_lines.append(f'<p class="r-sum">{_esc(chosen)}</p>')
        if rec.upstream_description:
            body_lines.append(
                f'<p class="r-up">{p("上游简介：", "upstream: ")}{_esc(rec.upstream_description)}</p>'
            )
        if summary is None and not rec.upstream_description:
            body_lines.append(f'<p class="r-up">{p("（暂无简介）", "(no description)")}</p>')

        flags = [p(f"{rec.stars:,}★", f"{rec.stars:,}★")]
        if rec.is_fork:
            flags.append(p("fork", "fork"))
        if rec.archived:
            flags.append(p("已归档", "archived"))
        flag_str = " · ".join(_esc(f) for f in flags)

        if rec.mirror and rec.files:
            n = len(rec.files)
            local = f"docs/github-resources/mirror/{rec.mirror_dir}"
            mirror_line = (
                f'<p class="r-mir">{p("逐字镜像：", "verbatim mirror: ")}{_esc(local)}'
                f" · {_esc(p(f'{n} 个文件', f'{n} files'))}</p>"
            )
        elif rec.mirror_reason:
            mirror_line = f'<p class="r-no">{_esc(rec.mirror_reason)}</p>'
        else:
            mirror_line = ""

        cats = " ".join(f'<span class="tag">{_esc(c)}</span>' for c in rec.categories)
        haystack = _esc(
            " ".join(
                [
                    rec.slug,
                    rec.repo,
                    rec.url,
                    rec.license_spdx,
                    rec.relevance,
                    " ".join(rec.categories),
                    rec.summary_zh or "",
                    rec.summary_en or "",
                    rec.upstream_description or "",
                ]
            ).casefold()
        )

        cards.append(
            f"""<div class="card rcard" data-t="{haystack}" data-lic="{lic}" data-rel="{_esc(rec.relevance)}">
<div class="r-head"><h3>{_esc(rec.repo)}</h3>
<span class="pill rel-{_esc(rec.relevance)}">{_esc(rec.relevance)}</span>
<span class="pill lic-{lic}">{_esc(rec.license_spdx)}</span></div>
<p class="r-url">{_esc(p("仓库地址", "repository"))} <code>{_esc(rec.url)}</code></p>
{"".join(body_lines)}
<p class="r-meta">{flag_str} · {_esc(p("更新", "updated"))} {_esc(rec.upstream_updated_at[:10])}
· {_esc(p("采集", "snapshot"))} {_esc(rec.snapshot_at[:10])}</p>
<div class="r-tags">{cats}</div>
<p class="r-decision">{_esc(_decision_line(rec.license_decision_applied, en))}</p>
{mirror_line}
</div>"""
        )
    return "".join(cards)


#: The resource card, authored once for two surfaces.
#:
#: The in-app ``/resources`` page and the generated portal
#: (``scripts/build_resources_site.py``) render the *same* object — a repository,
#: its two orthogonal badges, its summary, its licence decision — and until now
#: each carried its own copy of these rules. That is how they drifted: the app's
#: chip at 2px against the portal's at 6px, the portal's badge ink at ``#fff``
#: (2.35:1 in dark) against the app's ``--accent-ink``, a GitHub green here and a
#: ``--good-fill`` wash there. Appearance is canonical here; placement stays with
#: each page, which is why the search bar, the chip row and the list container are
#: in this block (both surfaces have them) while the portal's masthead and query
#: box are not (only one surface has them).
#:
#: No CJK may be added to this string: it is shipped into the English portal too.
RESOURCE_CSS = """
.rbar{display:flex;flex-wrap:wrap;gap:var(--sp3);align-items:center;margin:var(--sp3) 0 0}
.rsearch{flex:1;min-width:220px}
/* the field itself comes from the canonical ``input`` rule in ``THEME_CSS``; only
   its width behaviour is page-specific. Repeating the metrics here is how the
   third and fourth field styles got made. */
.rsearch input{width:100%}
.r-count{font:600 var(--fs-xs)/1.5 var(--mono);color:var(--muted);white-space:nowrap}
.rchips{display:flex;flex-wrap:wrap;gap:var(--sp1);margin:var(--sp3) 0}
/* The track count is a consequence of the card, not a viewport number. 340px is
   the width at which a badge line and a repo URL stop wrapping mid-token, and
   ``auto-fill`` fills whatever the column allows — which is two on both surfaces
   at full width (3 × 340 + 2 × 16 = 1052 clears neither the 1020px console nor
   the 1032px portal column) and one below 696. The old pairing of a fixed
   two-column grid with a ``960px`` breakpoint meant the portal collapsed at a
   different width than the app for no reason anyone had; and it has to be
   ``auto-fill``, not ``auto-fit``: an empty track stays allocated under
   ``auto-fit``, so a filtered list of one or two hits would stretch an orphan
   card the full 1032px. ``min(340px,100%)`` floors it on a phone, where 340
   exceeds the whole column. */
.rl{display:grid;gap:var(--sp3);margin:0;
grid-template-columns:repeat(auto-fill,minmax(min(340px,100%),1fr))}
.rcard{background:var(--panel);border:1px solid var(--border);border-radius:var(--r2);
padding:14px 16px;min-width:0;display:flex;flex-direction:column;gap:7px;
transition:border-color var(--dur) var(--ease)}
.rcard:hover{border-color:var(--border-strong)}
.r-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.r-head h3{margin:0;font-size:var(--fs-body);font-weight:650;overflow-wrap:anywhere;flex:1;min-width:0}
/* Badges are labels, not capsules: ``--r1`` corner, ``--fs-xs`` mono, and an ink
   that is a token role rather than ``#fff`` — white on ``--accent`` is 2.35:1 in
   dark, so a filled badge takes ``--accent-ink`` and a state badge takes its own
   ink on its own wash. */
.pill{font:600 var(--fs-xs)/1.5 var(--mono);padding:3px 8px;border-radius:var(--r1);white-space:nowrap}
.rel-core{background:var(--accent);color:var(--accent-ink)}
.rel-adjacent{background:var(--code);color:var(--fg);border:1px solid var(--border-strong)}
.rel-noise{background:transparent;color:var(--muted);border:1px solid var(--border)}
.lic-permissive{background:var(--good-fill);color:var(--good)}
.lic-noassertion{background:var(--code);color:var(--muted);border:1px solid var(--border)}
.lic-none{background:var(--bad-fill);color:var(--bad)}
.r-url,.r-meta,.r-decision,.r-up,.r-mir,.r-no{margin:0;font-size:var(--fs-xs);color:var(--muted);line-height:1.6}
.r-sum{margin:0;font-size:var(--fs-sm);color:var(--fg);line-height:1.7;overflow-wrap:anywhere}
.r-up{font-style:italic}
/* the repository and mirror URLs are inline code: they take the canonical ``code``
   chip from ``THEME_CSS`` and nothing else. A local ``.8em`` used to ride the 12px
   meta line and render a GitHub URL at 9.6px, the smallest thing on the page. */
.r-decision{border:1px solid var(--border);border-radius:var(--r1);background:var(--layer-02);
padding:6px 9px}
.r-tags{display:flex;flex-wrap:wrap;gap:5px}
"""

_STYLE = BASE_CSS + RESOURCE_CSS + SHELL_CSS

_SCRIPT = """
function toggleTheme(){
  var h = document.documentElement;
  var n = h.dataset.theme === 'light' ? 'dark' : 'light';
  h.dataset.theme = n;
  try { localStorage.setItem('fde-theme', n); } catch(e) {}
}
var RES = {lic: 'all', rel: 'all'};
function chipPick(group, value, el){
  RES[group] = value;
  document.querySelectorAll('.chip[data-' + group + ']').forEach(function(c){
    var on = c.dataset[group] === value;
    c.classList.toggle('on', on);
    c.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  resFilter();
}
function resFilter(){
  var q = (document.getElementById('res-q').value || '').trim().toLowerCase();
  var shown = 0, total = 0;
  document.querySelectorAll('.rcard[data-t]').forEach(function(c){
    total++;
    var ok = (!q || c.dataset.t.indexOf(q) !== -1)
      && (RES.lic === 'all' || c.dataset.lic === RES.lic)
      && (RES.rel === 'all' || c.dataset.rel === RES.rel);
    c.hidden = !ok;
    if (ok) shown++;
  });
  var count = document.getElementById('res-count');
  if (count) count.textContent = (shown === total) ? String(total) : (shown + ' / ' + total);
  var empty = document.getElementById('res-empty');
  if (empty) empty.hidden = shown !== 0;
}
"""


def render(locale: str = "zh") -> str:
    """The GitHub-resource index as HTML. ``locale`` is ``"zh"`` or ``"en"``."""
    if locale not in ("zh", "en"):
        raise ValueError(f"unsupported locale: {locale!r}")
    en = locale == "en"

    def p(zh: str, eng: str) -> str:
        return eng if en else zh

    records = load_resources()
    core = sum(1 for r in records if r.relevance == "core")
    adj = sum(1 for r in records if r.relevance == "adjacent")
    mirrored = sum(1 for r in records if r.mirror)

    lang = "en" if en else "zh"
    other = "/resources" if en else "/en/resources"
    lang_label = "中文" if en else "EN"

    #: A filter is a control, so it is a ``<button>``: a ``<span>`` with an
    #: ``onclick`` is unreachable from the keyboard and gets no focus ring, and the
    #: catalog portal was already emitting buttons here — the two surfaces disagreed
    #: about the element, not just its radius. ``aria-pressed`` rather than
    #: ``role="radio"`` because a radio group obliges the widget to implement
    #: arrow-key navigation, and these are seven independent one-of-N toggles in two
    #: rows: Tab through them is the honest interaction, and the pressed state is the
    #: thing a screen reader has to be told.
    lic_chips = "".join(
        f'<button class="chip{" on" if val == "all" else ""}" type="button" '
        f'aria-pressed="{"true" if val == "all" else "false"}" data-lic="{val}" '
        f"onclick=\"chipPick('lic','{val}',this)\">{_esc(label)}</button>"
        for val, label in (
            ("all", p("全部许可", "all licences")),
            ("permissive", p("宽松可镜像", "permissive")),
            ("noassertion", "NOASSERTION"),
            ("none", "NONE"),
        )
    )
    rel_chips = "".join(
        f'<button class="chip{" on" if val == "all" else ""}" type="button" '
        f'aria-pressed="{"true" if val == "all" else "false"}" data-rel="{val}" '
        f"onclick=\"chipPick('rel','{val}',this)\">{_esc(label)}</button>"
        for val, label in (
            ("all", p("全部", "all")),
            ("core", p("核心", "core")),
            ("adjacent", p("相关", "adjacent")),
            ("noise", p("未审", "unreviewed")),
        )
    )

    out: list[str] = []
    add = out.append
    add(
        f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{p("GitHub 资源 · FDE Scope", "GitHub resources · FDE Scope")}</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{_STYLE}</style>
</head>
<body id="top">
__ICON_SPRITE__
<div class="shell">
<aside class="side">
<div class="brand">
<div class="logo">FDE <span>Scope</span></div>
<span class="tag">{p("GitHub 资源索引", "GitHub resource index")}</span>
</div>
<nav class="snav">
{side_nav("resources", en=en)}
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
<p class="eyebrow">{
            p("GitHub 资源 · forward-deployed engineer", "GitHub resources · forward-deployed engineer")
        }</p>
<h2>{
            p(
                "把 GitHub 上的 FDE 资源抓到本地、标注来源、可检索",
                "Harvested FDE repositories, provenance-stamped and searchable",
            )
        }</h2>
<p>{
            p(
                f"共建档 {len(records)} 个仓库（核心 {core} · 相关 {adj}），其中 {mirrored} 个许可宽松、"
                "已把 Markdown 正文逐字镜像到仓库本地。许可与相关度是两条正交的轴：宽松许可决定能否再分发"
                "正文，相关度决定值不值得看。无许可（NONE）与看不清（NOASSERTION）的仓库只存元数据 + 我们"
                "自撰的摘要 + 上游链接，正文不复制。GitHub 地址一律以纯文本呈现，不出站。",
                f"{len(records)} repositories catalogued ({core} core · {adj} adjacent); {mirrored} "
                "carry a permissive licence so their Markdown body is mirrored verbatim on disk. Licence "
                "and relevance are two orthogonal axes: a permissive licence decides whether we may "
                "redistribute the body, relevance decides whether it is worth reading. NONE (no licence) "
                "and NOASSERTION (unrecognised) repos keep metadata + our own summary + an upstream link "
                "only — the body is not copied. GitHub URLs are plain text; nothing leaves the site.",
            )
        }</p>
</div>
<div class="rbar">
<div class="rsearch">
<input id="res-q" type="search" aria-label="{p("搜索资源", "Search resources")}"
 placeholder="{p("按仓库名 / 许可 / 类目 / 关键词过滤…", "Filter by repo, licence, category, keyword…")}"
 oninput="resFilter()">
</div>
<span id="res-count" class="r-count" aria-live="polite">{len(records)}</span>
</div>
<div class="rchips">
<span class="chip-lbl">{p("许可", "licence")}</span>{lic_chips}
<span class="chip-lbl">{p("相关度", "relevance")}</span>{rel_chips}
</div>
<p id="res-empty" class="sec-note" hidden>{p("没有匹配的资源。", "No matching resources.")}</p>
<section id="index">
<div class="rl">"""
    )
    add(_record_cards(records, p, en))
    add(
        """</div>
</section>"""
    )
    add(
        f"""
<footer>
<span>{p("FDE Scope · GitHub 资源", "FDE Scope · GitHub resources")}</span>
<span>{
            p(
                "抓取快照，星标为采集时刻的值；正文镜像见 docs/github-resources/mirror",
                "A harvest snapshot; star counts are as-of-crawl. Verbatim bodies live under docs/github-resources/mirror",
            )
        }</span>
<a href="#top" class="totop">{p("回到顶部 ↑", "Back to top ↑")}</a>
</footer>

</div>
</main>
</div>
<script>{_SCRIPT}</script>
<script>{SHELL_JS}</script>
</body>
</html>
"""
    )
    return "".join(out)

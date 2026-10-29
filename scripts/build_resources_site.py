#!/usr/bin/env python3
"""生成 docs/github-resources/site/ 的单文件静态门户（离线双击可开、可被 /gh-resources 挂载）。

    make build-resources-site    # 等价 python3 scripts/build_resources_site.py

与 ``scripts/build_catalog_site.py`` 同构，但**数据源是 manifest**（而非 README
markdown）：读同一份 ``fde_scope/resources/data/resources.yaml``，把每仓一行序列化成
JSON 内联进 ``<script type="application/json">``，前端只做过滤/检索/渲染。

样式来自共享层，门户不复制令牌：
``CSS = COMPONENT_CSS + RESOURCE_CSS + CHROME``。``COMPONENT_CSS`` 已含 ``THEME_CSS``
（oklch ramp + ``html[data-theme]`` 主题契约），``RESOURCE_CSS`` 是资源卡片的**唯一定义**
——站内 /resources 与门户渲染的是同一个对象，过去各写一份于是漂移成 chip 2px/6px/999px、
badge 墨水 ``#fff`` 对 ``--accent-ink``。门户自己只留 masthead、查询框、镜像文件链接这些
「另一面没有的东西」的**摆放**。（不用 ``BASE_CSS``：那是 console 的 chrome。）

两条正交轴在门户里是两组独立 chip，永不合并（与站内 /resources 一致）：
``lic``∈{permissive,noassertion,none} · ``rel``∈{core,adjacent,noise}，外加「仅镜像」开关。

转义按信任边界分两处，不是两处都逃一遍：

* 上游文本（``upstream_description`` / ``repo`` / ``url`` / 许可串）在**数据里存原文**，
  由前端 JS 的 ``esc()`` 注入卡片时**统一转义一次**——建数据时再 ``html.escape`` 会造成
  ``&`` → ``&amp;amp;`` 的双重转义；
* 我们自撰的文案（标题、chip、说明段、页脚）在**服务端**用 ``html.escape(quote=True)``
  渲染，因此**不进 JS payload**：payload 的 ``l10n`` 只剩卡片要用的那一子集（``_CARD_KEYS``）。
  静态区（masthead / 搜索行 / chip 行 / 查询表 / 页脚）一律服务端出 HTML，直接双击打开时
  不跑 JS 也能读到页面骨架与全部统计，JS 只渲染 ``#rl`` 卡片列表。

其余诚实约束：

* GitHub URL 一律渲染成不可点的 ``<code>``，镜像正文用**站内相对链接**指向
  ``../mirror/<dir>/<file>``（zh）或 ``../../mirror/<dir>/<file>``（en），因此**整页不含
  任何 ``http`` 出站链接**（``tests/test_build_resources_site.py`` 钉死）；
* ``json.dumps`` 后把裸 ``<`` 换成 ``\\u003c``，防止某条 summary 里的 ``</script>`` 提前闭合；
* 顶部展示 ``snapshot.yaml`` 每条查询的 total_count + 实采页数 —— 「本次采集」而非全量。

镜像正文不进门户（920 KB / 最大单文件数十 KB），只给路径与相对链接：门户负责
「哪个仓库、本地哪、许可是什么、值不值得读」，全文检索交给 ``rg`` / 编辑器 / agent。
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from fde_scope.resources.repo import load_resources, load_snapshot
from fde_scope.web.layout import COMPONENT_CSS
from fde_scope.web.resources import _DECISION_CLAUSES_EN, RESOURCE_CSS, _lic_bucket

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "github-resources" / "site"
OUT = SITE / "index.html"

_REL_ORDER = {"core": 0, "adjacent": 1, "noise": 2}

#: The l10n keys the card template reads. Everything else is server-rendered and
#: must not ride in the payload, or it would have to be escaped twice (once at
#: build time, once by ``esc()`` on injection) to be safe either way.
_CARD_KEYS = (
    "star",
    "forkLbl",
    "archLbl",
    "updLbl",
    "snapLbl",
    "repolbl",
    "upLbl",
    "mirLbl",
    "noDesc",
    "trunc",
)


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


#: ``snapshot.yaml``'s ``note`` is authored by ``harvest.py`` in Chinese, the same
#: way ``license_decision_applied`` is authored in Chinese by ``_decision``. The
#: clause dictionary above is exported from ``fde_scope.web.resources`` because
#: two surfaces read it; this one is not, because the in-app ``/resources`` page
#: never shows the harvest note — only this portal does.
_SNAPSHOT_NOTE_EN = {
    "union 是「本次采集前若干页」的去重结果，不是全体匹配。in:readme / "
    "name,description 的全量命中远大于此；此处诚实记录 total_count 与实采页数。": "The union is de-duplicated across the pages this harvest actually fetched, not across "
    "every match on GitHub — in:readme and name,description return far more. total_count and "
    "pages fetched are recorded here exactly as the API returned them."
}


def _note_for(note: str, en: bool) -> str:
    """zh keeps the stored string; en takes the mapped translation or drops the line.

    Unmapped Chinese is never rendered onto ``/en`` — leaking the source language
    into a translated page is the failure this guard exists for, and the omission
    costs little because ``qNote`` already states the same caveat in both
    languages. ``tests/test_build_resources_site.py`` asserts every stored note is
    mapped, so a new note fails loudly at the test rather than vanishing quietly.
    """
    if not en:
        return note
    return _SNAPSHOT_NOTE_EN.get(note, "") if note else ""


def _decision_for(license_decision_applied: str, en: bool) -> str:
    """zh 用原文；en 只译子句、SPDX 头保持不动（与站内 _decision_line 同一规则）。"""
    if not en:
        return license_decision_applied
    head, sep, clause = license_decision_applied.partition(" → ")
    translated = _DECISION_CLAUSES_EN.get(clause)
    return f"{head} → {translated}" if sep and translated else license_decision_applied


def _row(rec, mirror_base: str, en: bool) -> dict:
    """一条记录 → 门户行对象。

    **所有值一律存原文**：门户 JS 的 ``esc()`` 是上游文本的唯一转义点（每个进
    innerHTML 的字段都过一次）。若在此再 :func:`html.escape` 一次，``&`` 会变
    ``&amp;amp;``——双重转义。``t`` 同样留原文，由 JS 转义一次后写进 ``data-t``
    供小写子串比较（与站内 /resources 的搜索字段同名同义）。
    """
    files = []
    if rec.mirror:
        for f in rec.files:
            files.append(
                {
                    "href": f"{mirror_base}{rec.mirror_dir}/{f.local_name}",
                    "name": f.path,
                    "truncated": bool(f.truncated),
                }
            )
    haystack = " ".join(
        [
            rec.slug,
            rec.repo,
            rec.url,
            rec.license_spdx,
            rec.relevance,
            " ".join(rec.categories),
            _decision_for(rec.license_decision_applied, en),
            (rec.summary_en if en else rec.summary_zh) or "",
            rec.upstream_description or "",
        ]
    ).casefold()
    return {
        "repo": rec.repo,
        "url": rec.url,
        "lic": _lic_bucket(rec.license_spdx),
        "spdx": rec.license_spdx,
        "rel": rec.relevance,
        "cats": list(rec.categories),
        "stars": rec.stars,
        "fork": rec.is_fork,
        "archived": rec.archived,
        "updated": rec.upstream_updated_at[:10],
        "snap": rec.snapshot_at[:10],
        "decision": _decision_for(rec.license_decision_applied, en),
        "summary": (rec.summary_en if en else rec.summary_zh) or "",
        "updesc": rec.upstream_description or "",
        "mirror": bool(rec.mirror),
        "mirrorDir": rec.mirror_dir if rec.mirror else "",
        "files": files,
        "reason": rec.mirror_reason if (rec.mirror_reason and not rec.mirror) else "",
        "t": haystack,
    }


def _l10n(lang: str, stats: dict) -> dict:
    en = lang == "en"

    def t(zh: str, eng: str) -> str:
        return eng if en else zh

    total, mirrored = stats["total"], stats["mirrored"]
    return {
        "htmlLang": "en" if en else "zh",
        "docTitle": t("GitHub FDE 资源 · 静态门户", "GitHub FDE resources · static portal"),
        "brandTag": t("GitHub 资源索引", "GitHub resource index"),
        "mastH1": t(
            "把 GitHub 上的 FDE 资源抓到本地、标注来源、可检索",
            "Harvested FDE repositories, provenance-stamped and searchable",
        ),
        "mastP": t(
            f"共建档 {total} 个仓库，其中 {mirrored} 个许可宽松，Markdown 正文已逐字镜像到 "
            "docs/github-resources/mirror。许可与相关度是两条正交的轴：前者决定能否再分发正文，"
            "后者决定值不值得读。无许可（NONE）与看不清（NOASSERTION）的仓库只留元数据、我们自撰的"
            "摘要与上游链接，正文不复制。GitHub 地址一律纯文本呈现，整页不出站。",
            f"{total} repositories catalogued; {mirrored} carry a permissive licence, so their "
            "Markdown body is mirrored verbatim under docs/github-resources/mirror. Licence and "
            "relevance are two orthogonal axes: the first decides whether we may redistribute the "
            "body, the second whether it is worth reading. NONE (no licence) and NOASSERTION "
            "(unrecognised) repos keep metadata, our own summary and an upstream link only — the "
            "body is not copied. GitHub URLs are plain text; nothing on this page leaves the site.",
        ),
        "statRepos": t("个仓库建档", "repos catalogued"),
        "statCore": t("核心", "core"),
        "statAdj": t("相关", "adjacent"),
        "statMir": t("逐字镜像", "mirrored verbatim"),
        "searchAria": t("搜索资源", "Search resources"),
        "searchPh": t(
            "按仓库名 / 许可 / 类目 / 关键词过滤…",
            "Filter by repo, licence, category, keyword…",
        ),
        "lblLic": t("许可", "licence"),
        "lblRel": t("相关度", "relevance"),
        "chipLic": [
            ("all", t("全部许可", "all licences")),
            ("permissive", t("宽松可镜像", "permissive")),
            ("noassertion", "NOASSERTION"),
            ("none", "NONE"),
        ],
        "chipRel": [
            ("all", t("全部", "all")),
            ("core", t("核心", "core")),
            ("adjacent", t("相关", "adjacent")),
            ("noise", t("未审", "unreviewed")),
        ],
        "mirrorOnly": t("仅看逐字镜像", "mirrored only"),
        "empty": t("没有匹配的资源。", "No matching resources."),
        "qHead": t("发现查询", "Discovery queries"),
        "qN": t("条查询", "queries"),
        "qNote": t(
            "每条查询在本次快照的 total_count 与实采页数——这是本次采集的截面，不是 GitHub 的全量，"
            "也不构成「已穷尽该主题」的断言。",
            "Total count and pages fetched per query for this snapshot — a cross-section of one "
            "harvest, not the whole of GitHub, and not a claim that the topic is exhausted.",
        ),
        "queryHits": t("命中", "hits"),
        "queryPages": t("实采页", "pages fetched"),
        "footBrand": t("FDE Scope · GitHub 资源", "FDE Scope · GitHub resources"),
        "footer": t(
            "抓取快照，星标为采集时刻的值；正文镜像见 docs/github-resources/mirror；"
            "GitHub 地址一律纯文本、不出站",
            "A harvest snapshot; star counts are as-of-crawl. Verbatim bodies live under "
            "docs/github-resources/mirror. GitHub URLs are plain text; nothing leaves the site.",
        ),
        "themeAria": t("切换深浅主题", "Toggle light/dark theme"),
        # 卡片专用（进 payload）：冒号是文案的一部分，不能写死在 JS 里——全角 ``：``
        # 落在英文页上就是漏译，而它不在 ``[一-鿿]`` 区间内，守卫正则看不见。
        "star": t("★", "★"),
        "forkLbl": t("fork", "fork"),
        "archLbl": t("已归档", "archived"),
        "updLbl": t("更新", "updated"),
        "snapLbl": t("采集", "snapshot"),
        "repolbl": t("仓库地址", "repository"),
        "upLbl": t("上游简介：", "upstream: "),
        "mirLbl": t("逐字镜像：", "verbatim mirror: "),
        "noDesc": t("（暂无简介）", "(no description)"),
        "trunc": t("截断", "truncated"),
        "langSwitch": t("EN", "中文"),
        "otherHref": "en/index.html" if not en else "../index.html",
    }


def build_data(lang: str) -> tuple[dict, dict]:
    """``(model, l10n)`` — everything the page needs, once, at build time.

    The model is a render model, not the shipped payload: it carries the metrics
    and the query log too, because the masthead, the stats row and the query
    section are server-rendered and never see the browser's JS. ``build_html``
    cuts the payload out of it (see ``_CARD_KEYS``), so the one place the split is
    enforced is the one place that writes ``<script type="application/json">``.
    """
    en = lang == "en"
    # zh 门户在 site/index.html，镜像在上一级 mirror/；en 在 site/en/index.html，需再上一级。
    mirror_base = "../../mirror/" if en else "../mirror/"
    recs = load_resources()
    recs = sorted(recs, key=lambda r: (_REL_ORDER.get(r.relevance, 3), -r.stars, r.slug))
    snap = load_snapshot()
    rows = [_row(r, mirror_base, en) for r in recs]
    core = sum(1 for r in recs if r.relevance == "core")
    adj = sum(1 for r in recs if r.relevance == "adjacent")
    mirrored = sum(1 for r in recs if r.mirror)
    queries = [
        {
            "query": q.query,
            "total": q.total_count,
            "pages": q.pages_fetched,
            "at": q.snapshot_at[:10],
        }
        for q in (snap.queries if snap else [])
    ]
    stats = {"total": len(recs), "core": core, "adjacent": adj, "mirrored": mirrored}
    model = {
        "lang": lang,
        "stats": stats,
        "queries": queries,
        "note": _note_for(snap.note if snap else "", en),
        "rows": rows,
    }
    return model, _l10n(lang, stats)


#: The theme toggle's two glyphs, inlined rather than referenced from the sprite
#: the app injects: a reader opens this file over ``file://`` as often as over
#: HTTP, and a ``<use href="#i-moon">`` would drag the app's whole sprite into a
#: standalone artifact to no purpose. Two paths cost less than that.
_SUN = (
    '<circle cx="8" cy="8" r="3.2"/>'
    '<path d="M8 1.2v1.8M8 13v1.8M1.2 8H3M13 8h1.8'
    'M3.2 3.2l1.3 1.3M11.5 11.5l1.3 1.3M12.8 3.2l-1.3 1.3M4.5 11.5l-1.3 1.3"/>'
)
_MOON = '<path d="M14 8.53A6 6 0 1 1 7.47 2 4.67 4.67 0 0 0 14 8.53z"/>'

#: The chrome this portal owns: its column, its masthead band, the query log and
#: the per-file mirror links. The appearance of anything with a shared meaning —
#: the metrics row, section heads, filter chips, the search field, the resource
#: card, the inline code chip, the footer — comes from ``COMPONENT_CSS`` and
#: ``RESOURCE_CSS`` above, so it cannot disagree with the app that renders the
#: same objects.
#:
#: The masthead is a band with a non-sticky identity row. That is a deliberate
#: departure from the catalog portal, which owns a sticky app bar: the bar is
#: sticky because it carries seven zone jumps and a search field a reader returns
#: to while scrolling a 900-entry list. This portal has no routes and no in-page
#: anchors, so a sticky row would spend 56px of the column to offer nothing —
#: and ``--z-sticky``, ``--nav-h`` and the ``[id]{scroll-margin-top}`` rule that
#: exists only to clear a sticky bar are not copied here either.
CHROME = """
.wrap{max-width:1080px;margin-inline:auto;padding-inline:var(--sp4)}
main{padding-block:var(--sp5) var(--sp6)}
/* One cadence between the chapters of the page; it hangs off the wrapper because
   the column is what holds the sections. */
.wrap>section+section{margin-top:var(--sp5)}
.masthead{background:var(--panel);border-bottom:1px solid var(--border);padding-block:var(--sp5)}
.mast-top{display:flex;align-items:center;gap:var(--sp2);flex-wrap:wrap}
.mast-top .brand{font-weight:650;font-size:var(--fs-h4);letter-spacing:var(--track-tight);color:var(--fg);
white-space:nowrap}
.mast-top .brand span{color:var(--accent-text)}
.mast-actions{display:flex;align-items:center;gap:var(--sp2);margin-left:auto;flex:none}
.masthead h1{margin:var(--sp3) 0 0;font-size:var(--fs-display);font-weight:650;
letter-spacing:var(--track-tight);line-height:1.2;text-wrap:balance;overflow-wrap:anywhere;max-width:28ch}
.masthead p{margin:var(--sp2) 0 0;color:var(--muted);max-width:75ch}
/* four dimensions, not the shared layer's fixed four equal columns: on a phone a
   150px floor is what turns the row into two-by-two instead of four hairline-thin
   cells. */
.masthead .stats{margin-top:var(--sp4);grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
/* The mirror toggle is the only Boolean in the chip row, and it has to read as a
   different kind of control from the seven one-of-N chips beside it before it is
   pressed. A dashed edge is the only cue available that is not colour: the ramp
   gives selected state to a fill and never to a stripe. */
.chip.mir{border-style:dashed}
/* The query log is data, not prose: rows divided by the same 1px hairline the
   metrics grid uses (a 1px gap over a border-coloured background), so the
   separation reads as structure rather than as air. */
.qlist{display:grid;gap:1px;background:var(--border);border:1px solid var(--border);
border-radius:var(--r1);overflow:hidden;margin-bottom:var(--sp3)}
.qrow{background:var(--bg2);padding:var(--sp2) var(--sp3);margin:0;
font:400 var(--fs-xs)/1.6 var(--mono);color:var(--muted);overflow-wrap:anywhere}
.qrow b{font-weight:600;color:var(--fg)}
.qnote{font-size:var(--fs-sm);color:var(--muted);line-height:1.7;margin:0;max-width:820px}
/* Per-file mirror links have no counterpart on /resources — the in-app page names
   the directory, the portal links the files — so this is the one genuinely
   portal-only component. It is a chip-shaped link, not a card: ``--r1`` corner,
   ``--border-strong`` boundary (a control edge is a graphic and clears 3:1), and
   hover takes the next layer step instead of an underline, because the console
   elevates by layer and underlines nothing. */
.files{display:flex;flex-wrap:wrap;gap:var(--sp1)}
.files a{font:500 var(--fs-xs)/1.5 var(--mono);color:var(--accent-text);text-decoration:none;
border:1px solid var(--border-strong);border-radius:var(--r1);padding:2px 8px;
transition:background-color var(--dur) var(--ease),border-color var(--dur) var(--ease)}
.files a:hover{background:var(--layer-02);border-color:var(--border-ink)}
@media(max-width:520px){.mast-top .brand span{display:none}}
"""

CSS = COMPONENT_CSS + RESOURCE_CSS + CHROME

JS = """
var L = {};
var ST = {lic: 'all', rel: 'all', mir: false};
function toggleTheme(){
  var h = document.documentElement;
  var n = h.dataset.theme === 'light' ? 'dark' : 'light';
  h.dataset.theme = n;
  try { localStorage.setItem('fde-theme', n); } catch(e) {}
}
/* Upstream text is untrusted and this is its only escape point; the payload's
   l10n labels go through it too, so the rule has no exceptions to remember. */
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function chipPick(group, value, el){
  ST[group] = value;
  document.querySelectorAll('.chip[data-' + group + ']').forEach(function(c){
    var on = c.dataset[group] === value;
    c.classList.toggle('on', on);
    c.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  resFilter();
}
function togMir(el){
  ST.mir = !ST.mir;
  el.classList.toggle('on', ST.mir);
  el.setAttribute('aria-pressed', ST.mir ? 'true' : 'false');
  resFilter();
}
/* The card is the app's card: same classes, same order, ``data-t`` for the
   search haystack. RESOURCE_CSS owns its appearance, so nothing here styles. */
function card(r){
  var flags = [r.stars + L.star];
  if (r.fork) flags.push(L.forkLbl);
  if (r.archived) flags.push(L.archLbl);
  var bits = '';
  if (r.summary) bits += '<p class="r-sum">' + esc(r.summary) + '</p>';
  if (r.updesc) bits += '<p class="r-up">' + esc(L.upLbl) + esc(r.updesc) + '</p>';
  if (!r.summary && !r.updesc) bits += '<p class="r-up">' + esc(L.noDesc) + '</p>';
  var cats = r.cats.map(function(c){ return '<span class="tag">' + esc(c) + '</span>'; }).join('');
  var mirBlock = '';
  if (r.mirror) {
    var fl = r.files.map(function(f){
      return '<a href="' + esc(f.href) + '">' + esc(f.name)
        + (f.truncated ? ' · ' + esc(L.trunc) : '') + '</a>';
    }).join('');
    mirBlock = '<p class="r-mir">' + esc(L.mirLbl) + '<code>docs/github-resources/mirror/'
      + esc(r.mirrorDir) + '</code></p><div class="files">' + fl + '</div>';
  } else if (r.reason) {
    mirBlock = '<p class="r-no">' + esc(r.reason) + '</p>';
  }
  return '<div class="rcard" data-t="' + esc(r.t) + '" data-lic="' + esc(r.lic)
    + '" data-rel="' + esc(r.rel) + '" data-mir="' + (r.mirror ? '1' : '0') + '">'
    + '<div class="r-head"><h3>' + esc(r.repo) + '</h3>'
    + '<span class="pill rel-' + esc(r.rel) + '">' + esc(r.rel) + '</span>'
    + '<span class="pill lic-' + esc(r.lic) + '">' + esc(r.spdx) + '</span></div>'
    + '<p class="r-url">' + esc(L.repolbl) + ' <code>' + esc(r.url) + '</code></p>'
    + bits
    + '<p class="r-meta">' + esc(flags.map(esc).join(' · ')) + ' · ' + esc(L.updLbl) + ' '
    + esc(r.updated) + ' · ' + esc(L.snapLbl) + ' ' + esc(r.snap) + '</p>'
    + '<div class="r-tags">' + cats + '</div>'
    + '<p class="r-decision">' + esc(r.decision) + '</p>'
    + mirBlock + '</div>';
}
function resFilter(){
  var q = (document.getElementById('res-q').value || '').trim().toLowerCase();
  var shown = 0, total = 0;
  document.querySelectorAll('.rcard[data-t]').forEach(function(c){
    total++;
    var ok = (!q || c.dataset.t.indexOf(q) !== -1)
      && (ST.lic === 'all' || c.dataset.lic === ST.lic)
      && (ST.rel === 'all' || c.dataset.rel === ST.rel)
      && (!ST.mir || c.dataset.mir === '1');
    c.hidden = !ok;
    if (ok) shown++;
  });
  var count = document.getElementById('res-count');
  if (count) count.textContent = (shown === total) ? String(total) : (shown + ' / ' + total);
  var empty = document.getElementById('res-empty');
  if (empty) empty.hidden = shown !== 0;
}
function boot(){
  var D = JSON.parse(document.getElementById('res-data').textContent);
  L = D.l10n;
  document.getElementById('rl').innerHTML = D.rows.map(card).join('');
  resFilter();
}
document.addEventListener('DOMContentLoaded', boot);
"""


def _chips(pairs: list[tuple[str, str]], attr: str) -> str:
    """One row of one-of-N filter buttons.

    ``<button type="button">`` and ``aria-pressed``, never a clickable ``<span>``
    — a span with an ``onclick`` is unreachable from the keyboard and gets no
    focus ring. ``aria-pressed`` rather than ``role="radio"`` because a radio
    group obliges the widget to implement arrow-key navigation, and these are
    independent one-of-N toggles in two rows: Tab is the honest interaction and
    the pressed state is the thing a screen reader has to be told.
    """
    return "".join(
        f'<button class="chip{" on" if val == "all" else ""}" type="button" '
        f'aria-pressed="{"true" if val == "all" else "false"}" data-{attr}="{val}" '
        f"onclick=\"chipPick('{attr}','{val}',this)\">{_esc(label)}</button>"
        for val, label in pairs
    )


def _stats(L: dict, stats: dict) -> str:
    cells = (
        (stats["total"], L["statRepos"]),
        (stats["core"], L["statCore"]),
        (stats["adjacent"], L["statAdj"]),
        (stats["mirrored"], L["statMir"]),
    )
    return "".join(
        f'<div class="stat"><div class="num">{_esc(f"{value:,}")}</div>'
        f'<div class="lab">{_esc(label)}</div></div>'
        for value, label in cells
    )


def _queries(L: dict, queries: list[dict], note: str) -> str:
    """The discovery log as a server-rendered data list, not a JS string."""
    rows = "".join(
        f'<p class="qrow"><b>{_esc(str(q["total"]))}</b> {_esc(L["queryHits"])} · '
        f"{_esc(L['queryPages'])} {_esc(str(q['pages']))} · {_esc(q['at'])}<br>{_esc(q['query'])}</p>"
        for q in queries
    )
    count = _esc(f"{len(queries)} {L['qN']}")
    tail = f'<p class="qnote">{_esc(note)}</p>' if note else ""
    return f"""<section>
<div class="sec-head"><h2>{_esc(L["qHead"])}</h2><span class="n">{count}</span></div>
<p class="sec-note">{_esc(L["qNote"])}</p>
<div class="qlist">{rows}</div>
{tail}
</section>"""


def _payload(model: dict, L: dict) -> dict:
    """Exactly what the JS reads: the rows, plus only the labels the card uses.

    The note and the query log are server-rendered, and every other label was
    already emitted at build time — shipping them too would put the same string
    on the page twice, once escaped by ``_esc`` and once by ``esc()`` on
    injection, which is the double-escape bug this split exists to prevent.
    """
    return {
        "l10n": {k: L[k] for k in _CARD_KEYS},
        "rows": model["rows"],
    }


def build_html(model: dict, L: dict) -> str:
    # `<script type="application/json">` 里不能出现裸 `<`：否则 summary 里的 `</script>`
    # 会提前闭合、吞掉整页。`\u003c` 是合法 JSON 转义，parse 后还原成 `<`。
    payload = json.dumps(_payload(model, L), ensure_ascii=False).replace("<", "\\u003c")
    stats = model["stats"]
    queries = model["queries"]
    total = stats["total"]
    return f"""<!DOCTYPE html>
<html lang="{L["htmlLang"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(L["docTitle"])}</title>
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{CSS}</style>
</head>
<body>
<header class="masthead"><div class="wrap">
<div class="mast-top">
<div class="brand">FDE <span>Scope</span></div>
<span class="tag">{_esc(L["brandTag"])}</span>
<div class="mast-actions">
<a class="lang" href="{_esc(L["otherHref"])}">{_esc(L["langSwitch"])}</a>
<button class="tbtn" type="button" onclick="toggleTheme()" aria-label="{_esc(L["themeAria"])}" title="{_esc(L["themeAria"])}">
<svg class="ic when-light" viewBox="0 0 16 16" aria-hidden="true">{_MOON}</svg>
<svg class="ic when-dark" viewBox="0 0 16 16" aria-hidden="true">{_SUN}</svg>
</button>
</div>
</div>
<h1>{_esc(L["mastH1"])}</h1>
<p>{_esc(L["mastP"])}</p>
<div class="stats">{_stats(L, stats)}</div>
</div></header>
<main class="wrap">
<section>
<div class="rbar">
<div class="rsearch">
<input id="res-q" type="search" aria-label="{_esc(L["searchAria"])}" placeholder="{_esc(L["searchPh"])}"
 oninput="resFilter()">
</div>
<span id="res-count" class="r-count" aria-live="polite">{_esc(f"{total:,}")}</span>
</div>
<div class="rchips">
<span class="chip-lbl">{_esc(L["lblLic"])}</span>{_chips(L["chipLic"], "lic")}
<span class="chip-lbl">{_esc(L["lblRel"])}</span>{_chips(L["chipRel"], "rel")}
<button class="chip mir" type="button" aria-pressed="false" onclick="togMir(this)">{_esc(L["mirrorOnly"])}</button>
</div>
<p id="res-empty" class="sec-note" hidden>{_esc(L["empty"])}</p>
<div class="rl" id="rl"></div>
</section>
{_queries(L, queries, model["note"])}
<footer>
<span>{_esc(L["footBrand"])}</span>
<span>{_esc(L["footer"])}</span>
</footer>
</main>
<script id="res-data" type="application/json">{payload}</script>
<script>{JS}</script>
</body>
</html>
"""


def build_page(lang: str) -> str:
    model, l10n = build_data(lang)
    return build_html(model, l10n)


def main() -> None:
    outputs = (("zh", OUT), ("en", SITE / "en" / "index.html"))
    for lang, out in outputs:
        model, l10n = build_data(lang)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_html(model, l10n), encoding="utf-8")
        s = model["stats"]
        print(
            f"OK {out.relative_to(ROOT)} ｜ {s['total']} 条（核心 {s['core']} · "
            f"相关 {s['adjacent']} · 镜像 {s['mirrored']}）｜ {out.stat().st_size // 1024} KB"
        )


if __name__ == "__main__":
    sys.exit(main())

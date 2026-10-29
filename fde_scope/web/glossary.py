"""The standalone glossary page (``/glossary``, ``/en/glossary``).

Rendered from paired literals rather than through :func:`fde_scope.web.i18n.to_en`
because the whole page *is* vocabulary: a single missing pair would ship
Chinese terms onto ``/en/glossary`` with no error. The two lists live in
``i18n.GLOSSARY_ZH`` / ``i18n.GLOSSARY_EN`` under identical keys, so a term
cannot exist in only one language; ``render`` picks the list and the group
labels by locale.

Every term belongs to exactly one group in :data:`_GROUPS`. Terms that are
not listed there fall into a trailing catch-all group, and
``tests/test_web.py`` asserts that catch-all is empty — adding a glossary
entry without filing it is a test failure, not a silently unlisted word.

The tips are this site's own one-line glosses, written to make the SOP and
the certification material readable. They are not vendor documentation and
carry no provenance claim.
"""

import html

from .i18n import GLOSSARY_EN, GLOSSARY_ZH
from .layout import BASE_CSS, SHELL_CSS, SHELL_JS, side_nav

#: (icon id, zh label, en label, zh blurb, en blurb, terms) — order is page order.
_GROUPS: list[tuple[str, str, str, str, str, list[str]]] = [
    (
        "i-compass",
        "驻场方法论",
        "Field method",
        "从第一次现场走查到原型验证：这套 SOP 里的角色、阶段与推进动词。",
        "From the first shop-floor walk to a working prototype: the roles, phases "
        "and verbs this SOP runs on.",
        [
            "Gemba walk",
            "Gemba",
            "FDE",
            "Engagements",
            "Engagement",
            "SOP",
            "zones",
            "Zone",
            "qualification",
            "stakeholder_map",
            "prototype",
            "force",
        ],
    ),
    (
        "i-shield",
        "门禁与合规",
        "Gates & compliance",
        "推进阶段时每次重新评估的谓词，以及签约侧必须落实的硬条件。",
        "The predicates re-evaluated on every phase advance, plus the hard conditions "
        "the contract side has to meet.",
        [
            "Gates",
            "Gate",
            "门禁",
            "overlay",
            "FAT/SAT",
            "sponsor",
            "success_criteria",
            "成功标准",
        ],
    ),
    (
        "i-db",
        "数据与语料",
        "Data & corpus",
        "场景配置与数据本身：接入什么、怎么锻造、什么算够。",
        "Scenario configuration and the data itself: what to ingest, how to forge it, "
        "and what counts as enough.",
        [
            "Context",
            "干系人",
            "Profile",
            "ticket",
            "manufacturing",
            "KPI",
            "Corpus",
            "语料锻造",
            "PII",
            "min_samples",
            "synth_per_gap",
            "JSONL",
            "stub",
        ],
    ),
    (
        "i-factory",
        "工业与机器人",
        "Industrial & robotics",
        "车间侧的数据源、协议与产线指标。",
        "Shop-floor data sources, protocols and production-line metrics.",
        [
            "ISA-95",
            "MES",
            "OPC UA",
            "OPC",
            "PLC",
            "MQTT-Sparkplug",
            "ROS2 Bag",
            "Historian",
            "OEE",
            "MTBF",
            "pick success",
            "DexNet",
        ],
    ),
    (
        "i-alert",
        "安全与法规",
        "Safety & regulation",
        "功能安全等级、部署形态与劳动法共决——写进 gate 的那部分合规。",
        "Functional-safety levels, deployment shapes and labour co-determination — "
        "the compliance that becomes gates.",
        [
            "功能安全",
            "ISO 13849",
            "IEC 61508",
            "ISO 10218",
            "CE",
            "EU AI Act",
            "PLr",
            "SIL",
            "works_council",
            "工会",
            "air-gapped",
            "气隙",
            "OT/IT 隔离",
            "班次",
        ],
    ),
    (
        "i-gauge",
        "运营与退场",
        "Operations & exit",
        "上线之后：服务承诺、漂移监测、回流飞轮与交接退场。",
        "After go-live: service commitments, drift monitoring, the backflow flywheel, and the exit.",
        [
            "SLO",
            "SLA",
            "on-call",
            "告警路由",
            "runbook",
            "移交包",
            "drift",
            "漂移",
            "Flywheel",
            "飞轮",
            "bad case",
        ],
    ),
    (
        "i-cpu",
        "平台与工具",
        "Platform & tooling",
        "AgentScope 运行时概念、外部系统，以及工作台里的功能名。",
        "AgentScope runtime concepts, external systems, and the feature names inside the workbench.",
        [
            "Zammad",
            "Salesforce",
            "RAG",
            "ACA",
            "ACP",
            "AgentState",
            "Toolkit",
            "SubAgentTemplate",
            "技能库",
            "工作台",
            "现场记录",
            "沉淀",
        ],
    ),
]

#: English labels for the CJK-keyed terms. Each tip in ``GLOSSARY_EN`` opens
#: with its English term, so these are read off existing content rather than
#: invented. ``tests/test_web.py`` pins totality over the CJK keys.
_EN_TERM: dict[str, str] = {
    "气隙": "Air-gapped",
    "OT/IT 隔离": "OT/IT separation",
    "班次": "Shift system",
    "工会": "Works council",
    "告警路由": "Alert route",
    "移交包": "Handoff package",
    "干系人": "Stakeholder",
    "成功标准": "Success criteria",
    "功能安全": "Functional safety",
    "语料锻造": "Corpus forging",
    "飞轮": "Flywheel",
    "漂移": "Drift",
    "技能库": "Skills library",
    "工作台": "Workbench",
    "现场记录": "Journal",
    "沉淀": "Consolidate",
    "门禁": "Gates",
}

_CATCH_ALL = (
    "i-box",
    "其他",
    "Other",
    "尚未归组的词条。",
    "Terms not yet filed into a group.",
)


def _is_cjk(term: str) -> bool:
    return any(ord(c) > 127 for c in term)


def _group_terms(terms: list[str]) -> list[list[str]]:
    """Terms in :data:`_GROUPS` order, then a catch-all for anything unlisted."""
    listed = {t for *_, group in _GROUPS for t in group}
    groups = [sorted(group, key=str.casefold) for *_, group in _GROUPS]
    rest = sorted((t for t in terms if t not in listed), key=str.casefold)
    if rest:
        groups.append(rest)
    return groups


def _label(term: str, en: bool) -> str:
    return _EN_TERM.get(term, term) if en and _is_cjk(term) else term


_STYLE = (
    BASE_CSS
    + """
.gsearch{display:flex;gap:var(--sp3);align-items:center;margin:var(--sp3) 0 0;max-width:860px}
/* metrics come from the canonical ``input`` rule in ``THEME_CSS``; a search field
   in a flex row grows instead of filling. */
.gsearch input{flex:1;min-width:0}
.gl-count{font:600 var(--fs-xs)/1.5 var(--mono);color:var(--muted);white-space:nowrap}
.totop{margin-left:auto;color:var(--muted);text-decoration:none;font-size:var(--fs-sm)}
.totop:hover{color:var(--accent-text)}
.gl{display:grid;gap:var(--sp3);margin:0}
.gl .card{background:var(--panel);border:1px solid var(--border);border-radius:var(--r2);
padding:13px 15px;min-width:0;transition:border-color var(--dur) var(--ease)}
.gl .card:hover{border-color:var(--border-strong)}
.gl dt{font-weight:600;font-size:var(--fs-body);color:var(--fg);overflow-wrap:anywhere}
.gl dt .alias{font:400 var(--fs-xs)/1.5 var(--mono);color:var(--muted);margin-left:7px}
.gl dd{margin:5px 0 0;color:var(--muted);font-size:var(--fs-sm);line-height:1.7}
@media(max-width:960px){
.cols-4,.cols-3,.gl{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:640px){
.cols-4,.cols-3,.cols-2,.gl{grid-template-columns:1fr}
.hero{padding:6px 0 24px}footer{flex-direction:column}
}
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
function glFilter(q){
  q = q.trim().toLowerCase();
  var shown = 0, total = 0;
  document.querySelectorAll('.card[data-t]').forEach(function(c){
    total++;
    var hit = !q || c.dataset.t.indexOf(q) !== -1;
    c.hidden = !hit;
    if (hit) shown++;
  });
  document.querySelectorAll('section[id^=g]').forEach(function(s){
    var any = s.querySelector('.card[data-t]:not([hidden])');
    s.hidden = !any;
  });
  var count = document.getElementById('gl-count');
  if (count) count.textContent = q ? (shown + ' / ' + total) : '';
  var empty = document.getElementById('gl-empty');
  if (empty) empty.hidden = shown !== 0;
}
"""


def render(locale: str = "zh") -> str:
    """The glossary as HTML. ``locale`` is ``"zh"`` or ``"en"``."""
    if locale not in ("zh", "en"):
        raise ValueError(f"unsupported locale: {locale!r}")
    en = locale == "en"

    def p(zh: str, eng: str) -> str:
        return eng if en else zh

    keys = [term for term, _ in (GLOSSARY_EN if en else GLOSSARY_ZH)]
    tips = dict(GLOSSARY_EN if en else GLOSSARY_ZH)
    groups = _group_terms(keys)

    heads = [group[:5] for group in _GROUPS]
    if len(groups) > len(_GROUPS):
        heads.append(_CATCH_ALL)

    lang = "en" if en else "zh"
    other = "/glossary" if en else "/en/glossary"
    lang_label = "中文" if en else "EN"

    # The letter-group anchors as ``side_nav`` leaf entries: the same ``heads``
    # list drives the page's section ids, so the rail cannot drift from the body.
    subnav = tuple((f"#g{idx:02d}", head[2] if en else head[1]) for idx, head in enumerate(heads, 1))

    out: list[str] = []
    add = out.append
    add(
        f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{p("名词解释 · FDE Scope", "Glossary · FDE Scope")}</title>
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
<span class="tag">{p("现场词汇表", "field vocabulary")}</span>
</div>
<nav class="snav">
{side_nav("glossary", en=en, subnav=subnav)}
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
<p class="eyebrow">{p("名词解释 · 现场词汇", "Glossary · field vocabulary")}</p>
<h2>{p("这套材料里的每个词，一行讲清", "Every term in this material, one line each")}</h2>
<p>{
            p(
                "SOP、认证大纲与控制台界面共用的词汇表。原先嵌在正文里的小标签已经移除——"
                "正文只留完整的句子，术语集中到这里，按主题分组。",
                "The vocabulary shared by the SOP, the certification outline and the console UI. "
                "The inline badges that used to sit in the body text are gone: the prose keeps only "
                "whole sentences, and the terms are collected here, grouped by theme.",
            )
        }</p>
</div>
<div class="gsearch">
<input id="gl-q" type="search" aria-label="{p("搜索术语", "Search terms")}"
 placeholder="{p("输入关键词即时过滤…", "Type to filter instantly…")}" oninput="glFilter(this.value)">
<span id="gl-count" class="gl-count" aria-live="polite"></span>
</div>
<p id="gl-empty" class="sec-note" hidden>{p("没有匹配的术语。", "No matching terms.")}</p>"""
    )
    for idx, (head, group) in enumerate(zip(heads, groups), 1):
        _, zh_label, en_label, zh_blurb, en_blurb = head
        add(
            f"""
<section id="g{idx:02d}">
<div class="sec-head">
<svg class="ic" aria-hidden="true"><use href="#{head[0]}"/></svg>
<h2>{en_label if en else zh_label}</h2>
<span class="n">{idx:02d}</span>
</div>
<p class="sec-note">{en_blurb if en else zh_blurb}</p>
<dl class="gl cols-2">"""
        )
        for term in group:
            label = _label(term, en)
            alias = (
                f'<span class="alias">{html.escape(term)}</span>'
                if label.casefold() != term.casefold()
                else ""
            )
            # the haystack also carries the alias and the gloss, so a search
            # for either language's wording finds the card
            haystack = html.escape(f"{label} {term} {tips[term]}".casefold(), quote=True)
            add(
                f"""<div class="card" data-t="{haystack}">
<dt>{html.escape(label)}{alias}</dt>
<dd>{html.escape(tips[term])}</dd>
</div>"""
            )
        add("""</dl>
</section>""")
    add(
        f"""
<footer>
<span>{p("FDE Scope · 名词解释", "FDE Scope · Glossary")}</span>
<span>{p("本站自撰的一行释义，非厂商文档", "One-line glosses written for this site, not vendor documentation")}</span>
<a href="#top" class="totop">{p("回到顶部 ↑", "Back to top ↑")}</a>
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

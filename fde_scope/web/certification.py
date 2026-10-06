"""The ``/certification`` page: FDE certification specs, exam outline, study guide.

Why a renderer instead of the ``app.py`` "HTML string + ``to_en``" pattern: this
page's copy is read off vendor documentation and has to stay parallel in both
locales. ``to_en`` is an exact-substring replace pass, and a single miss would
silently ship Chinese on ``/en/certification``. Here the Chinese and English
strings sit next to each other in the source, so a translator cannot forget one.

Provenance is the point of this page, so it is encoded, not decorative. Every
figure is one of:

``OFFICIAL``
    Read off the vendor's own page — the URL is in :data:`_SOURCES`.
``NOTED``
    From a third-party study note. The copy says so, next to the number.
``GAP``
    No public source exists. The page states the gap rather than filling it.

Do not add a number without saying which of the three it is. The page is a
reference people will study from; a plausible-looking invented exam question or
pass mark is worse than an admitted hole. ``tests/test_web.py`` pins the three
disclaimers that keep this honest.

When a vendor publishes only part of a spec, say which part is missing rather
than completing it. Alibaba publishes the ACP mark allocation (so a total of 100
is arithmetic) but no pass mark — the page prints the first and refuses to
invent the second. Same rule for a partially-public vendor story: Volcengine
runs a certification platform and publishes partner tiers, but no LLM subject,
so the tile says both.
"""

from __future__ import annotations

from .layout import BASE_CSS, SHELL_CSS, SHELL_JS

# ---------------------------------------------------------------------------
# Sources — rendered as the provenance table, and the reason each claim is OK.
# ---------------------------------------------------------------------------
# (label_zh, label_en, url, tier). An empty url means "no public page to link".
_SOURCES: list[tuple[str, str, str, str]] = [
    (
        "腾讯云培训认证 · 认证科目列表（OPC 从业者 / 应用师，线上与线下理论）",
        "Tencent Cloud Training · certification catalogue (OPC Practitioner / "
        "Practitioner, online and offline theory)",
        "https://cloud.tencent.com/developer/training",
        "OFFICIAL",
    ),
    (
        "腾讯云文档 658/134240 · WorkBuddy 效率智能体应用师考试细则（题型、时长、及格线、模块权重）",
        "Tencent Cloud doc 658/134240 · WorkBuddy Efficiency Agent Practitioner exam "
        "specification (question types, duration, pass mark, module weights)",
        "https://cloud.tencent.com/document/product/658/134240",
        "OFFICIAL",
    ),
    (
        "腾讯云认证 1056 · WorkBuddy 效率智能体 OPC 从业者（100/70 分、90 分钟、3 次考试机会、¥330、2 年有效期、实名主账号 + 人脸核身）",
        "Tencent Cloud cert 1056 · WorkBuddy Efficiency Agent OPC Practitioner "
        "(100/70, 90 min, 3 attempts, ¥330, 2-year validity, verified main account + face check)",
        "https://cloud.tencent.com/edu/cert/developer/1056",
        "OFFICIAL",
    ),
    (
        "腾讯云课程 · OPC 从业者备考课程（11 模块 / 31 章节 / 约 6 小时，证书编号可在线核验）",
        "Tencent Cloud course · OPC Practitioner course (11 modules / 31 chapters / ~6 h; "
        "certificate number verifiable online)",
        "https://cloud.tencent.com/edu/training/workbuddy-opc-cert",
        "OFFICIAL",
    ),
    (
        "腾讯云文档 563/137252 · 代理合作伙伴准入条件（注册资金、团队规模、两门渠道考试、保证金与保密承诺书）",
        "Tencent Cloud doc 563/137252 · agent partner admission conditions (registered "
        "capital, team size, the two channel exams, deposits and the confidentiality undertaking)",
        "https://cloud.tencent.com/document/product/563/137252",
        "OFFICIAL",
    ),
    (
        "阿里云认证 · 大模型工程师 ACA（aca13）：费用、有效期、考试机会",
        "Alibaba Cloud certification · LLM Engineer ACA (aca13): fee, validity, exam attempts",
        "https://edu.aliyun.com/certification/aca13",
        "OFFICIAL",
    ),
    (
        "阿里云认证 · 大模型高级工程师 ACP（acp26）：费用、有效期、考试机会",
        "Alibaba Cloud certification · Senior LLM Engineer ACP (acp26): fee, validity, exam attempts",
        "https://edu.aliyun.com/certification/acp26",
        "OFFICIAL",
    ),
    (
        "阿里云公告 · 大模型 ACP 考试大纲变更：题型、每题分值与六大知识域权重（不含及格线）",
        "Alibaba Cloud announcement · LLM ACP outline change: question types, per-question "
        "marks and the six domain weights (no pass mark)",
        "https://help.aliyun.com/zh/document_detail/2986614.html",
        "OFFICIAL",
    ),
    (
        "阿里云合作伙伴 · 代理伙伴准入条件（注册资本、保证金、员工数、成立年限）",
        "Alibaba Cloud partner programme · agent partner admission conditions (registered "
        "capital, deposit, headcount, years in business)",
        "https://help.aliyun.com/zh/document_detail/677705.html",
        "OFFICIAL",
    ),
    (
        "阿里云伙伴技术认证 · ASE-X / APE-X 体系（伙伴架构师与售前方向，计入伙伴级别晋升）",
        "Alibaba Cloud partner certification · ASE-X / APE-X track (partner architects and "
        "pre-sales; feeds partner-tier promotion)",
        "https://edu.aliyun.com/certification/partner",
        "OFFICIAL",
    ),
    (
        "火山引擎合作伙伴 · 代理商分级与准入（六档、业绩与认证人数门槛、注册资金与年限）",
        "Volcengine partner programme · agent tiers and admission (six tiers, revenue and "
        "certified-headcount gates, registered capital and company age)",
        "https://partner.volcengine.com/partner/agent",
        "OFFICIAL",
    ),
    (
        "火山引擎赋能平台 · 未检索到 TRAE / 大模型方向的公开认证目录",
        "Volcengine enablement platform · no public TRAE / LLM certification catalogue is indexed",
        "https://edu.volcengine.com/",
        "GAP",
    ),
    (
        "标题为「火山引擎技能认证考试平台」（第三方运营）· 目录仅数智增长营销与 A/B 测试两科，均非大模型方向",
        "A platform titled 'Volcengine skills certification exam' (third-party operated) · "
        "catalogue holds only two non-LLM subjects",
        "https://certexam.edu360.cn/",
        "GAP",
    ),
    (
        "阿里云千问办公 · 官方产品页（企业标准版 ¥198/席/月、企业旗舰版 ¥298/席/月 100 席起购、积分包 ¥100 起）",
        "Alibaba Cloud QwenWork · product page (Standard ¥198/seat/month, Flagship ¥298/seat/month "
        "from 100 seats, credit packs from ¥100)",
        "https://www.aliyun.com/product/qwenwork",
        "OFFICIAL",
    ),
    (
        "阿里云文档 · 伙伴经营管理指引（技能认证须在财年结算前，即每年 3 月 31 日完成绑定）",
        "Alibaba Cloud doc · partner operations guide (skill certificates must be bound before fiscal "
        "year settlement, i.e. by 31 March each year)",
        "https://help.aliyun.com/zh/document_detail/728665.html",
        "OFFICIAL",
    ),
    (
        "阿里云文档 · 技能认证证书绑定 / 解绑操作（持证人须 7 个工作日内确认）",
        "Alibaba Cloud doc · binding and unbinding skill certificates (holder must confirm within "
        "7 working days)",
        "https://help.aliyun.com/zh/document_detail/273110.html",
        "OFFICIAL",
    ),
    (
        "第三方整理材料（非官方）· 千问办公政企培训与返点口径，未逐条重抓核对",
        "Third-party compiled material (unofficial) · QwenWork public-sector training and "
        "rebate figures, not re-verified line by line",
        "",
        "NOTED",
    ),
]

_TIER_LABEL = {
    "OFFICIAL": ("官方", "official"),
    "NOTED": ("第三方", "noted"),
    "GAP": ("缺口", "gap"),
}

# ---------------------------------------------------------------------------
# Exam specifications. Weights are percentages; they are asserted to total 100
# in tests/test_web.py so a typo cannot quietly ship.
# ---------------------------------------------------------------------------
_WORKBUDDY_APPLICATION_WEIGHTS: list[tuple[str, str, int]] = [
    ("初识", "Foundations", 12),
    ("高效对话", "Effective dialogue", 20),
    ("职场实战", "Workplace in practice", 20),
    ("进阶功能", "Advanced features", 18),
    ("安全合规", "Security and compliance", 18),
    ("企业构建", "Enterprise build-out", 12),
]

_ALIYUN_ACP_WEIGHTS: list[tuple[str, str, int]] = [
    ("RAG", "RAG", 20),
    ("大模型应用开发", "LLM application development", 17),
    ("微调", "Fine-tuning", 16),
    ("多 Agent 及多模态", "Multi-agent and multimodal", 16),
    ("生产环境应用实践", "Production practice", 16),
    ("提示词工程", "Prompt engineering", 15),
]

# The concept index. Module weights above are published numbers; this list is a
# curated summary of concepts the public outline touches, not a chapter mapping
# — the copy labels it as such, so keep the wording loose.
_OUTLINE_CONCEPTS: list[tuple[str, str]] = [
    (
        "智能体与聊天式 AI 的边界（可操作本地文件、可执行多步任务）",
        "Where an agent differs from chat AI (it can touch local files and run multi-step work)",
    ),
    ("三层架构：Agent / Runtime / Session", "Three-layer architecture: Agent / Runtime / Session"),
    ("记忆层级与上下文管理", "Memory tiers and context management"),
    ("提示词四要素", "The four elements of a prompt"),
    ("Ask / Plan / Craft 三档风险分级", "Ask / Plan / Craft risk tiers"),
    ("数据流向与本地、云端处理边界", "Data flow and the local-versus-cloud boundary"),
    ("企业侧治理：账号、权限、审计", "Enterprise governance: accounts, permissions, audit"),
    ("安全合规：脱敏、留痕、可追溯", "Security and compliance: redaction, logging, traceability"),
]

# ---------------------------------------------------------------------------
# The channel due-diligence checklist. These are the dimensions a partner
# agreement is negotiated on. Part of the picture is now public (see the "hard
# gates" tile in section 07 and the per-vendor rows it carries); the rest is
# still answered privately per vendor, so the checklist stays the deliverable.
# ---------------------------------------------------------------------------
_DUE_DILIGENCE: list[tuple[str, str]] = [
    ("渠道载体与官方准入文档名称", "Channel vehicle and the name of the official admission document"),
    ("注册资金与成立年限门槛", "Registered capital and years-in-business thresholds"),
    ("人员配置要求（专职人数、岗位）", "Headcount requirements (dedicated staff, roles)"),
    ("保证金 / 履约金及其退还条件", "Deposit / performance bond and its refund conditions"),
    ("专项考试与最低通过人数", "Vendor-specific exam and the minimum number of passers"),
    ("FDE 能力要求（交付、实施、售后）", "FDE capability requirements (delivery, implementation, support)"),
    ("伙伴认证品牌与等级", "Partner accreditation brand and tier"),
    ("分级业绩门槛（年度 / 季度）", "Tiered revenue thresholds (annual / quarterly)"),
    ("激励政策：返点、市场基金、培训支持", "Incentives: rebates, market funds, training support"),
    ("价格锚点：企业版 / 行业版报价", "Price anchors: enterprise and industry editions"),
    ("市场阶段（试点 / 扩张 / 饱和）", "Market stage (pilot / expansion / saturated)"),
    ("续约与退出条款", "Renewal and exit terms"),
]

_STYLE = (
    BASE_CSS
    + """
.status{display:inline-flex;align-items:center;gap:6px;margin-top:10px;padding:2px 9px;border:1px solid var(--border);
border-radius:999px;font:500 11px/1.6 var(--mono);color:var(--muted)}
.status::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--faint);flex:none}
.s-ok::before{background:var(--good)}
.s-partial::before{background:var(--warn)}
.s-stub::before{background:var(--bad)}
.step-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.zone{background:var(--panel);border:1px solid var(--border);border-radius:9px;padding:14px 16px;min-width:0}
.zone .ztag{font:600 10.5px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.zone .zname{font-size:.95rem;font-weight:650;margin:6px 0 10px}
.zone ol{margin:0;padding:0;list-style:none;font-size:.82rem;color:var(--muted)}
.zone li{display:flex;align-items:flex-start;gap:7px;padding:5px 0;border-top:1px solid var(--border);line-height:1.5}
.zone li:first-child{border-top:0}
.zone li b{color:var(--fg);font:600 .76rem/1.5 var(--mono)}
.kpi-row{display:flex;justify-content:space-between;align-items:baseline;gap:8px;padding:5px 0;border-bottom:1px solid var(--border);font-size:.8rem;color:var(--muted)}
.kpi-row:last-child{border:0}
.kpi-row .v{font:700 .85rem var(--mono);color:var(--fg);text-align:right}
.tier{display:inline-flex;align-items:center;font:600 10px/1.7 var(--mono);letter-spacing:.08em;padding:1px 8px;
border-radius:999px;border:1px solid var(--border);color:var(--muted);text-transform:uppercase;white-space:nowrap}
.tier.official{color:var(--good);border-color:color-mix(in oklab,var(--good) 42%,var(--border))}
.tier.noted{color:var(--warn);border-color:color-mix(in oklab,var(--warn) 42%,var(--border))}
.tier.gap{color:var(--bad);border-color:color-mix(in oklab,var(--bad) 42%,var(--border))}
.tblwrap{overflow-x:auto;border:1px solid var(--border);border-radius:9px;background:var(--panel)}
table.tbl{width:100%;border-collapse:collapse;font-size:.83rem}
table.tbl th,table.tbl td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:top}
table.tbl th{font:600 .7rem/1.5 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);white-space:nowrap}
table.tbl tr:last-child td{border-bottom:0}
table.tbl td b{color:var(--fg)}
table.tbl td.num{font:700 .82rem var(--mono);color:var(--fg);white-space:nowrap}
table.tbl td .cite{font:.76rem/1.6 var(--mono);color:var(--muted);overflow-wrap:anywhere}
.wrow{display:flex;align-items:center;gap:10px;padding:6px 0;border-top:1px solid var(--border);font-size:.82rem}
.wrow:first-child{border-top:0}
.wrow .wl{flex:1;min-width:0;color:var(--muted)}
.wrow .wbar{flex:none;width:104px;height:6px;border-radius:99px;background:var(--panel2);overflow:hidden}
.wrow .wbar i{display:block;height:100%;background:var(--accent);border-radius:99px}
.wrow .wv{font:700 .8rem var(--mono);color:var(--fg);white-space:nowrap;width:38px;text-align:right}
.qa{background:var(--panel);border:1px solid var(--border);border-radius:9px;margin:0}
.qa summary{cursor:pointer;padding:12px 16px;font-weight:600;font-size:.88rem;list-style:none;
display:flex;gap:10px;align-items:flex-start;line-height:1.6}
.qa summary::-webkit-details-marker{display:none}
.qa summary::before{content:"Q";font:700 10.5px/1.7 var(--mono);color:var(--accent);border:1px solid var(--border);
border-radius:5px;padding:0 5px;flex:none;margin-top:2px}
.qa summary:hover{color:var(--accent)}
.qa .ans{padding:0 16px 14px 44px;color:var(--muted);font-size:.83rem;line-height:1.7}
.qa .ans b{color:var(--fg)}
.chk{list-style:none;margin:0;padding:0;font-size:.83rem;color:var(--muted)}
.chk li{display:flex;gap:9px;align-items:flex-start;padding:7px 0;border-top:1px solid var(--border);line-height:1.55}
.chk li:first-child{border-top:0}
.chk li .ic-xs{color:var(--accent);margin-top:4px}
@media(max-width:960px){
.cols-4,.cols-3,.step-flow{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:640px){
.cols-4,.cols-3,.cols-2,.step-flow{grid-template-columns:1fr}
.stats{grid-template-columns:repeat(2,minmax(0,1fr))}
.hero{padding:6px 0 24px}
footer{flex-direction:column}
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
"""


def _weight_rows(weights: list[tuple[str, str, int]], locale: str) -> str:
    idx = 1 if locale == "en" else 0
    return "".join(
        f'<div class="wrow"><span class="wl">{row[idx]}</span>'
        f'<span class="wbar"><i style="width:{row[2]}%"></i></span>'
        f'<span class="wv">{row[2]}%</span></div>'
        for row in weights
    )


def render(locale: str = "zh") -> str:
    """Build the certification page. ``locale`` is ``"zh"`` or ``"en"``.

    Returns HTML with ``__ICON_SPRITE__`` still in place: the sprite lives in
    ``app.py`` (it is shared with the other pages) and is substituted there,
    exactly like ``_OVERVIEW_HTML``.
    """
    if locale not in ("zh", "en"):
        raise ValueError(f"unsupported locale: {locale!r}")
    en = locale == "en"

    def p(zh: str, eng: str) -> str:
        return eng if en else zh

    lang = "en" if en else "zh"
    other = "/certification" if en else "/en/certification"
    badge = "切换到中文" if en else "EN"
    badge_title = "切换到中文" if en else "English version"
    badge_label = "切换到中文" if en else "Switch to English"

    out: list[str] = []
    add = out.append

    add(f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{p("FDE Scope · 认证中心", "FDE Scope · Certification")}</title>
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
    <span class="tag">{p("认证 · 渠道准入", "certification · channel admission")}</span>
  </div>
  <nav class="snav">
    <div class="grp">{p("FDE 学习者", "FDE learners")}</div>
    <a href="{"/en/" if en else "/"}">{p("功能总览", "Overview")}</a>
    <a href="{"/en/course" if en else "/course"}">{p("入门课程", "Intro course")}</a>
    <a href="{"/en/glossary" if en else "/glossary"}">{p("名词解释", "Glossary")}</a>
    <a href="{"/en/certification" if en else "/certification"}" class="active">{
        p("认证中心", "Certification")
    }</a>
    <div class="subnav">
      <a href="#landscape">{p("认证全景", "Landscape")}</a>
      <a href="#specs">{p("认证细则", "Exam specs")}</a>
      <a href="#aliyun">{p("阿里云认证", "Alibaba Cloud")}</a>
      <a href="#outline">{p("考点大纲", "Exam outline")}</a>
      <a href="#papers">{p("真题与样题", "Papers")}</a>
      <a href="#guide">{p("备考指南", "Study guide")}</a>
      <a href="#channel">{p("渠道准入", "Channel admission")}</a>
      <a href="#sources">{p("数据来源", "Sources")}</a>
    </div>
    <div class="grp">{p("FDE 工程师", "FDE engineers")}</div>
    <a href="{"/en/sop" if en else "/sop"}">{p("SOP 全文", "SOP full text")}</a>
    <a href="{"/catalog/en/index.html" if en else "/catalog/index.html"}">{
        p("技能手册库", "Skills handbook")
    }</a>
    <a href="{"/en/docs/readme" if en else "/docs/readme"}">{p("仓库文档", "Repo docs")}</a>
    <div class="grp">{p("FDE 工作台", "FDE workbench")}</div>
    <a href="{"/en/console" if en else "/console"}">{p("Engagement 控制台", "Engagement console")}</a>
    <div class="grp">{p("外部", "External")}</div>
    <a href="{"/GTM/en/index.html" if en else "/GTM/index.html"}">{p("GTM 官网", "GTM site")}</a>
  </nav>
  <div class="side-foot">
    <a class="lang" href="{other}" title="{badge_title}" aria-label="{badge_label}">{badge}</a>
    <button class="tbtn" onclick="toggleTheme()" title="{p("切换深浅主题", "Toggle theme")}" aria-label="{
        p("切换深浅主题", "Toggle theme")
    }">
      <svg class="ic when-dark"><use href="#i-sun"/></svg>
      <svg class="ic when-light"><use href="#i-moon"/></svg>
    </button>
  </div>
</aside>

<main class="main">
<div class="wrap">

<div class="hero">
  <div class="eyebrow">{p("Certification · Channel readiness", "Certification · Channel readiness")}</div>
  <h2>{p("FDE 认证与渠道准入", "FDE certification and channel admission")}</h2>
  <p>{
        p(
            "三家 AI 办公平台的认证细则、公开考点大纲、公开样题与备考路径。每个数字都标注来源等级：",
            "Exam specs, public outlines, published sample items and a study path for "
            "three AI-office platforms. Every figure carries its provenance: ",
        )
    }<span class="tier official">official</span> · <span class="tier noted">noted</span> · <span class="tier gap">gap</span>{
        p(
            "——查不到的就写查不到。",
            " — where nothing is published, the page says so.",
        )
    }</p>
  <div class="cta">
    <a class="btn" href="#specs">{p("看认证细则", "Read the exam specs")}</a>
    <a class="btn ghost" href="#papers"><svg class="ic"><use href="#i-flask"/></svg>{
        p("刷样题", "Try the sample items")
    }</a>
    <a class="btn ghost" href="#guide"><svg class="ic"><use href="#i-compass"/></svg>{
        p("备考路径", "Study path")
    }</a>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="num">3</div><div class="lab">{
        p("平台（腾讯 / 阿里 / 字节）", "platforms (Tencent / Alibaba / ByteDance)")
    }</div></div>
  <div class="stat"><div class="num">5</div><div class="lab">{
        p("认证与考试科目（腾讯 3 · 阿里云 2）", "certifications and exams (Tencent 3 · Alibaba Cloud 2)")
    }</div></div>
  <div class="stat"><div class="num">2</div><div class="lab">{
        p("年 · 证书有效期（主流）", "years · typical certificate validity")
    }</div></div>
  <div class="stat"><div class="num">{len(_SOURCES)}</div><div class="lab">{
        p("条来源，逐条分级", "sources, each graded")
    }</div></div>
</div>

<section id="landscape">
<div class="sec-head"><svg class="ic"><use href="#i-globe"/></svg><h2>{
        p("认证全景 · 三家平台", "Landscape · three platforms")
    }</h2><span class="n">01</span></div>
<p class="sec-note">{
        p(
            "判断一家平台的「FDE 认证」能不能当招聘与投标凭证，先看它有没有独立认证科目，还是只在大模型通用认证里覆盖。"
            "三家的成熟度差别很大，下面按公开可查的程度排序。",
            "To know whether a platform's FDE certification is usable as a hiring or bid credential, check whether "
            "it is a standalone exam or merely covered inside a general LLM certification. The three vendors differ "
            "sharply — ordered below by how much is publicly verifiable.",
        )
    }</p>
<div class="grid cols-3">
  <div class="tile">
    <svg class="ic"><use href="#i-check-badge"/></svg>
    <div class="name">{
        p("腾讯 WorkBuddy", "Tencent WorkBuddy")
    } <span class="tier official">official</span></div>
    <div class="desc">{
        p(
            "独立认证科目两条路径：<b>效率智能体 OPC 从业者</b>（线上理论）与<b>效率智能体应用师</b>（线下理论）；"
            "渠道准入还要过两门考试（售卖应知应会 + OPC 从业者，各 ≥ 3 人）。规格、价格、有效期都在官方页面可查，是最完整的一家。",
            "Two standalone tracks: <b>Efficiency Agent OPC Practitioner</b> (online theory) and "
            "<b>Efficiency Agent Practitioner</b> (offline theory). Channel admission adds two more exams "
            "(sales essentials + OPC Practitioner, ≥ 3 passers each). Specs, prices and validity are all "
            "on published pages — the most complete of the three.",
        )
    }</div>
    <span class="status s-ok">{p("细则公开 · 可备考", "specs published · studyable")}</span>
  </div>
  <div class="tile">
    <svg class="ic"><use href="#i-cloud"/></svg>
    <div class="name">{
        p("阿里云 · 千问办公", "Alibaba Cloud · QwenWork")
    } <span class="tier official">official</span></div>
    <div class="desc">{
        p(
            "千问办公<b>没有专属认证</b>：FDE 能力映射到通用大模型认证 <b>ACA</b> 与 <b>ACP</b>——题型与知识域权重公开，"
            "<b>及格线未公开</b>。伙伴侧另有 ASE-X / APE-X 技术认证体系，覆盖售前架构与实施运维，专家数量计入伙伴级别晋升，"
            "是阿里系里最接近 FDE 的一张凭证。",
            "QwenWork has <b>no dedicated certification</b>: FDE capability maps onto the general LLM certs — "
            "<b>ACA</b> and <b>ACP</b> (question types and domain weights published, <b>pass mark not</b>). The "
            "partner track adds the ASE-X / APE-X programme covering pre-sales architecture and delivery; "
            "certified headcount feeds partner-tier promotion and it is the closest thing Alibaba has to an FDE "
            "credential.",
        )
    }</div>
    <span class="status s-partial">{
        p("借用通用认证 · 及格线未公开", "general certs · pass mark unpublished")
    }</span>
  </div>
  <div class="tile">
    <svg class="ic"><use href="#i-ban"/></svg>
    <div class="name">{
        p("字节 TRAE（企业版）", "ByteDance TRAE (enterprise)")
    } <span class="tier gap">gap</span></div>
    <div class="desc">{
        p(
            "火山引擎品牌下确有一个技能认证考试平台（第三方运营），但目录只有数智增长营销与 A/B 测试两科，"
            "<b>未检索到</b> TRAE 或大模型方向的科目与细则。伙伴分级表（六档）是公开的，认证科目本身仍是缺口——"
            "需要 TRAE 认证路径时，向渠道经理索取内部准入文档。",
            "A Volcengine-labelled skills certification platform exists (third-party operated), but its "
            "catalogue holds only two non-LLM subjects; <b>no TRAE or LLM</b> subject or spec sheet is indexed. "
            "The six partner tiers are public; the certification subject itself remains a gap — ask the channel "
            "manager for the internal admission document.",
        )
    }</div>
    <span class="status s-stub">{p("公开数据缺口", "public-data gap")}</span>
  </div>
</div>
</section>

<section id="specs">
<div class="sec-head"><svg class="ic"><use href="#i-flask"/></svg><h2>{
        p("认证细则 · 考试规格", "Exam specs")
    }</h2><span class="n">02</span></div>
<p class="sec-note">{
        p(
            "腾讯两条认证路径的题型、时长、及格线、价格与有效期都来自官方页面（应用师 → 考试细则文档，OPC 从业者 → 认证详情页）。"
            "渠道准入考的是另外两门，见本节末块。",
            "Question types, duration, pass mark, price and validity for both Tencent tracks come from published "
            "pages (Practitioner → the spec document, OPC Practitioner → the cert detail page). Channel admission "
            "is examined separately — see the last tile of this section.",
        )
    }</p>
<div class="grid cols-2">
  <div class="tile">
    <div class="name">{
        p("腾讯 WorkBuddy 效率智能体应用师", "Tencent WorkBuddy Efficiency Agent Practitioner")
    } <span class="tier official">official</span></div>
    <div class="kpi-row"><span>{p("题型与题量", "Question types")}</span><span class="v">{
        p("单选 40 + 多选 20 = 60 题", "40 single + 20 multi = 60")
    }</span></div>
    <div class="kpi-row"><span>{p("考试时长", "Duration")}</span><span class="v">{
        p("120 分钟", "120 min")
    }</span></div>
    <div class="kpi-row"><span>{p("满分 / 及格", "Total / pass")}</span><span class="v">{
        p("100 分 / 70 分", "100 / 70")
    }</span></div>
    <div class="kpi-row"><span>{p("多选题计分", "Multi-select scoring")}</span><span class="v">{
        p("错选、漏选均不得分", "no credit for wrong or missed picks")
    }</span></div>
    <div class="kpi-row"><span>{p("考试形式", "Format")}</span><span class="v">{
        p("线下理论", "offline, theory")
    }</span></div>
  </div>
  <div class="tile">
    <div class="name">{
        p("腾讯 WorkBuddy 效率智能体 OPC 从业者", "Tencent WorkBuddy Efficiency Agent OPC Practitioner")
    } <span class="tier official">official</span></div>
    <div class="kpi-row"><span>{p("考试形式", "Format")}</span><span class="v">{
        p("线上理论", "online, theory")
    }</span></div>
    <div class="kpi-row"><span>{p("满分 / 通过", "Total / pass")}</span><span class="v">{
        p("100 分 / 70 分", "100 / 70")
    }</span></div>
    <div class="kpi-row"><span>{p("考试时长", "Duration")}</span><span class="v">{
        p("90 分钟", "90 min")
    }</span></div>
    <div class="kpi-row"><span>{p("考试机会", "Attempts")}</span><span class="v">{
        p("3 次，用尽需重新购买", "3, then repurchase")
    }</span></div>
    <div class="kpi-row"><span>{p("考试费用", "Fee")}</span><span class="v">{
        p("¥330（原价 ¥600）", "¥330 (list ¥600)")
    }</span></div>
    <div class="kpi-row"><span>{p("报考要求", "Eligibility")}</span><span class="v">{
        p("个人实名主账号 + 人脸核身（不支持子账号）", "verified main account + face check (no sub-accounts)")
    }</span></div>
    <div class="kpi-row"><span>{p("证书有效期", "Validity")}</span><span class="v">{
        p("2 年，唯一编号可在线核验", "2 years, unique number verifiable online")
    }</span></div>
    <div class="kpi-row"><span>{p("课程规模", "Course size")}</span><span class="v">{
        p("11 模块 31 章节 · 约 6 小时", "11 modules, 31 chapters · ~6 h")
    }</span></div>
    <div class="sec-note" style="margin:10px 0 0">{
        p(
            "以上均来自腾讯云官方认证详情页与课程页；报考前以购买页说明为准。",
            "All rows come from Tencent Cloud's own cert detail and course pages; trust the purchase page at "
            "booking time.",
        )
    }</div>
  </div>
  <div class="tile">
    <div class="name">{
        p("应用师 · 六大模块权重", "Practitioner · six module weights")
    } <span class="tier official">official</span></div>
    {_weight_rows(_WORKBUDDY_APPLICATION_WEIGHTS, locale)}
  </div>
  <div class="tile">
    <div class="name">{
        p(
            "渠道准入（WorkBuddy 专属）· 两门考试 + 保证金",
            "Channel admission (WorkBuddy) · two exams + deposit",
        )
    } <span class="tier official">official</span></div>
    <div class="kpi-row"><span>{p("考试①", "Exam 1")}</span><span class="v">{
        p("产品售卖应知应会 ≥ 3 人", "Product Sales Essentials ≥ 3 passers")
    }</span></div>
    <div class="kpi-row"><span>{p("考试②", "Exam 2")}</span><span class="v">{
        p("效率智能体 OPC 从业者 ≥ 3 人", "Efficiency Agent OPC Practitioner ≥ 3 passers")
    }</span></div>
    <div class="kpi-row"><span>{p("保证金", "Deposits")}</span><span class="v">{
        p("云代理 1 万 + WB 专属 5 万 = 6 万元", "cloud agent ¥10k + WorkBuddy ¥50k = ¥60k")
    }</span></div>
    <div class="kpi-row"><span>{p("附加文件", "Extra document")}</span><span class="v">{
        p("签署《单方保密承诺书》", "sign a unilateral confidentiality undertaking")
    }</span></div>
    <div class="sec-note" style="margin:10px 0 0">{
        p(
            "两门考试都是人数门槛而非技术认证，是最容易被低估的签约前置条件——招人节奏要提前排。",
            "Both exams are headcount gates rather than technical credentials, and they are the most "
            "commonly underestimated precondition — budget the hiring lead time.",
        )
    }</div>
  </div>
</div>
</section>

<section id="aliyun">
<div class="sec-head"><svg class="ic"><use href="#i-cloud"/></svg><h2>{
        p("阿里云 · 大模型认证", "Alibaba Cloud · LLM certifications")
    }</h2><span class="n">03</span></div>
<p class="sec-note">{
        p(
            "千问办公侧没有专属认证，FDE 的技术凭证落在阿里云通用大模型认证上。两个等级按「会不会用」与「会不会建」划分。",
            "QwenWork has no dedicated certification, so the FDE credential lands on Alibaba Cloud's general LLM "
            "certifications. The two tiers split along use-it versus build-it.",
        )
    }</p>
<div class="grid cols-2">
  <div class="tile">
    <div class="name">{
        p("大模型工程师 ACA（aca13）", "LLM Engineer ACA (aca13)")
    } <span class="tier official">official</span></div>
    <div class="kpi-row"><span>{p("考试费用", "Fee")}</span><span class="v">{
        p("¥600（含课程 + 考试）", "¥600 incl. course + exam")
    }</span></div>
    <div class="kpi-row"><span>{p("证书有效期", "Validity")}</span><span class="v">{
        p("2 年", "2 years")
    }</span></div>
    <div class="kpi-row"><span>{p("考试机会", "Attempts")}</span><span class="v">{
        p("2 次（失败需间隔 24 小时）", "2 (24 h wait after a fail)")
    }</span></div>
    <div class="desc" style="margin-top:10px">{
        p(
            "定位：会用大模型能力完成业务任务。适合作为 FDE 团队的统一入门门槛。",
            "Positioning: use LLM capability to get work done — a sensible baseline for a whole FDE team.",
        )
    }</div>
  </div>
  <div class="tile">
    <div class="name">{
        p("大模型高级工程师 ACP（acp26）", "Senior LLM Engineer ACP (acp26)")
    } <span class="tier official">official</span></div>
    <div class="kpi-row"><span>{p("考试费用", "Fee")}</span><span class="v">{p("¥1200", "¥1200")}</span></div>
    <div class="kpi-row"><span>{p("证书有效期", "Validity")}</span><span class="v">{
        p("2 年", "2 years")
    }</span></div>
    <div class="kpi-row"><span>{p("题型与题量", "Question types")}</span><span class="v">{
        p("单选 50×1 + 多选 25×2 = 75 题", "50 single ×1 + 25 multi ×2 = 75")
    }</span></div>
    <div class="kpi-row"><span>{p("满分", "Total")}</span><span class="v">{
        p("100 分（官方分值分配）", "100 (per the official allocation)")
    }</span></div>
    <div class="kpi-row"><span>{p("及格线", "Pass mark")}</span><span class="v">{
        p("官方未公布", "not published by the vendor")
    } <span class="tier gap">gap</span></span></div>
    <div class="kpi-row"><span>{p("考试机会", "Attempts")}</span><span class="v">{
        p("1 次（订单 1 年内有效）", "1 (order valid 1 year)")
    }</span></div>
    <div class="kpi-row"><span>{p("大纲更新", "Outline revision")}</span><span class="v">{
        p("2025-10-17 起", "from 2025-10-17")
    }</span></div>
    <div class="sec-note" style="margin:10px 0 0">{
        p(
            "100 分由官方公布的分值分配算出；<b>及格线本页检索不到官方出处</b>，第三方笔记里的数字无官方依据，因此留空。",
            "The 100 is arithmetic from the published mark allocation. <b>No official page carries a pass mark</b>, "
            "and third-party numbers have no official basis — so the row stays empty.",
        )
    }</div>
  </div>
  <div class="tile">
    <div class="name">{
        p("ACP · 六大知识域权重", "ACP · six knowledge domains")
    } <span class="tier official">official</span></div>
    {_weight_rows(_ALIYUN_ACP_WEIGHTS, locale)}
  </div>
  <div class="tile">
    <div class="name">{
        p("千问办公 · 政企培训", "QwenWork · public-sector training")
    } <span class="tier noted">noted</span></div>
    <div class="desc">{
        p(
            "面向央国企非技术岗的零基础培训路径，内容覆盖提示词、Skill、工作流到「AI 团队」搭建。"
            "它<b>不是认证考试</b>，培训结业不等于持证——投标时不能当资质用。",
            "A zero-prerequisite path for non-technical staff in state-owned enterprises, covering prompts, Skills, "
            "workflows and standing up an AI team. It is <b>training, not an exam</b> — completion is not a "
            "certificate and cannot serve as a bid qualification.",
        )
    }</div>
    <span class="status s-partial">{p("培训 ≠ 认证", "training ≠ certification")}</span>
  </div>
  <div class="tile">
    <div class="name">{
        p("千问办公 · 产品价格锚点", "QwenWork · list prices")
    } <span class="tier official">official</span></div>
    <div class="kpi-row"><span>{p("企业标准版", "Enterprise Standard")}</span><span class="v">{
        p("¥198 / 席 / 月", "¥198/seat/month")
    }</span></div>
    <div class="kpi-row"><span>{p("标准版基础积分", "Standard credits")}</span><span class="v">{
        p("2,000 积分/人/月", "2,000 credits/seat/month")
    }</span></div>
    <div class="kpi-row"><span>{p("企业旗舰版", "Enterprise Flagship")}</span><span class="v">{
        p("¥298 / 席 / 月（100 席起购）", "¥298/seat/month (from 100 seats)")
    }</span></div>
    <div class="kpi-row"><span>{p("积分包", "Credit packs")}</span><span class="v">{
        p("¥100 起 · 2,000 积分起 · 12 个月有效", "from ¥100 · from 2,000 credits · 12 months")
    }</span></div>
    <div class="kpi-row"><span>{p("私有化部署", "Private deployment")}</span><span class="v">{
        p("询价", "quote only")
    }</span></div>
    <div class="sec-note" style="margin:10px 0 0">{
        p(
            "官方产品页现价，不含渠道折扣与共拓激励。第三方材料另有一套版本名与价格（团队旗舰版 / "
            "企业专享版 316 元），与官方产品页不符，<b>本页不采用</b>。",
            "Vendor list price, excluding channel discounts and co-sell incentives. Third-party material "
            "circulates a different edition naming and price (Team Flagship / Enterprise Exclusive at "
            "¥316) that does not match the vendor's page; <b>this page does not use those figures</b>.",
        )
    }</div>
  </div>
  <div class="tile">
    <div class="name">{
        p("阿里云伙伴技术认证（ASE-X / APE-X）", "Alibaba Cloud partner certification (ASE-X / APE-X)")
    } <span class="tier official">official</span></div>
    <div class="desc">{
        p(
            "伙伴专属的认证体系，面向伙伴架构师与售前人员，覆盖业务运营、产品与技术、售前架构、实施运维；"
            "<b>持证专家数量计入伙伴级别晋升</b>，是阿里系里最接近 FDE 的技术凭证。"
            "注意：官方两处页面分别写作 ASE-X 与 APE-X，口径未统一，报名前以伙伴经理说法为准。",
            "A partner-only certification programme for solution architects and pre-sales, covering business "
            "operations, product and technology, solution architecture, and delivery/operations. <b>Certified "
            "headcount feeds partner-tier promotion</b> — the closest thing to an FDE credential on the Alibaba "
            "side. Note: the vendor's own pages spell the programme both ASE-X and APE-X; confirm with the "
            "partner manager before booking.",
        )
    }</div>
    <span class="status s-partial">{p("伙伴专属 · 计入级别晋升", "partner-only · counts toward tier")}</span>
  </div>
</div>
</section>

<section id="outline">
<div class="sec-head"><svg class="ic"><use href="#i-book"/></svg><h2>{
        p("考点大纲", "Exam outline")
    }</h2><span class="n">04</span></div>
<p class="sec-note">{
        p(
            "模块名与权重是官方公布数据；考点概念是按公开大纲整理的索引，用于组织复习，不是官方章节编号的逐条映射。",
            "Module names and weights are published figures. The concept list below is a curated index drawn from the "
            "public outline — it organises revision, it is not a line-by-line mapping of official chapter numbers.",
        )
    }</p>
<div class="grid cols-3">
  <div class="tile">
    <div class="name">{
        p("应用师 · 考点概念索引", "Practitioner · concept index")
    } <span class="tier noted">noted</span></div>
    <ul class="chk">
      {
        "".join(
            f'<li><svg class="ic-xs"><use href="#i-check"/></svg><span>{c[1] if en else c[0]}</span></li>'
            for c in _OUTLINE_CONCEPTS
        )
    }
    </ul>
  </div>
  <div class="tile">
    <div class="name">{p("备考要点 · 三条经验", "Three rules of thumb")}</div>
    <div class="desc" style="margin-bottom:12px">{
        p(
            "<b>按判断题准备，不要按功能清单准备。</b>大纲里最容易失分的是「会 / 不会」的边界——哪些操作留在本地、"
            "哪些走云端、哪些必须人工确认。",
            "<b>Study boundaries, not feature lists.</b> The points people lose are on can / cannot: what stays "
            "local, what goes to the cloud, what needs human confirmation.",
        )
    }</div>
    <div class="desc" style="margin-bottom:12px">{
        p(
            "<b>职场实战占 20%，题目以场景为载体。</b>复习时按「场景 → 该调用哪个能力」组织记忆，而不是背参数。",
            "<b>Workplace practice is 20% and the questions are scenario-shaped.</b> Memorise scenario → which "
            "capability, not parameter tables.",
        )
    }</div>
    <div class="desc">{
        p(
            "<b>考前回到官方指南核对。</b>权重与大纲会滚动更新，本页是索引不是考纲原件。",
            "<b>Re-check the official guide before sitting.</b> Weights and outlines roll; this page is an index, "
            "not the source of truth.",
        )
    }</div>
  </div>
  <div class="tile">
    <div class="name">{
        p("ACP · 高分域的复习次序", "ACP · suggested order")
    } <span class="tier noted">noted</span></div>
    <div class="desc">{
        p(
            "RAG 20% + 应用开发 17% 合计 37%，是分值重心；微调、多 Agent 与多模态、生产实践各 16% 平分；提示词工程 15% 垫底但最容易拿满。"
            "建议次序：提示词工程打底 → RAG 与检索 → 应用开发 → 微调与多 Agent → 生产实践。",
            "RAG (20%) plus application development (17%) is 37% of the paper; fine-tuning, multi-agent/multimodal "
            "and production practice split 16% each; prompt engineering is the smallest at 15% and the easiest to "
            "sweep. Suggested order: prompts → RAG and retrieval → application development → fine-tuning and "
            "multi-agent → production practice.",
        )
    }</div>
  </div>
</div>
</section>

<section id="papers">
<div class="sec-head"><svg class="ic"><use href="#i-docs"/></svg><h2>{
        p("真题与样题", "Papers and sample items")
    }</h2><span class="n">05</span></div>
<p class="sec-note">{
        p(
            "考卷不公开，官方只发布样题。下面一道是官方公开样题；其余是为练习自编的原创题，"
            "<b>明确标注为非官方真题</b>，用于检验是否真的理解考点，不能当题库背。",
            "The live papers are not published; vendors release sample items only. The first item below is an official "
            "sample. The rest are original practice questions written for this page and <b>explicitly labelled as not "
            "real exam items</b>. Use them to check understanding, not to memorise.",
        )
    }</p>
<div class="grid cols-2">
  <div>
    <div class="tile" style="margin-bottom:10px">
      <div class="name">{
        p("官方公开样题", "Official published sample")
    } <span class="tier official">official</span></div>
      <div class="desc">{
        p(
            "题面：WorkBuddy 与聊天式 AI 的核心区别是什么？<br>"
            "官方答案要点：WorkBuddy 能直接操作本地文件、执行多步任务，而聊天式 AI 停留在对话与建议。",
            "Prompt: what is the core difference between WorkBuddy and chat-style AI?<br>"
            "Answer as published: WorkBuddy can act on local files and run multi-step tasks, whereas chat AI stays "
            "at conversation and suggestion.",
        )
    }</div>
      <span class="status s-ok">{p("来自官方考试细则文档", "from the official spec document")}</span>
    </div>
    <div class="tile">
      <div class="name">{p("怎么用这一页", "How to use this page")}</div>
      <div class="desc">{
        p(
            "先按 04 的考点概念逐条自述一遍，能讲清边界再刷题；刷题时先选答案再看解析。"
            "全部答对不等于覆盖了 60 题的知识面——它只说明你没踩到最常见的几个坑。",
            "Walk the concept list in 04 first and explain each boundary out loud before practising. Answer "
            "first, then open the explanation. Getting these right does not mean you covered a 60-question "
            "paper — only that you avoided the usual traps.",
        )
    }</div>
    </div>
  </div>
  <div class="grid" style="gap:10px">
    {_practice_html(locale)}
    <div class="tile">
      <div class="name">{p("免责声明", "Disclaimer")} <span class="tier noted">noted</span></div>
      <div class="desc">{
        p(
            "本区块除第一道样题外均为自编原创练习题，<b>不是官方真题，也不是官方答案</b>，不构成任何考试承诺。"
            "官方题库与样题请以各平台考试指南为准。",
            "Apart from the first sample, every item here is original practice material written for this page. "
            "<b>It is not a real exam question and not an official answer</b>, and it promises nothing about the "
            "real paper. For official banks and samples, use each vendor's own exam guide.",
        )
    }</div>
    </div>
  </div>
</div>
</section>

<section id="guide">
<div class="sec-head"><svg class="ic"><use href="#i-compass"/></svg><h2>{
        p("备考指南 · 四周路径", "Study guide · a four-week path")
    }</h2><span class="n">06</span></div>
<p class="sec-note">{
        p(
            "以通过「腾讯 WorkBuddy 效率智能体应用师」为主线排的四周计划；换到 ACA / ACP 时把第二、三周的模块换成对应知识域即可。",
            "A four-week plan laid out for the Tencent WorkBuddy Practitioner exam. For ACA or ACP, swap the "
            "week-two and week-three modules for the matching knowledge domains.",
        )
    }</p>
<div class="step-flow">
  <div class="zone">
    <div class="ztag">Week 1</div><div class="zname">{p("报名与摸底", "Sign up and baseline")}</div>
    <ol>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("核对官方最新考试指南与权重", "Confirm the current official guide and weights")
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "确认形式与报名：应用师线下理论；OPC 线上，实名主账号 ¥330",
            "Confirm format and booking: Practitioner is offline; OPC is online, verified main account, ¥330",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("通读 11 模块 31 章节课程，约 6 小时", "Read the 11-module / 31-chapter course, ~6 h")
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("做 05 的样题，记录错因", "Do the section-05 items, log why each miss happened")
    }</span></li>
    </ol>
  </div>
  <div class="zone">
    <div class="ztag">Week 2</div><div class="zname">{p("吃下分值重心", "Take the heavy modules")}</div>
    <ol>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("高效对话 20%：提示词四要素", "Dialogue 20%: the four prompt elements")
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("职场实战 20%：场景到能力的映射", "Practice 20%: scenario → capability")
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("用真实办公任务各跑一遍", "Run each one on a real work task")
    }</span></li>
    </ol>
  </div>
  <div class="zone">
    <div class="ztag">Week 3</div><div class="zname">{p("补边界与治理", "Boundaries and governance")}</div>
    <ol>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("安全合规 18%：Ask/Plan/Craft 分级", "Security 18%: Ask / Plan / Craft tiers")
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("进阶功能 18%：记忆与三层架构", "Advanced 18%: memory and the three layers")
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("企业构建 12% + 初识 12% 收口", "Enterprise 12% + foundations 12% to close")
    }</span></li>
    </ol>
  </div>
  <div class="zone">
    <div class="ztag">Week 4</div><div class="zname">{p("模拟与报名", "Mock and book")}</div>
    <ol>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("按 120 分钟限时模拟", "Mock under the 120-minute clock")
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p("多选题按全对标准复盘", "Review multi-selects on an all-or-nothing basis")
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "渠道侧：两门考试各凑齐 ≥ 3 人通过",
            "Channel side: line up ≥ 3 passers on each of the two exams",
        )
    }</span></li>
    </ol>
  </div>
</div>
</section>

<section id="channel">
<div class="sec-head"><svg class="ic"><use href="#i-wrench"/></svg><h2>{
        p("渠道准入 · 尽调清单", "Channel admission · due diligence")
    }</h2><span class="n">07</span></div>
<p class="sec-note">{
        p(
            "渠道政策按平台、按季度滚动。左栏是公开页面能逐条核对到的硬性项（2026-09-30 逐条复核），"
            "中栏是仍需落实到书面答复的维度，右栏是本页确认不到、因此没有写入的内容。",
            "Channel policy rolls per platform and per quarter. The left tile lists the hard gates that public "
            "pages do carry (each re-checked 2026-09-30); the middle tile is the checklist that must come back in "
            "writing; the right tile is what this page could not confirm and therefore does not state.",
        )
    }</p>
<div class="grid cols-3">
  <div class="tile">
    <div class="name">{p("已公开可核对的硬性项", "Hard gates that are publicly checkable")}</div>
    <ul class="chk">
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "腾讯 · 代理合作伙伴：注册资金 ≥ 100 万、成立 ≥ 1 年、专职销售 ≥ 3 人",
            "Tencent · agent partner: ≥ ¥1M registered capital, ≥ 1 year in business, ≥ 3 dedicated sales staff",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "腾讯 · WorkBuddy 专属：两门渠道考试（售卖应知应会 + OPC 从业者）各 ≥ 3 人通过",
            "Tencent · WorkBuddy-specific: ≥ 3 passers on each of the two channel exams (sales essentials + OPC)",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "腾讯 · 保证金：云代理 1 万 + WorkBuddy 专属 5 万 = 6 万元，另签《单方保密承诺书》",
            "Tencent · deposits: ¥10k cloud agent + ¥50k WorkBuddy = ¥60k, plus a confidentiality undertaking",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "腾讯 · OPC 从业者：实名主账号 + 人脸核身，¥330，3 次考试机会，证书 2 年",
            "Tencent · OPC Practitioner: verified main account + face check, ¥330, 3 attempts, 2-year certificate",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "阿里云 · 代理伙伴：注册资本 ≥ 100 万、成立 ≥ 1 年、在职员工 ≥ 5 人、信用保证金 1 万元（签约后 30 天内缴纳）",
            "Alibaba Cloud · agent partner: ≥ ¥1M registered capital, ≥ 1 year in business, ≥ 5 employees, "
            "¥10k deposit (paid within 30 days of signing)",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "阿里云 · ACA ¥600（2 次考试机会）/ ACP ¥1200（1 次），均 2 年有效期",
            "Alibaba Cloud · ACA ¥600 (2 attempts) / ACP ¥1200 (1 attempt), both valid 2 years",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "阿里云 · 技能认证证书须在财年结算前（每年 3 月 31 日）完成绑定，否则不计入伙伴等级考核；"
            "持证人须在收到邀请后 7 个工作日内于阿里云大学确认，绑定次日 APS 等级信息自动更新",
            "Alibaba Cloud · skill certificates must be bound before fiscal-year settlement (31 March each "
            "year) or they do not count toward partner-tier assessment; the holder must confirm in Alibaba "
            "Cloud University within 7 working days, and APS tier data refreshes the next day",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-check"/></svg><span>{
        p(
            "火山引擎 · 代理商分级：六档（认证级 → 精英级），业绩 100 万 → 2000 万+，认证人数 1/2/3/5/10；"
            "准入注册资金 > 100 万、注册 > 1 年、无重大违法或黑名单记录",
            "Volcengine · agent tiers: six (Certified → Elite), revenue ¥1M → ¥20M+, certified headcount "
            "1/2/3/5/10; admission needs > ¥1M registered capital, > 1 year registered, no major violations",
        )
    }</span></li>
    </ul>
  </div>
  <div class="tile">
    <div class="name">{
        p("签约前逐项索取书面答复的维度", "Dimensions to get back in writing before signing")
    }</div>
    <ul class="chk">
      {
        "".join(
            f'<li><svg class="ic-xs"><use href="#i-wrench"/></svg><span>{d[1] if en else d[0]}</span></li>'
            for d in _DUE_DILIGENCE
        )
    }
    </ul>
  </div>
  <div class="tile">
    <div class="name">{p("数据缺口清单", "Known data gaps")} <span class="tier gap">gap</span></div>
    <div class="desc" style="margin-bottom:10px">{
        p(
            "本页无法从公开渠道确认、因此没有写入的内容：",
            "What this page could not confirm from public sources, and therefore does not state:",
        )
    }</div>
    <ul class="chk">
      <li><svg class="ic-xs"><use href="#i-alert"/></svg><span>{
        p(
            "字节 TRAE / 火山引擎的大模型方向：认证科目、题型与细则（品牌下的第三方认证平台只有两门非大模型科目）",
            "ByteDance TRAE / Volcengine LLM track: subjects, question types and specs (the third-party platform "
            "under the brand lists only two non-LLM subjects)",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-alert"/></svg><span>{
        p(
            "火山引擎的保证金 / 履约金具体数额（公开分级表未列）",
            "Volcengine's deposit / performance bond amount (not in the public tier table)",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-alert"/></svg><span>{
        p(
            "阿里云 ACA / ACP 的官方及格线（分值分配公开，及格线未见官方页面）",
            "Alibaba Cloud's official ACA / ACP pass mark (the allocation is public, the pass mark is not)",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-alert"/></svg><span>{
        p(
            "千问办公专属 FDE 认证是否存在（目前只见通用认证、伙伴认证与政企培训）",
            "Whether a QwenWork-specific FDE certification exists (only general certs, partner certs and "
            "training are visible)",
        )
    }</span></li>
      <li><svg class="ic-xs"><use href="#i-alert"/></svg><span>{
        p(
            "三家返点 / 市场基金的具体比例（未见官方公开页，仅第三方渠道口径）",
            "Rebate / market-fund percentages for all three (no official page; third-party channel figures only)",
        )
    }</span></li>
    </ul>
  </div>
</div>
</section>

<section id="sources">
<div class="sec-head"><svg class="ic"><use href="#i-doc"/></svg><h2>{
        p("数据来源与时效", "Sources and currency")
    }</h2><span class="n">08</span></div>
<p class="sec-note">{
        p(
            "政策与价格滚动更新。签约或报考前请以官方最新公告为准——本页是索引与复习工具，不是官方文件，也不构成商业合作建议。",
            "Policy and prices roll. Before signing or booking an exam, go to the vendor's current announcement: "
            "this page is an index and a revision aid, not an official document, and not commercial advice.",
        )
    }</p>
<div class="tblwrap">
<table class="tbl">
  <thead><tr><th>{p("来源", "Source")}</th><th>{p("等级", "Tier")}</th><th>{
        p("链接", "Link")
    }</th></tr></thead>
  <tbody>
    {"".join(_source_row(s, locale) for s in _SOURCES)}
  </tbody>
</table>
</div>
</section>

<footer>
  <span>{
        p(
            "FDE Scope · 认证中心 · 公开信息整理，非官方文件",
            "FDE Scope · Certification centre · compiled from public sources, not an official document",
        )
    }</span>
  <span>{
        p(
            "报考与签约前请核对官方最新公告 · 更新于 2026-09-30",
            "Verify against the vendor's current announcement · compiled 2026-09-30",
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
""")
    return "".join(out)


# ---------------------------------------------------------------------------
# Practice items. Original, written for this page — see the disclaimer in the
# copy. Each entry is (question_zh, question_en, answer_zh, answer_en).
# ---------------------------------------------------------------------------
_PRACTICE: list[tuple[str, str, str, str]] = [
    (
        "多选题：下面哪些操作是「智能体」与「聊天式 AI」的分界线？"
        "A. 读取本地 Excel 并改写 B. 把结论整理成一封邮件草稿 C. 在对话里解释一个概念 D. 连续执行多步任务",
        "Multi-select: which operations mark the line between an agent and chat AI? "
        "A. read and rewrite a local Excel file B. draft an email from a conclusion "
        "C. explain a concept in conversation D. execute a multi-step task chain",
        "A、D。判据是「是否能触达本地资源并自主推进多步任务」，"
        "而不是「输出是否像人」。B、C 聊天式 AI 同样能做，所以不构成分界线。",
        "A and D. The test is whether it can reach local resources and drive a multi-step task itself — not "
        "whether the output reads well. Chat AI can already do B and C, so they do not separate the two.",
    ),
    (
        "多选题：关于多选题计分，以下理解正确的是？A. 漏选可得部分分 B. 错选不得分 "
        "C. 漏选不得分 D. 多选题和单选题一样只占 1 分",
        "Multi-select: which statements about multi-select scoring are correct? A. missed picks earn partial "
        "credit B. wrong picks earn nothing C. missed picks earn nothing D. a multi-select is worth the same "
        "as a single-select",
        "B、C。应用师考试规则是「错选、漏选均不得分」——多选题是全对才给分。"
        "D 属于没有依据的推断：官方公布了题型、题量与及格线，但没有公布每题分值。",
        "B and C. The rules state no credit for wrong or missed picks — a multi-select scores only when "
        "complete. D is an unfounded inference: the vendor published question types, counts and the pass "
        "mark, but not per-question marks.",
    ),
    (
        "判断：安全合规模块要求记住所有数据必须留在本地处理。这个说法对吗？",
        "True or false: the security module requires that all data stay local.",
        "不对。大纲考的是<b>边界判断</b>——不同处理路径有不同的合规前提，"
        "而不是「一律本地」。把「有时必须本地 / 需人工确认」记成「一律本地」，是这一模块最常见的失分方式。",
        "False. The outline tests boundary judgement — different processing paths carry different compliance "
        'preconditions — not a blanket rule. Flattening it to "always local" is the usual way people drop '
        "marks here.",
    ),
    (
        "单选：企业构建模块占 12%，与「初识」并列最低。在复习时间有限时，最合理的策略是？"
        "A. 直接放弃，靠常识答题 B. 只记结论性条目，把时间投给 20% 的两个模块 "
        "C. 优先深挖，因为最难 D. 按分值等比例分配时间",
        "Single-select: the enterprise module is 12%, tied for the smallest. With limited revision time, the "
        "sensible strategy is? A. skip it and rely on common sense B. memorise the conclusion-level items "
        "and spend the time on the two 20% modules C. go deepest on it because it is hardest D. split time "
        "proportionally to the weights",
        "B。低权重模块不意味着可以放过——多选题常常在这里设点，而全对才给分；"
        "但它考的是结论性条目（账号、权限、审计），深挖性价比低。A 的风险在于多选题会直接归零。",
        "B. A low weight does not license skipping: multi-selects are often set here and they only score when "
        "complete. But what it tests is conclusion-level (accounts, permissions, audit), so depth pays badly. "
        "A is risky because a multi-select sinks to zero.",
    ),
    (
        "多选：ACP 大纲里合计占 37% 的两个知识域是？A. 提示词工程 B. RAG C. 微调 D. 大模型应用开发",
        "Multi-select: which two ACP domains total 37%? A. prompt engineering B. RAG C. fine-tuning "
        "D. LLM application development",
        "B、D。RAG 20% + 大模型应用开发 17% = 37%。提示词工程只有 15%，是最低权重但最容易拿满的一块——"
        "先把它扫掉，再攻 RAG。",
        "B and D. RAG 20% + application development 17% = 37%. Prompt engineering is the smallest at 15% and "
        "the easiest to sweep — clear it first, then go after RAG.",
    ),
]


def _practice_html(locale: str) -> str:
    """The practice items as native ``<details>`` disclosures — no JS needed."""
    idx = 1 if locale == "en" else 0
    label = ("官方样题之外的原创练习", "original practice, not official items")
    return "".join(
        f'<details class="qa"><summary>{item[idx]} '
        f'<span class="tier noted">{label[1] if locale == "en" else label[0]}</span></summary>'
        f'<div class="ans"><b>{"Answer" if locale == "en" else "解析"}：</b>{item[idx + 2]}</div></details>'
        for item in _PRACTICE
    )


def _source_row(source: tuple[str, str, str, str], locale: str) -> str:
    label = source[1] if locale == "en" else source[0]
    tier_zh, tier_en = _TIER_LABEL[source[3]]
    tier = tier_en if locale == "en" else tier_zh
    # the URL stays visible as plain text — provenance without an off-site
    # jump (the reader copies it if they need the official page)
    link = (
        f'<span class="cite">{source[2]}</span>'
        if source[2]
        else ("—" if locale == "en" else "—（无公开链接）")
    )
    return f'<tr><td>{label}</td><td><span class="tier {tier_en}">{tier}</span></td><td>{link}</td></tr>'

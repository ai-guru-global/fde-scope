"""Bilingual support for the web console (fde_scope.web.app).

The Chinese pages are the source of truth: ``app.py`` holds the zh HTML
templates. This module provides:

- ``I18N_PAIRS``: exact zh -> en substring replacements, applied longest-key
  first by :func:`to_en` at import time to produce ``_OVERVIEW_HTML_EN`` /
  ``_DASHBOARD_HTML_EN``. Keys are UI literals (HTML/JS template lines), so a
  key only matches where that literal appears; API-returned domain data
  (phase names, gate blockers ...) stays Chinese on both locales.
- ``GLOSSARY_EN``: English tips for the same term list as ``app._GLOSSARY``
  (zh tips live there; terms/keys are shared so glossify matches identically).

To keep the locales in sync: any new Chinese UI literal added to app.py needs
a pair here, and any new ``_GLOSSARY`` entry needs a ``GLOSSARY_EN`` entry.
``tests/test_web.py`` guards the /en routes.
"""

GLOSSARY_EN: list[tuple[str, str]] = [
    (
        "Gemba walk",
        "From Japanese genba (the actual place): walk the shop floor where value is "
        "created, observe real work and talk to operators instead of judging from "
        "reports. A core lean/Toyota practice.",
    ),
    (
        "Gemba",
        "Site walk: engineers embed on the shop floor to observe real processes, "
        "equipment and pain points (maps to the site_survey phase).",
    ),
    (
        "FDE",
        "Forward Deployed Engineer: an engineer who embeds at the customer site with "
        "the product to deliver solutions fast.",
    ),
    ("Engagements", "Engagement list: the entry point for all field projects."),
    (
        "Engagement",
        "One full on-site customer project: progressed from problem framing through "
        "build and industrialization to handoff and exit.",
    ),
    ("SOP", "Standard Operating Procedure; here, the 18-phase project lifecycle."),
    (
        "zones",
        "Phase groups (Zone): A pre-engagement → B build → C industrialization → D handoff & exit.",
    ),
    (
        "Zone",
        "SOP phase group: A pre-engagement → B build → C industrialization → D handoff & exit.",
    ),
    ("Gates", "Gate list: every gate that applies to this project and its status."),
    (
        "Gate",
        "Predicate-style gate: re-evaluated on every phase advance (e.g. dual sponsor, "
        "FAT/SAT sign-off); a failure blocks the advance and a stale pass never counts.",
    ),
    (
        "overlay",
        "Overlay: extra gates that only apply to the industrial profile (factory icon).",
    ),
    (
        "FAT/SAT",
        "FAT = Factory Acceptance Test; SAT = Site Acceptance Test — both need the customer's signature.",
    ),
    (
        "sponsor",
        "The project's decision-maker/funding stakeholder; this SOP requires a business "
        "and an industrial sponsor to jointly confirm success criteria.",
    ),
    (
        "works_council",
        "German Works Constitution Act (BetrVG §87) co-determination: deployments "
        "involving employee monitoring/performance need union consent.",
    ),
    (
        "air-gapped",
        "Air-gapped deployment: physically isolated from external networks; installs "
        "and updates go through an offline checklist.",
    ),
    ("气隙", "Air-gapped: a closed network physically isolated from external networks."),
    (
        "OT/IT 隔离",
        "OT/IT separation: isolating the shop-floor operational-technology network from "
        "the corporate IT network — a common industrial security requirement.",
    ),
    (
        "班次",
        "Shift system (e.g. 3 shifts); 24/7 lines need shift-handover integration (shift_handover gate).",
    ),
    (
        "工会",
        "Employee representative body; in Germany, deployments involving employee "
        "monitoring/performance require its co-determination (works_council gate).",
    ),
    (
        "SLO",
        "Service Level Objective: an internal, measurable quality commitment, e.g. "
        "'99% of tickets first-responded within 5 minutes'.",
    ),
    (
        "SLA",
        "Service Level Agreement: the external contractual commitment, usually backed by several SLOs.",
    ),
    (
        "on-call",
        "Rotating duty response: alerts route to whoever is on call so someone can act around the clock.",
    ),
    ("告警路由", "Alert route: the channel/on-call group an SLO breach pages (alert_route)."),
    (
        "runbook",
        "Operations runbook: failure-handling steps, rollback plans and escalation paths.",
    ),
    (
        "移交包",
        "Handoff package: the full artifact set delivered to the customer at project end "
        "— runbook, model, monitoring config, known limitations and more.",
    ),
    (
        "OEE",
        "Overall Equipment Effectiveness = availability × performance × quality; world-class ≥ 0.85.",
    ),
    ("MTBF", "Mean Time Between Failures (hours); higher is more reliable."),
    ("pick success", "Robotic pick success rate; DexNet benchmark ≈ 0.80."),
    (
        "DexNet",
        "UC Berkeley grasp-planning network and benchmark dataset; a common reference for pick success.",
    ),
    (
        "KPI",
        "Key Performance Indicator; the ticket and manufacturing scenarios use different catalogs.",
    ),
    (
        "Profile",
        "Scenario profile: defines available connectors, the KPI catalog and applicable "
        "gates (ticket support / manufacturing).",
    ),
    (
        "ticket",
        "Support-ticket scenario: CSV/Zammad/Salesforce/MySQL ingestion, no industrial gates.",
    ),
    (
        "manufacturing",
        "Manufacturing / embodied-robotics scenario: OPC UA, MQTT, ROS2 and other "
        "industrial feeds + 6 industrial compliance gates.",
    ),
    (
        "Context",
        "Project context: a structured set of site, stakeholders, success criteria, "
        "SLOs, functional safety and assets.",
    ),
    (
        "success_criteria",
        "Success criteria: contractual, measurable acceptance conditions signed off by both sponsors.",
    ),
    (
        "干系人",
        "Stakeholder: project roles (decision-maker, users, ops, union…) and their success metrics.",
    ),
    (
        "成功标准",
        "Success criteria (success_criteria): contractual, measurable acceptance "
        "conditions confirmed by the dual sponsors.",
    ),
    (
        "功能安全",
        "Functional Safety: standards ensuring machinery/control systems stay safe under "
        "failure (PL/SIL levels).",
    ),
    ("ISO 13849", "Machinery functional-safety standard; defines Performance Levels PL / PLr."),
    ("IEC 61508", "Functional-safety standard for E/E/PE systems; defines SIL levels."),
    (
        "ISO 10218",
        "Industrial robot safety standard: risk-assessment requirements for collaborative "
        "and regular robots.",
    ),
    ("CE", "EU conformity marking: the product meets the relevant EU directives."),
    (
        "EU AI Act",
        "EU AI Act: risk-tiered AI regulation; high-risk uses require compliance "
        "assessment and documentation.",
    ),
    ("PLr", "Required Performance Level (ISO 13849); PL is the level actually achieved."),
    ("SIL", "Safety Integrity Level (IEC 61508)."),
    (
        "Corpus",
        "Corpus: the sample set for training/eval; forging is the pipeline of cleaning, "
        "PII masking, dedup, gap-filling and synthesis.",
    ),
    (
        "语料锻造",
        "Corpus forging: raw data (CSV etc.) → PII masking → dedup → quality gate → "
        "coverage analysis → targeted synthesis → report.",
    ),
    (
        "Flywheel",
        "Flywheel: field events flow back as corpus with weekly incremental retraining — "
        "the loop that makes the system better the longer it runs.",
    ),
    (
        "飞轮",
        "The data flywheel: event backflow → corpus increment → retraining; the longer a "
        "project runs, the better the model fits that customer.",
    ),
    (
        "ISA-95",
        "The international standard for enterprise-to-shop-floor integration; the basis "
        "of the MES data model.",
    ),
    (
        "MES",
        "Manufacturing Execution System: shop-floor data source for work orders, quality and downtime.",
    ),
    (
        "OPC UA",
        "Unified industrial-automation communication protocol; reads PLC tag data directly.",
    ),
    ("PLC", "Programmable Logic Controller: the control unit of production equipment."),
    (
        "MQTT-Sparkplug",
        "MQTT: lightweight pub/sub protocol; Sparkplug B standardizes its industrial payload semantics.",
    ),
    (
        "ROS2 Bag",
        "ROS 2 recording/replay format, common for robot trajectories and sensor data.",
    ),
    ("Historian", "Time-series historian: stores process history (temperature, takt, alarms…)."),
    ("Zammad", "Open-source helpdesk/ticketing system."),
    ("Salesforce", "CRM platform; here a customer/ticket data source."),
    ("stub", "Stub: interface and data model ready, the real system not yet wired."),
    (
        "PII",
        "Personally Identifiable Information (name/email/phone); automatically masked during forging.",
    ),
    (
        "min_samples",
        "Minimum real samples per category; below it the category is a gap and triggers synthesis.",
    ),
    ("synth_per_gap", "How many synthetic samples to add per gap category."),
    ("JSONL", "One JSON object per line; common for sample and eval data."),
    (
        "drift",
        "Drift: data distribution/quality shifting over time and degrading the model; "
        "monitor it to trigger retraining.",
    ),
    ("漂移", "Drift: data distribution/quality shifting over time and eroding the model; a monitoring item."),
    (
        "bad case",
        "Bad-case mining: find poorly performing samples from eval results, then classify "
        "and attribute them.",
    ),
    (
        "force",
        "Force advance: bypasses the block, but gates still evaluate and record; "
        "exceptions land in the audit log.",
    ),
    (
        "qualification",
        "Qualification: confirm the problem is real and the customer has budget and intent.",
    ),
    (
        "stakeholder_map",
        "Stakeholder map: identify decision-makers, users, blockers and what each wants.",
    ),
    (
        "prototype",
        "Real-data prototype: build a verifiable prototype on the customer's real data, not demo data.",
    ),
    (
        "AgentState",
        "AgentScope's agent state object; the permission context is injected into the runtime through it.",
    ),
    (
        "Toolkit",
        "AgentScope's tool collection: binds connectors/functions as callable agent tools.",
    ),
    (
        "SubAgentTemplate",
        "AgentScope's sub-agent blueprint: a template with a preset role, tools and prompt.",
    ),
    (
        "技能库",
        "Skills library: reusable methodology/field notes in research / implementation / "
        "optimization / methodology.",
    ),
    ("工作台", "Workbench: cross-project overview — global stats, project matrix, recent skills."),
    (
        "现场记录",
        "Journal: research / implementation / optimization field notes; one click turns "
        "them into skill drafts.",
    ),
    ("沉淀", "Consolidate field experience into a reusable skill for later retrieval and reuse."),
    ("门禁", "Gates: the gate-check results applying to the current phase (pass/blocked)."),
]

I18N_PAIRS: list[tuple[str, str]] = [
    # -- document-level ------------------------------------------------------
    ('<html lang="zh">', '<html lang="en">'),
    ("<title>FDE Scope · 功能总览</title>", "<title>FDE Scope · Overview</title>"),
    # -- language switcher (zh pages carry the EN badge; en pages flip it) ---
    (
        '<a class="lang" href="/en/" title="English version" aria-label="Switch to English">EN</a>',
        '<a class="lang" href="/" title="中文版" aria-label="切换到中文">中文</a>',
    ),
    (
        '<a class="lang" href="/en/console" title="English version" aria-label="Switch to English">EN</a>',
        '<a class="lang" href="/console" title="中文版" aria-label="切换到中文">中文</a>',
    ),
    # -- shared nav fragments ------------------------------------------------
    (">GTM 官网 ↗</a>", ">GTM site ↗</a>"),
    (">技能手册库 ↗</a>", ">Skills handbook ↗</a>"),
    ("切换深浅主题", "Toggle light/dark theme"),
    # -- overview: topbar + hero --------------------------------------------
    ('<a href="/" class="active">功能总览</a>', '<a href="/en/" class="active">Overview</a>'),
    ('<a href="/console">Engagement 控制台 →</a>', '<a href="/en/console">Engagement console →</a>'),
    ('<a href="#arch">架构清单</a>', '<a href="#arch">Architecture</a>'),
    ('<a href="#practices">最佳实践</a>', '<a href="#practices">Best practices</a>'),
    (
        '<a href="/docs/fde_sop_full.md" target="_blank">SOP 文档</a>',
        '<a href="/docs/fde_sop_full.md" target="_blank">SOP document</a>',
    ),
    ("<h2>FDE 的完整现场工作台</h2>", "<h2>The complete field workbench for FDEs</h2>"),
    (
        "从第一次 Gemba walk 到签字移交——覆盖软件/SaaS 与具身机器人/制造业两类场景。",
        "From the first Gemba walk to signed handoff — covering software/SaaS and "
        "embodied-robotics/manufacturing scenarios.",
    ),
    (
        "18 阶段 SOP、10 个可执行合规 gate、10 个数据连接器、真实生产 KPI。</p>",
        "An 18-phase SOP, 10 executable compliance gates, 10 data connectors, real production KPIs.</p>",
    ),
    (
        '<a class="btn" href="/console">进入 Engagement 控制台</a>',
        '<a class="btn" href="/en/console">Open the engagement console</a>',
    ),
    (
        '<a class="btn ghost" href="/console#deploy"><svg class="ic"><use href="#i-bot"/></svg>Agent 部署预检</a>',
        '<a class="btn ghost" href="/en/console#deploy"><svg class="ic"><use href="#i-bot"/></svg>Agent deploy preflight</a>',
    ),
    (
        '<a class="btn ghost" href="#quickstart">快速上手</a>',
        '<a class="btn ghost" href="#quickstart">Quick start</a>',
    ),
    # -- overview: stats -----------------------------------------------------
    ('<div class="lab">SOP 阶段（4 zones）</div>', '<div class="lab">SOP phases (4 zones)</div>'),
    ('<div class="lab">可执行 gate</div>', '<div class="lab">Executable gates</div>'),
    ('<div class="lab">数据连接器</div>', '<div class="lab">Data connectors</div>'),
    ('<div class="lab">测试全绿</div>', '<div class="lab">Tests green</div>'),
    # -- overview: SOP zones --------------------------------------------------
    ("<h2>完整 SOP · 18 阶段 · 4 Zones</h2>", "<h2>Full SOP · 18 phases · 4 zones</h2>"),
    ('<div class="zname">立项勘察</div>', '<div class="zname">Pre-engagement</div>'),
    ("qualification</b> 问题框定", "qualification</b> Problem framing"),
    ("stakeholder_map</b> 双 sponsor", "stakeholder_map</b> Dual sponsor"),
    ("success_criteria</b> 契约化", "success_criteria</b> Contracted"),
    ('<div class="zname">构建</div>', '<div class="zname">Build</div>'),
    ("connect</b> 数据接入", "connect</b> Data ingestion"),
    ("corpus</b> 语料锻造", "corpus</b> Corpus forging"),
    ("prototype</b> 真实数据原型", "prototype</b> Real-data prototype"),
    ("validate</b> 验证", "validate</b> Validation"),
    ("eval</b> 评估", "eval</b> Evaluation"),
    ('<div class="zname">运营化</div>', '<div class="zname">Industrialization</div>'),
    ("runbook</b> 应急手册", "runbook</b> Emergency runbook"),
    ("monitoring</b> 漂移检测", "monitoring</b> Drift detection"),
    ("change_mgmt</b> 工会", "change_mgmt</b> Works council"),
    ("flywheel</b> 飞轮产品化", "flywheel</b> Flywheel productization"),
    ('<div class="zname">交接退场</div>', '<div class="zname">Handoff &amp; exit</div>'),
    ("ops_handoff</b> 运维移交", "ops_handoff</b> Ops handoff"),
    ("knowledge_transfer</b> 知识转移", "knowledge_transfer</b> Knowledge transfer"),
    ("disengage</b> 签字退场", "disengage</b> Signed exit"),
    # -- overview: gates ------------------------------------------------------
    (
        "<h2>10 个可执行合规 Gate（工业 overlay）</h2>",
        "<h2>10 executable compliance gates (industrial overlay)</h2>",
    ),
    (
        'Gate 是谓词，不是清单：清单记录"曾经查过"，随现实漂移单向腐化；gate 在每次推进时重新评估，过期 passed 不作数。--force 只豁免拦截、照常评估留痕，例外进入审计日志。',
        'A gate is a predicate, not a checklist: checklists record "was once checked" and rot one-way as reality drifts; '
        "gates re-evaluate on every advance and a stale pass never counts. --force only waives the block while still "
        "evaluating and recording; exceptions land in the audit log.",
    ),
    ('<div class="desc">现场勘察记录校验</div>', '<div class="desc">Site-survey record check</div>'),
    (
        '<div class="desc">双 sponsor + 可度量 done</div>',
        '<div class="desc">Dual sponsor + measurable done</div>',
    ),
    ('<div class="desc">FAT/SAT 验收签字</div>', '<div class="desc">FAT/SAT acceptance sign-off</div>'),
    (
        '<div class="desc">德国 BetrVG §87 工会共决</div>',
        '<div class="desc">German BetrVG §87 works-council co-determination</div>',
    ),
    (
        '<div class="desc">air-gapped 部署清单</div>',
        '<div class="desc">Air-gapped deployment checklist</div>',
    ),
    ('<div class="desc">24/7 班次交接集成</div>', '<div class="desc">24/7 shift-handover integration</div>'),
    ('<div class="desc">SLO + on-call 定义</div>', '<div class="desc">SLO + on-call definition</div>'),
    ('<div class="desc">移交包签字确认</div>', '<div class="desc">Handoff-package sign-off</div>'),
    # -- overview: connectors -------------------------------------------------
    ("<h2>10 个数据连接器</h2>", "<h2>10 data connectors</h2>"),
    ('<div class="desc">通用兜底，冷启动</div>', '<div class="desc">Universal fallback, cold start</div>'),
    (">真实可用</span>", ">Live</span>"),
    ('<div class="desc">关系库直连</div>', '<div class="desc">Direct relational-DB access</div>'),
    ('<div class="desc">工厂设备遥测</div>', '<div class="desc">Factory device telemetry</div>'),
    (">JSONL 可用</span>", ">JSONL</span>"),
    ('<div class="desc">工单/质量/停机</div>', '<div class="desc">Work orders / quality / downtime</div>'),
    (
        '<div class="desc">PLC tag 读取（asyncua 驱动）</div>',
        '<div class="desc">PLC tag reads (asyncua driver)</div>',
    ),
    ('<div class="desc">机器人轨迹回放</div>', '<div class="desc">Robot trajectory replay</div>'),
    ('<div class="desc">时序历史库</div>', '<div class="desc">Time-series historian</div>'),
    ('<div class="desc">工单系统</div>', '<div class="desc">Ticketing system</div>'),
    (
        '<div class="desc">PDF/Word/Excel/PPT 解析（agentscope.rag，延迟导入）</div>',
        '<div class="desc">PDF/Word/Excel/PPT parsing (agentscope.rag, lazy import)</div>',
    ),
    (">需 [agentscope]</span>", ">needs [agentscope]</span>"),
    # -- overview: ontology ---------------------------------------------------
    ("<h2>Ontology 语义层 · TBox + ABox</h2>", "<h2>Ontology semantic layer · TBox + ABox</h2>"),
    ('<div class="name">TBox 双 Schema</div>', '<div class="name">Dual TBox schemas</div>'),
    (
        "fde-core（Skill/Connector/Engagement 等核心概念）+ mfg-overlay（ISA-95 制造业 overlay，imports 复用）",
        "fde-core (Skill/Connector/Engagement core concepts) + mfg-overlay (ISA-95 manufacturing overlay, reused via imports)",
    ),
    ('<div class="name">SKOS 概念体系</div>', '<div class="name">SKOS concept schemes</div>'),
    (
        "fde-corpus-taxonomy 双向集成：corpus 引擎按概念覆盖度选样本，skill 搜索概念扩展召回",
        "Two-way fde-corpus-taxonomy integration: the corpus engine samples by concept coverage, skill search expands "
        "recall via concepts",
    ),
    ('<div class="name">SHACL-lite 校验</div>', '<div class="name">SHACL-lite validation</div>'),
    (
        "ONTO-* 错误码契约（domain/range、环引用、未声明前缀），校验失败即拦截",
        "ONTO-* error-code contract (domain/range, cycles, undeclared prefixes); a failed check blocks",
    ),
    (">10 个错误码</span>", ">10 error codes</span>"),
    ('<div class="name">JSON-LD 1.1 导出</div>', '<div class="name">JSON-LD 1.1 export</div>'),
    (
        'schema 直出；store 导出自动并入其 TBox 上下文，CLI 与 Web API 同一实现。<a href="/console#ontology">→ 本体库</a>',
        "schemas export directly; store export merges its TBox context; CLI and Web API share one implementation."
        '<a href="/en/console#ontology">→ Ontology</a>',
    ),
    (">零新依赖</span>", ">zero new deps</span>"),
    ('<span class="status s-ok">内置</span>', '<span class="status s-ok">Built-in</span>'),
    ('<div class="name">Eval 评估</div>', '<div class="name">Eval</div>'),
    ('<div class="name">Deploy 部署</div>', '<div class="name">Deploy</div>'),
    ('<div class="name">Flywheel 飞轮</div>', '<div class="name">Flywheel</div>'),
    ('<div class="name">SOP 状态机</div>', '<div class="name">SOP state machine</div>'),
    # -- overview: modules -----------------------------------------------------
    ("<h2>6 大功能模块</h2>", "<h2>6 functional modules</h2>"),
    (
        "脱敏→去重→质量门→覆盖度分析→缺口检测→针对性合成→报告。<b>核心差异化</b>：合成是补盲区不是凑数量。",
        "PII masking → dedup → quality gate → coverage analysis → gap detection → targeted synthesis → report. "
        "<b>Core differentiator</b>: synthesis fills blind spots, it doesn't pad counts.",
    ),
    (
        "ticket 指标 + 制造业 KPI（OEE/MTBF/抓取率/碰撞率）+ bad case 挖掘 + 自动建议。",
        "ticket metrics + manufacturing KPIs (OEE/MTBF/pick rate/collision rate) + bad-case mining + auto suggestions.",
    ),
    (
        '角色 Agent 真实装配：沙箱 workspace + 权限上下文（经 AgentState 注入）+ Toolkit 工具绑定 + SubAgentTemplate 蓝图，全部真实 AgentScope 2.0 API。<a href="/console#deploy">→ 部署预检台</a>',
        "Real role-agent assembly: sandboxed workspace + permission context (injected via AgentState) + Toolkit tool "
        'binding + SubAgentTemplate blueprints — all real AgentScope 2.0 APIs.<a href="/en/console#deploy">→ Deploy preflight</a>',
    ),
    (
        "概念事件→真实事件映射 + 语料回流 + 周度增量重训。",
        "Concept-event → real-event mapping + corpus backflow + weekly incremental retraining.",
    ),
    ("18 阶段推进/回滚，gate 不通过即拦截。", "18-phase advance/rollback; a failed gate blocks."),
    (">Web 控制台</div>", ">Web console</div>"),
    (
        "交互式 engagement 仪表盘 + gate + forge + KPI + Agent 部署预检（/console#deploy）+ 本体库（/console#ontology）。",
        "Interactive engagement dashboard + gates + forge + KPIs + agent deploy preflight (/en/console#deploy) + "
        "ontology (/en/console#ontology).",
    ),
    # -- overview: architecture ------------------------------------------------
    ("<h2>架构清单 · 四层 + 横切</h2>", "<h2>Architecture map · 4 layers + cross-cutting</h2>"),
    (
        '<p class="sec-note">证据化建模见 docs/architecture-model/。</p>',
        '<p class="sec-note">Evidence-based modeling: docs/architecture-model/.</p>',
    ),
    ('<div class="name">UI 层</div>', '<div class="name">UI layer</div>'),
    (
        "CLI（Typer，全延迟导入）· Web 控制台（32 路由）· QwenPaw PawApp（18 路由 /api/fde-scope）· macOS App（DMG 双击即用，即本控制台）。",
        "CLI (Typer, fully lazy imports) · Web console (32 routes) · QwenPaw PawApp (18 routes /api/fde-scope) · "
        "macOS app (double-click DMG — this console).",
    ),
    ('<div class="name">SOP 层</div>', '<div class="name">SOP layer</div>'),
    (
        "engagement/：18 阶段 · 4 zones · 10 个可执行 gate（advance 实时重评估）+ handoff；profiles/：ticket · manufacturing 场景选择器。",
        "engagement/: 18 phases · 4 zones · 10 executable gates (re-evaluated live on advance) + handoff; "
        "profiles/: ticket · manufacturing scenario selectors.",
    ),
    ('<div class="name">能力层</div>', '<div class="name">Capability layer</div>'),
    (
        "connectors · corpus · deploy · eval · flywheel · integrations · ontology · skills —— 核心数据管线，规则为底、LLM 可选增强。",
        "connectors · corpus · deploy · eval · flywheel · integrations · ontology · skills — the core data pipeline, "
        "rules-first with optional LLM enhancement.",
    ),
    ('<div class="name">横切层</div>', '<div class="name">Cross-cutting</div>'),
    (
        "llm.py（唯一 LLM 出口，失败回退规则路径）· config.py · templates/（Jinja 报告与 runbook）· paths.py（data_root 唯一路径解析）。",
        "llm.py (the only LLM egress, falls back to rule paths) · config.py · templates/ (Jinja reports and runbooks) · "
        "paths.py (single data_root path resolution).",
    ),
    ('<div class="name">文件事实源</div>', '<div class="name">Files as source of truth</div>'),
    (
        "零数据库：.fde_scope/（engagements · skills · uploads）+ reports/；一律经 fsutil.atomic_write_text 原子写。",
        "Zero database: .fde_scope/ (engagements · skills · uploads) + reports/; every write goes through "
        "fsutil.atomic_write_text.",
    ),
    ('<div class="name">外部依赖（全可选）</div>', '<div class="name">External deps (all optional)</div>'),
    (
        "AgentScope 2.0.x（extra，实测窗口 >=2.0.4.post1,&lt;3；deploy 三支柱 + documents 延迟导入）· MiMo LLM（凭据仅环境变量）· QwenPaw 宿主。",
        "AgentScope 2.0.x (extra, measured window >=2.0.4.post1,&lt;3; deploy pillars + lazy documents) · MiMo LLM "
        "(credentials via env vars only) · QwenPaw host.",
    ),
    # -- overview: invariants ---------------------------------------------------
    ("<h2>工程最佳实践 · 六条不变式</h2>", "<h2>Engineering best practices · six invariants</h2>"),
    ("</span>Gate 实时重评估</div>", "</span>Live gate re-evaluation</div>"),
    ("</span>ID 服务端生成</div>", "</span>Server-generated IDs</div>"),
    ("</span>凭据只走环境变量</div>", "</span>Credentials via env vars only</div>"),
    ("</span>原子写盘</div>", "</span>Atomic writes</div>"),
    ("</span>规则授权是唯一通道</div>", "</span>Rule grants are the only channel</div>"),
    ("</span>实测版本窗口</div>", "</span>Measured version window</div>"),
    ("AGENTS.md 契约，由架构守护测试钉住。", "The AGENTS.md contract, pinned by architecture-guard tests."),
    (
        "advance() 每次重评当前阶段全部 gate，过期通过不作数；强推也评估留痕。禁止缓存/短路。",
        "advance() re-evaluates every gate of the current phase each time; stale passes never count; forced advances "
        "still evaluate and record. No caching or short-circuits.",
    ),
    (
        "SkillRecord.id / EngagementContext.id 由所属服务分配，外部输入永远不能指定。",
        "SkillRecord.id / EngagementContext.id are assigned by the owning service; external input can never set them.",
    ),
    (
        "API key 不落 manifest / 报告 / engagement JSON / 日志。",
        "API keys never land in manifests / reports / engagement JSON / logs.",
    ),
    (
        "一切用户状态经 fsutil.atomic_write_text（临时文件 + os.replace），禁止裸 write_text。",
        "All user state goes through fsutil.atomic_write_text (temp file + os.replace); bare write_text is banned.",
    ),
    (
        "build_toolkit 不打 is_read_only（上游 ≥2.0.5 read-only 先放行）；未匹配工具按模式回退 DEFAULT→ASK / DONT_ASK→DENY。",
        "build_toolkit never flags is_read_only (upstream ≥2.0.5 auto-allows read-only first); unmatched tools fall back "
        "by mode: DEFAULT→ASK / DONT_ASK→DENY.",
    ),
    (
        "pyproject 与 docs 逐字引用同一 agentscope specifier，放宽前逐版本真库跑测。",
        "pyproject and docs quote the same agentscope specifier verbatim; widen only after per-version runs against the "
        "real library.",
    ),
    (
        "验证锚点：make test · pytest tests/test_architecture_guard.py（6 项契约）· pytest -m agentscope（真库运行时）· ruff check + format --check · 架构证据模型 docs/architecture-model/architecture-map.md",
        "Verification anchors: make test · pytest tests/test_architecture_guard.py (6 contracts) · pytest -m agentscope "
        "(real-library runtime) · ruff check + format --check · architecture evidence model "
        "docs/architecture-model/architecture-map.md",
    ),
    # -- overview: KPI ----------------------------------------------------------
    ("<h2>制造业 KPI（实测 BMW 数据）</h2>", "<h2>Manufacturing KPIs (measured on BMW data)</h2>"),
    ("<span>设备综合效率</span>", "<span>Overall Equipment Effectiveness</span>"),
    ('<div class="desc">世界级 ≥0.85</div>', '<div class="desc">World-class ≥0.85</div>'),
    ('<div class="name">抓取成功率</div>', '<div class="name">Pick success</div>'),
    ('<div class="desc">DexNet 基准 ~0.80</div>', '<div class="desc">DexNet benchmark ~0.80</div>'),
    ("<span>平均无故障(h)</span>", "<span>Mean time between failures (h)</span>"),
    ('<div class="desc">越高越好</div>', '<div class="desc">Higher is better</div>'),
    ('<div class="name">碰撞/干预率</div>', '<div class="name">Collision / intervention rate</div>'),
    ('<div class="desc">越低越好</div>', '<div class="desc">Lower is better</div>'),
    # -- overview: quickstart ------------------------------------------------------
    ("<h2>快速上手</h2>", "<h2>Quick start</h2>"),
    ('<div class="name">CLI 命令行</div>', '<div class="name">CLI</div>'),
    ("# 安装（核心层零依赖）", "# Install (core layer has zero deps)"),
    ("# 启动制造业 engagement", "# Start a manufacturing engagement"),
    ("# 推进 SOP（gate 拦截）", "# Advance the SOP (gate enforcement)"),
    ("# 语料锻造 + KPI", "# Corpus forging + KPIs"),
    ("# 生成移交包", "# Generate the handoff package"),
    ('<div class="name">Web 界面</div>', '<div class="name">Web UI</div>'),
    ("# 启动交互控制台", "# Start the interactive console"),
    ("# 控制台功能：", "# Console features:"),
    ("· 新建 engagement（选 profile）", "· Create an engagement (pick a profile)"),
    ("· 18 阶段可视化 + gate 拦截", "· 18-phase visualization + gate blocking"),
    ("· CSV → 语料锻造（HTML 报告）", "· CSV → corpus forging (HTML report)"),
    ("· KPI 计算（ticket / 制造业）", "· KPI computation (ticket / manufacturing)"),
    ("· 推进/回滚 SOP 状态机", "· Advance/roll back the SOP state machine"),
    ("· Agent 部署预检（/console#deploy）", "· Agent deploy preflight (/en/console#deploy)"),
    # -- overview: scenarios + footer ------------------------------------------------
    ("<h2>两种场景</h2>", "<h2>Two scenarios</h2>"),
    ('<div class="name">ticket · 客服工单</div>', '<div class="name">ticket · support</div>'),
    (
        "CSV/Zammad/Salesforce/MySQL 接入。意图准确率、回复采纳率、升级率评估。无工业 gate。",
        "CSV/Zammad/Salesforce/MySQL ingestion. Intent accuracy, reply adoption and escalation-rate eval. No industrial gates.",
    ),
    ('<span class="status s-ok">完整可用</span>', '<span class="status s-ok">Fully available</span>'),
    (
        '<div class="name">manufacturing · 具身机器人</div>',
        '<div class="name">manufacturing · embodied robotics</div>',
    ),
    (
        "OPC UA/MQTT/ROS2/MES/Historian 接入。OEE/MTBF/抓取率/碰撞率 + 6 个工业合规 gate。",
        "OPC UA/MQTT/ROS2/MES/Historian ingestion. OEE/MTBF/pick rate/collision rate + 6 industrial compliance gates.",
    ),
    (
        '<span class="status s-partial">核心可用 · 工业IO部分 stub</span>',
        '<span class="status s-partial">Core available · industrial IO partly stub</span>',
    ),
    (
        "<span>FDE Scope · 基于真实 AgentScope 2.0 API · MIT License</span>",
        "<span>FDE Scope · built on real AgentScope 2.0 APIs · MIT License</span>",
    ),
    (
        "<span>测试套件 CI 全绿（含架构守护测试 6 项契约）· 零配置可跑</span>",
        "<span>Test suite green in CI (including 6 architecture-guard contracts) · runs with zero config</span>",
    ),
    # -- dashboard: header + sidebar ----------------------------------------------
    (
        "72h from raw data to a deployed agent · 全 SOP 工作台",
        "72h from raw data to a deployed agent · full-SOP workbench",
    ),
    ('<a class="back" href="/">&#8592; 功能总览</a>', '<a class="back" href="/en/">&#8592; Overview</a>'),
    ('<use href="#i-gauge"/></svg>工作台</button>', '<use href="#i-gauge"/></svg>Workbench</button>'),
    ('<use href="#i-library"/></svg>技能库</button>', '<use href="#i-library"/></svg>Skills</button>'),
    ('<use href="#i-bot"/></svg>Agent 部署</button>', '<use href="#i-bot"/></svg>Agent deploy</button>'),
    ('<use href="#i-globe"/></svg>本体库</button>', '<use href="#i-globe"/></svg>Ontology</button>'),
    # -- dashboard: new engagement form -------------------------------------------
    ("<h2>新建 Engagement</h2>", "<h2>New engagement</h2>"),
    ("<label>客户</label>", "<label>Customer</label>"),
    (
        '<option value="ticket">ticket / 客服</option><option value="manufacturing">manufacturing / 制造业</option>',
        '<option value="ticket">ticket / support</option><option value="manufacturing">manufacturing / industrial</option>',
    ),
    (">+ 创建</button>", ">+ Create</button>"),
    # -- dashboard: tools card -----------------------------------------------------
    ("<h2>工具</h2>", "<h2>Tools</h2>"),
    (">报告归档</a>", ">Report archive</a>"),
    (">查看 Profiles &amp; Phases</button>", ">View Profiles &amp; Phases</button>"),
    # -- dashboard: JS workbench ----------------------------------------------------
    (">选择或创建一个 engagement 开始</div>", ">Select or create an engagement to begin</div>"),
    ("function yn(ok){return dot(ok)+(ok?'是':'否')}", "function yn(ok){return dot(ok)+(ok?'Yes':'No')}"),
    ("// -- 工作台", "// -- Workbench"),
    ('<div class="k">进行中项目</div>', '<div class="k">Active projects</div>'),
    ('<div class="k">技能总数</div>', '<div class="k">Total skills</div>'),
    ('<div class="k">待审草稿</div>', '<div class="k">Drafts to review</div>'),
    ('<div class="k">阶段分布</div>', '<div class="k">Phase mix</div>'),
    ("<h2>跨项目矩阵</h2>", "<h2>Cross-project matrix</h2>"),
    (
        '<h2>最近沉淀 <button class="ghost" style="margin-left:8px;font-size:.7rem" onclick="go(\'skills\')">去沉淀 →</button></h2>',
        '<h2>Recent skills <button class="ghost" style="margin-left:8px;font-size:.7rem" onclick="go(\'skills\')">Add skill →</button></h2>',
    ),
    (
        "'<div class=\"empty\">暂无项目 — 左侧创建第一个 engagement</div>'",
        "'<div class=\"empty\">No projects yet — create your first engagement on the left</div>'",
    ),
    ("' 完成</td>'", "' done</td>'"),
    (
        "<tr><th>客户</th><th>Profile</th><th>阶段</th><th>门禁</th><th>最近更新</th></tr>",
        "<tr><th>Customer</th><th>Profile</th><th>Phase</th><th>Gates</th><th>Updated</th></tr>",
    ),
    (
        "'<div class=\"empty\">还没有沉淀 — 把现场经验变成可复用技能</div>'",
        "'<div class=\"empty\">Nothing yet — turn field experience into reusable skills</div>'",
    ),
    (">查看来源</button>", ">View source</button>"),
    # -- dashboard: JS skills ---------------------------------------------------------
    ("// -- 技能库", "// -- Skills"),
    ("<h2>技能库</h2>", "<h2>Skills</h2>"),
    ("<label>搜索</label>", "<label>Search</label>"),
    ('placeholder="标题 / 正文关键词"', 'placeholder="title / body keywords"'),
    ("<label>分类</label>", "<label>Category</label>"),
    ('<option value="">全部</option>', '<option value="">All</option>'),
    ("<label>状态</label>", "<label>Status</label>"),
    ("'<div class=\"empty\">无匹配技能</div>'", "'<div class=\"empty\">No matching skills</div>'"),
    ("<h2>草稿审阅队列</h2>", "<h2>Draft review queue</h2>"),
    ("<h2>新建技能</h2>", "<h2>New skill</h2>"),
    ("<label>标题</label>", "<label>Title</label>"),
    ('placeholder="如：OPC UA 连接踩坑"', 'placeholder="e.g. OPC UA connection pitfalls"'),
    ("research 调研", "research"),
    ("implementation 实施", "implementation"),
    ("optimization 调优", "optimization"),
    ("methodology 方法论", "methodology"),
    ("<label>标签</label>", "<label>Tags</label>"),
    ('placeholder="逗号分隔：opcua,plc"', 'placeholder="comma-separated: opcua,plc"'),
    ("<label>正文</label>", "<label>Body</label>"),
    (">+ 沉淀技能</button>", ">+ Capture skill</button>"),
    (">发布</button>", ">Publish</button>"),
    (">编辑</button>", ">Edit</button>"),
    (">归档</button>", ">Archive</button>"),
    ("' · 来自 '", "' · from '"),
    (
        "'<div class=\"empty\">无待审草稿 — 自动捕获与 gate 提示会出现在这里</div>'",
        "'<div class=\"empty\">No drafts to review — auto-captures and gate prompts will appear here</div>'",
    ),
    ("toast('请填写标题','warn')", "toast('Please enter a title','warn')"),
    ("toast('技能已沉淀','ok')", "toast('Skill captured','ok')"),
    ("toast('已发布','ok')", "toast('Published','ok')"),
    ("toast('已归档','ok')", "toast('Archived','ok')"),
    ("toast('已保存','ok')", "toast('Saved','ok')"),
    # -- dashboard: JS journal ---------------------------------------------------------
    ("// -- 现场记录", "// -- Field journal"),
    (">沉淀为技能</button>", ">Capture as skill</button>"),
    ("'<div class=\"empty\">暂无现场记录</div>'", "'<div class=\"empty\">No journal entries yet</div>'"),
    ("<h2>现场记录</h2>", "<h2>Field journal</h2>"),
    ("<h2>追加记录</h2>", "<h2>Add entry</h2>"),
    ("<label>类型</label>", "<label>Type</label>"),
    ("<label>内容</label>", "<label>Note</label>"),
    ('placeholder="记录本次现场发现…"', 'placeholder="note what you found on site…"'),
    (">+ 记录</button>", ">+ Add entry</button>"),
    ("toast('请填写记录内容','warn')", "toast('Please enter the note text','warn')"),
    (
        "toast(`已沉淀为技能草稿: ${r.id} (${r.category})`,'ok')",
        "toast(`Captured as skill draft: ${r.id} (${r.category})`,'ok')",
    ),
    # -- dashboard: JS deploy -----------------------------------------------------------
    (
        "// -- Agent 部署（dry-run 计划，与 CLI / PawApp 同一 build_deploy_plan）",
        "// -- Agent deploy (dry-run plan; same build_deploy_plan as CLI / PawApp)",
    ),
    ("<h2>Agent 部署计划 · dry-run</h2>", "<h2>Agent deploy plan · dry-run</h2>"),
    (
        "与 <code>fde-scope deploy</code> / PawApp 走同一 <code>build_deploy_plan</code>：纯数据预览「哪个角色 Agent 拿到哪个连接器工具、对着哪个数据源」，不 import AgentScope、不调模型、不起服务。",
        'Same <code>build_deploy_plan</code> as <code>fde-scope deploy</code> / PawApp: a pure-data preview of "which '
        'role agent gets which connector tool, against which data source" — no AgentScope import, no model calls, '
        "no services started.",
    ),
    ("<label>审批模式</label>", "<label>Approval mode</label>"),
    (
        '<option value="conservative">conservative · 例行外呼/高成本也 ASK</option>',
        '<option value="conservative">conservative · ASK often (routine + high-cost)</option>',
    ),
    (
        '<option value="balanced" selected>balanced · 仅高风险 ASK</option>',
        '<option value="balanced" selected>balanced · ASK only for high-risk</option>',
    ),
    (
        '<option value="autonomous">autonomous · 无人值守（未匹配 DENY）</option>',
        '<option value="autonomous">autonomous · unattended (unmatched → DENY)</option>',
    ),
    ("<label>模型</label>", "<label>Model</label>"),
    (
        'placeholder="每行一个：名字:角色[:模型]&#10;数据员:数据分析&#10;日志员:日志分析:qwen3-14b"',
        'placeholder="one per line: name:role[:model]&#10;data:analysis&#10;logs:log-analysis:qwen3-14b"',
    ),
    ("<label>数据源</label>", "<label>Data sources</label>"),
    (
        'placeholder="每行一个：slug=路径或URL&#10;csv=examples/quickstart_csv/sample_tickets.csv"',
        'placeholder="one per line: slug=path or URL&#10;csv=examples/quickstart_csv/sample_tickets.csv"',
    ),
    (">生成部署计划</button>", ">Generate deploy plan</button>"),
    (
        '<span class="meta">角色是自由文本 → 自动归 数据/日志/文件 工具桶；匹配不上 → corpus-only</span>',
        '<span class="meta">Roles are free text → auto-bucketed into data/logs/files tools; no match → corpus-only</span>',
    ),
    (
        '<div class="empty">填写上方配置后点「生成部署计划」</div>',
        '<div class="empty">Fill in the config above, then click "Generate deploy plan"</div>',
    ),
    ("<h2>注意事项</h2>", "<h2>Good to know</h2>"),
    (
        '<b style="color:var(--fg)">数据源优先级</b>：Agent 级 <code>toolkit.sources</code> → tenant <code>sources</code> → 隐式字段（ticket 下 <code>ticket_api</code> 隐式喂 zammad/salesforce）。三处都没配的工具诚实标注 <span class="pill" style="color:var(--bad)">unbound</span>，不进 Toolkit、不假装可用。',
        '<b style="color:var(--fg)">Data-source precedence</b>: agent-level <code>toolkit.sources</code> → tenant '
        "<code>sources</code> → implicit fields (for ticket, <code>ticket_api</code> implicitly feeds "
        'zammad/salesforce). Tools configured nowhere are honestly marked <span class="pill" '
        'style="color:var(--bad)">unbound</span> — they never enter the Toolkit, no pretending.',
    ),
    (
        '<b style="color:var(--fg)">审批模式决定未匹配工具的命运</b>：绑定工具自动获得 ALLOW 规则；conservative / balanced 未匹配 → ASK（HITL 人工确认），autonomous → DENY。默认 deny 恒含 access_other_tenant / delete_any / exec_shell。',
        '<b style="color:var(--fg)">Approval mode decides unmatched tools\' fate</b>: bound tools get ALLOW rules '
        "automatically; conservative / balanced unmatched → ASK (human-in-the-loop), autonomous → DENY. Default-deny "
        "always includes access_other_tenant / delete_any / exec_shell.",
    ),
    (
        '<b style="color:var(--fg)">skills_dirs 必须真实存在</b>（含 SKILL.md 的目录），技能经 <code>Toolkit(skills_or_loaders=…)</code> 注册，路径错误装配期即报。',
        '<b style="color:var(--fg)">skills_dirs must really exist</b> (directories containing SKILL.md); skills '
        "register via <code>Toolkit(skills_or_loaders=…)</code> and bad paths fail at assembly time.",
    ),
    (
        '<b style="color:var(--fg)">凭据只走环境变量</b>（<code>FDE_SCOPE_MIMO_API_KEY</code> 等）——不进 manifest / tenant_config / 报告。',
        '<b style="color:var(--fg)">Credentials via env vars only</b> (<code>FDE_SCOPE_MIMO_API_KEY</code> etc.) — '
        "never in manifests / tenant_config / reports.",
    ),
    (
        '<b style="color:var(--fg)">连接器 sample 每调用最多 50 行</b>（MAX_TOOL_ROWS），是预览不是导出通道。',
        '<b style="color:var(--fg)">Connector samples cap at 50 rows per call</b> (MAX_TOOL_ROWS) — for preview, '
        "not bulk export.",
    ),
    (
        '<b style="color:var(--fg)">装配 ≠ 服务</b>：<code>deploy --serve</code> 需 <code>.[agentscope]</code> extra + Redis + 可达模型；2.0 无 <code>Agent.stop</code>，停服用 <code>TenantDeployer.stop()</code>。',
        '<b style="color:var(--fg)">Assembly ≠ serving</b>: <code>deploy --serve</code> needs the '
        "<code>.[agentscope]</code> extra + Redis + a reachable model; 2.0 has no <code>Agent.stop</code> — shut down "
        "via <code>TenantDeployer.stop()</code>.",
    ),
    ("'<div class=\"empty\">计算中…</div>'", "'<div class=\"empty\">Computing…</div>'"),
    ("<b>校验失败（422）</b>", "<b>Validation failed (422)</b>"),
    ("${esc(a.model||'runtime 注入')}", "${esc(a.model||'runtime-injected')}"),
    ("连接器集：", "Connectors: "),
    ("'<span class=\"meta\">仅语料工具</span>'", "'<span class=\"meta\">corpus-only tools</span>'"),
    (
        "未绑定 ${un.length} 个工具 — 在「数据源」里给对应连接器配 slug=源 即可绑定",
        '${un.length} unbound tools — set slug=source for the matching connector under "Data sources" to bind',
    ),
    ('<div class="k">Bound 工具</div>', '<div class="k">Bound tools</div>'),
    ('<div class="k">Unbound 工具</div>', '<div class="k">Unbound tools</div>'),
    ("<h2>权限规则</h2>", "<h2>Permission rules</h2>"),
    (">审批模式：", ">Approval mode: "),
    ("<summary>查看完整 manifest JSON</summary>", "<summary>View full manifest JSON</summary>"),
    (
        '\'<div class="empty" style="padding:14px">暂无</div>\'',
        '\'<div class="empty" style="padding:14px">None yet</div>\'',
    ),
    ("toast('请填写客户名','warn')", "toast('Please enter a customer name','warn')"),
    ("toast('已创建 engagement','ok')", "toast('Engagement created','ok')"),
    # -- dashboard: JS detail (tabs + overview) -------------------------------------------
    ('title="工业阶段"', 'title="Industrial phase"'),
    (">重新校验</button>", ">Re-check</button>"),
    (
        "'<div class=\"empty\">无适用 gate（当前 profile）</div>'",
        "'<div class=\"empty\">No applicable gates (current profile)</div>'",
    ),
    (">概览</div>", ">Overview</div>"),
    (">SOP 阶段</div>", ">SOP phases</div>"),
    (">现场记录</div>", ">Journal</div>"),
    ("<label>当前阶段</label>", "<label>Current phase</label>"),
    ("<label>下一阶段</label>", "<label>Next phase</label>"),
    ("'— (完成)'", "'— (done)'"),
    ("<label>进度</label>", "<label>Progress</label>"),
    (" 推进到下一阶段</button>", " Advance to next phase</button>"),
    (">force 推进</button>", ">Force advance</button>"),
    ("} ｜ system_prompt:", "} | system_prompt:"),
    (
        "（未匹配工具 → ${m.approval_policy&&m.approval_policy.mode==='autonomous'?'DENY':'ASK'}）",
        " (unmatched tools → ${m.approval_policy&&m.approval_policy.mode==='autonomous'?'DENY':'ASK'})",
    ),
    ('<div class="meta">ALLOW：', '<div class="meta">ALLOW: '),
    ('<div class="meta">DENY：', '<div class="meta">DENY: '),
    ('<div class="meta">ASK：', '<div class="meta">ASK: '),
    # -- dashboard: JS forge + KPI ----------------------------------------------------------
    ("<h2>语料锻造（CSV → CorpusReport）</h2>", "<h2>Corpus forging (CSV → CorpusReport)</h2>"),
    (">锻造</button>", ">Forge</button>"),
    ("<h2>KPI 计算</h2>", "<h2>KPI computation</h2>"),
    (">计算</button>", ">Compute</button>"),
    # -- dashboard: JS context -----------------------------------------------------------------
    ("'<div class=\"empty\">无 context 数据</div>'", "'<div class=\"empty\">No context data</div>'"),
    ("// 现场 / Site", "// Site"),
    ("<label>地点</label>", "<label>Location</label>"),
    ("<label>班次</label>", "<label>Shifts</label>"),
    (" · OT/IT 隔离 ", " · OT/IT separated "),
    (" · 气隙 ", " · air-gapped "),
    ("<label>网络</label>", "<label>Network</label>"),
    ("<label>资产</label>", "<label>Assets</label>"),
    (" 项 · 工会代表 ", " items · works council rep "),
    ("<label>备注</label>", "<label>Notes</label>"),
    (
        "'<div class=\"empty\">无现场数据（SaaS 项目）</div>'",
        "'<div class=\"empty\">No site data (SaaS project)</div>'",
    ),
    ("// 干系人", "// Stakeholders"),
    ("// 成功标准", "// Success criteria"),
    ("'<li class=\"meta\">未定义</li>'", "'<li class=\"meta\">undefined</li>'"),
    (
        '\'<tr><td colspan="4" class="meta">未定义 SLO</td></tr>\'',
        '\'<tr><td colspan="4" class="meta">No SLOs defined</td></tr>\'',
    ),
    ("// 功能安全", "// Functional safety"),
    ("<tr><td>ISO 10218 评估</td>", "<tr><td>ISO 10218 assessed</td>"),
    ("<tr><td>EU AI Act 高风险</td>", "<tr><td>EU AI Act high-risk</td>"),
    ("<tr><td>危险分析</td>", "<tr><td>Hazard analysis</td>"),
    ("<tr><td>评估备注</td>", "<tr><td>Assessment notes</td>"),
    (
        '\'<tr><td colspan="2" class="meta">非工业 profile，无功能安全数据</td></tr>\'',
        '\'<tr><td colspan="2" class="meta">Non-industrial profile — no functional-safety data</td></tr>\'',
    ),
    ("// 产物与交付", "// Assets &amp; delivery"),
    (" 语料报告</a>", " Corpus report</a>"),
    ("<h2>现场 / Site</h2>", "<h2>Site</h2>"),
    ("<h2>干系人</h2>", "<h2>Stakeholders</h2>"),
    (
        "<tr><th>姓名</th><th>角色</th><th>Sponsor</th><th>成功指标</th></tr>",
        "<tr><th>Name</th><th>Role</th><th>Sponsor</th><th>Success metric</th></tr>",
    ),
    (
        '\'<tr><td colspan="4" class="meta">未记录</td></tr>\'',
        '\'<tr><td colspan="4" class="meta">Not recorded</td></tr>\'',
    ),
    ("<h2>成功标准</h2>", "<h2>Success criteria</h2>"),
    (
        "<tr><th>名称</th><th>目标</th><th>告警路由</th><th>窗口</th></tr>",
        "<tr><th>Name</th><th>Target</th><th>Alert route</th><th>Window</th></tr>",
    ),
    ("<h2>功能安全</h2>", "<h2>Functional safety</h2>"),
    ("<h2>产物与交付</h2>", "<h2>Assets &amp; delivery</h2>"),
    ("<label>语料</label>", "<label>Corpus</label>"),
    ("<tr><th>评估指标</th><th>值</th></tr>", "<tr><th>Eval metric</th><th>Value</th></tr>"),
    ("<label>已知局限</label>", "<label>Known limitations</label>"),
    ("<label>监控</label>漂移 ", "<label>Monitoring</label>drift "),
    ("' 每日'", "' daily'"),
    (" · 质量 ", " · quality "),
    ("' 每周'", "' weekly'"),
    ("' 未启用'", "' off'"),
    # -- dashboard: advance + forge output ----------------------------------------------------
    ("toast('推进被拦截：'", "toast('Advance blocked: '"),
    (".join('；')", ".join('; ')"),
    ("<p>缺口: ", "<p>Gaps: "),
    ("||'无'}", "||'none'}"),
    (" 查看完整 HTML 报告</a>", " View full HTML report</a>"),
    ("${v.industrial?'工业':'SaaS'}", "${v.industrial?'Industrial':'SaaS'}"),
    # -- dashboard: ontology view ---------------------------------------------------------------
    (
        "// ---- Ontology 视图（只读：与 CLI `ontology` 子命令同源数据） ----",
        "// ---- Ontology view (read-only; same data as the CLI `ontology` subcommand) ----",
    ),
    ("'<span class=\"pill ind\">内置</span>'", "'<span class=\"pill ind\">Built-in</span>'"),
    ("'<span class=\"pill tkt\">工作区</span>'", "'<span class=\"pill tkt\">Workspace</span>'"),
    (
        "类 ${s.classes} · 对象属性 ${s.object_properties} · 数据属性 ${s.data_properties} · 概念体系 ${s.concept_schemes}",
        "classes ${s.classes} · object props ${s.object_properties} · data props ${s.data_properties} · "
        "concept schemes ${s.concept_schemes}",
    ),
    (">详情</button>", ">Details</button>"),
    ("'<div class=\"empty\">无 schema</div>'", "'<div class=\"empty\">No schemas</div>'"),
    (" JSON-LD（含 TBox）</button>", " JSON-LD (incl. TBox)</button>"),
    (
        '\'<div class="empty" style="padding:14px">工作区暂无实例库（ontology/stores/*.json）</div>\'',
        '\'<div class="empty" style="padding:14px">No workspace stores yet (ontology/stores/*.json)</div>\'',
    ),
    ("<h2>本体库 · TBox + ABox</h2>", "<h2>Ontology · TBox + ABox</h2>"),
    ("<h2>Schema（TBox）</h2>", "<h2>Schema (TBox)</h2>"),
    ("<h2>实例库（ABox）</h2>", "<h2>Stores (ABox)</h2>"),
    (
        "ontology_ref 指向 schema@version；导出时自动并入其 TBox 上下文（JSON-LD 1.1）。",
        "ontology_ref points at schema@version; export merges its TBox context automatically (JSON-LD 1.1).",
    ),
    ("'<div class=\"empty\">无</div>'", "'<div class=\"empty\">None</div>'"),
    ("'<div class=\"empty\">无概念体系</div>'", "'<div class=\"empty\">No concept schemes</div>'"),
    (">← 返回</button>", ">← Back</button>"),
    ("<h2>类（${(s.classes||[]).length}）</h2>", "<h2>Classes (${(s.classes||[]).length})</h2>"),
    (
        "<h2>对象属性（${(s.object_properties||[]).length}）</h2>",
        "<h2>Object properties (${(s.object_properties||[]).length})</h2>",
    ),
    (
        "<h2>数据属性（${(s.data_properties||[]).length}）</h2>",
        "<h2>Data properties (${(s.data_properties||[]).length})</h2>",
    ),
    ("<h2>概念体系（SKOS）</h2>", "<h2>Concept schemes (SKOS)</h2>"),
    ("（环引用，仅渲染一次）", " (cycle, rendered once)"),
    (" · 关键词: ", " · keywords: "),
    ("（仅存在于环中）", " (only exists inside a cycle)"),
    (">← 返回详情</button>", ">← Back to details</button>"),
    (
        "与 CLI <code>fde-scope ontology export ${esc(target)}</code> 同一实现；store 导出自动并入其 TBox。",
        "Same implementation as the CLI <code>fde-scope ontology export ${esc(target)}</code>; store export merges "
        "its TBox.",
    ),
    # -- dashboard: edit dialog ------------------------------------------------------------------
    (
        '<b id="dlg-edit-title">编辑技能正文（Markdown）</b>',
        '<b id="dlg-edit-title">Edit skill body (Markdown)</b>',
    ),
    ('placeholder="粘贴新的 Markdown 正文…"', 'placeholder="paste the new Markdown body…"'),
    (">取消</button>", ">Cancel</button>"),
    (">保存</button>", ">Save</button>"),
]

_PAIRS_SORTED = sorted(I18N_PAIRS, key=lambda pair: len(pair[0]), reverse=True)


def to_en(html: str) -> str:
    """Translate a zh UI template to its English variant (exact-substring pass)."""
    out = html
    for zh, en in _PAIRS_SORTED:
        if zh in out:
            out = out.replace(zh, en)
    return out

"""Bilingual support for the web console (fde_scope.web.app).

The Chinese pages are the source of truth: ``app.py`` holds the zh HTML
templates. This module provides:

- ``I18N_PAIRS``: exact zh -> en substring replacements, applied longest-key
  first by :func:`to_en` at import time to produce ``_OVERVIEW_HTML_EN`` /
  ``_DASHBOARD_HTML_EN``. Keys are UI literals (HTML/JS template lines), so a
  key only matches where that literal appears; API-returned domain data
  (phase names, gate blockers ...) stays Chinese on both locales.
- ``GLOSSARY_ZH``: Chinese glossary tips, rendered by the standalone
  ``/glossary`` page (``fde_scope.web.glossary``). ``GLOSSARY_EN`` carries the
  English tips for the same terms.

To keep the locales in sync: any new Chinese UI literal added to app.py needs
a pair here, and any new glossary term needs a tip in both ``GLOSSARY_ZH`` and
``GLOSSARY_EN``. ``tests/test_web.py`` guards the /en routes.
"""

#: Chinese glossary (term -> zh tip), the source of truth for /glossary.
#: ``GLOSSARY_EN`` below carries the English tips for the same terms; the page
#: renders one list per locale from these two, so a term cannot exist in only
#: one language.
GLOSSARY_ZH: list[tuple[str, str]] = [
    (
        "Gemba walk",
        "源自日语「現場」：到价值创造的第一线（车间/工位）实地走查，"
        "观察真实作业、与一线员工交谈，而不是隔着报表判断。精益/丰田生产方式的核心实践。",
    ),
    ("Gemba", "现场走查：工程师驻车间实地观察真实流程、设备与痛点（对应 site_survey 阶段）。"),
    ("FDE", "Forward Deployed Engineer，前置部署工程师：带产品驻客户现场、快速交付解决方案的工程师角色。"),
    ("Engagements", "Engagement 列表：本项目所有驻场项目的入口。"),
    ("Engagement", "一次完整的驻场客户项目：从问题框定、构建、运营化到交接退场的全过程推进单位。"),
    ("SOP", "Standard Operating Procedure，标准作业程序；这里指覆盖项目全生命周期的 18 阶段流程。"),
    ("zones", "阶段分组（Zone）：A 立项勘察 → B 构建 → C 运营化 → D 交接退场。"),
    ("Zone", "SOP 阶段分组：A 立项勘察 → B 构建 → C 运营化 → D 交接退场。"),
    ("Gates", "Gate 列表：当前项目适用的所有门禁及其状态。"),
    (
        "Gate",
        "谓词式门禁：每次推进阶段都重新评估的条件（如双 sponsor、FAT/SAT 签字），"
        "不通过即拦截，过期结果不作数。",
    ),
    ("overlay", "叠加层：仅工业 profile 才额外生效的 gate 集合（工厂小图标标记）。"),
    (
        "FAT/SAT",
        "FAT = Factory Acceptance Test 出厂验收测试；SAT = Site Acceptance Test 现场验收测试，均需客户签字。",
    ),
    ("sponsor", "项目拍板人/出资方干系人；本 SOP 要求业务与工业双 sponsor 共同确认成功标准。"),
    ("works_council", "德国《企业组织法》BetrVG §87 工会共决：涉及员工监控/绩效的部署须工会同意。"),
    ("air-gapped", "气隙部署：与外部网络物理隔离的封闭环境，安装与更新需走离线清单。"),
    ("气隙", "air-gapped：与外部网络物理隔离的封闭网络环境。"),
    ("OT/IT 隔离", "运营技术（OT）车间网与企业 IT 网隔离，是工业现场安全的常见要求。"),
    ("班次", "轮班制度（如 3 班倒）；24/7 产线的部署需集成班次交接（shift_handover gate）。"),
    ("工会", "员工代表机构；涉及员工监控/绩效的部署在德国需其共决（见 works_council gate）。"),
    ("SLO", "Service Level Objective，服务等级目标：内部可度量的质量承诺，如「99% 工单 5 分钟内首次响应」。"),
    ("SLA", "Service Level Agreement，服务等级协议：对外的合同性承诺，通常由多个 SLO 支撑。"),
    ("on-call", "轮班值班响应机制：告警路由到当班人，保证 7×24 有人处置。"),
    ("告警路由", "SLO 违约时告警送达的渠道/值班组（alert_route）。"),
    ("runbook", "运维/应急手册：故障处置步骤、回滚方案与升级路径的文档。"),
    ("移交包", "项目结束时交付客户的完整产物集合：runbook、模型、监控配置、已知局限等。"),
    ("OEE", "Overall Equipment Effectiveness，设备综合效率 = 可用率 × 性能率 × 良品率；世界级水平 ≥ 0.85。"),
    ("MTBF", "Mean Time Between Failures，平均无故障时间（小时），越高越可靠。"),
    ("pick success", "机械臂抓取成功率；参照 DexNet 基准约 0.80。"),
    ("DexNet", "UC Berkeley 的抓取规划神经网络及基准数据集，抓取成功率的常用参照。"),
    ("KPI", "Key Performance Indicator，关键绩效指标；ticket 与 manufacturing 场景使用不同目录。"),
    ("Profile", "场景档案：定义可用连接器、KPI 目录与适用 gate（ticket 客服 / manufacturing 制造业）。"),
    ("ticket", "客服工单场景：CSV/Zammad/Salesforce/MySQL 数据接入，无工业 gate。"),
    ("manufacturing", "制造业/具身机器人场景：OPC UA、MQTT、ROS2 等工业接入 + 6 个工业合规 gate。"),
    ("Context", "项目上下文：现场、干系人、成功标准、SLO、功能安全与产物的结构化集合。"),
    ("success_criteria", "成功标准：契约化、可度量的验收条件，由双 sponsor 签字确认。"),
    ("干系人", "Stakeholder：与项目相关的角色（拍板人、使用者、运维、工会…）及其成功指标。"),
    ("成功标准", "契约化、可度量的验收条件（success_criteria），双 sponsor 确认。"),
    ("功能安全", "Functional Safety：机械/控制系统在故障时仍保持安全的标准体系（PL/SIL 等级）。"),
    ("ISO 13849", "机械安全功能安全标准，定义性能等级 PL / PLr。"),
    ("IEC 61508", "电气/电子/可编程电子安全系统的功能安全标准，定义 SIL 等级。"),
    ("ISO 10218", "工业机器人安全标准：协作与常规机器人的风险评估要求。"),
    ("CE", "欧盟合规标志：产品符合相关欧盟指令方可进入欧洲市场。"),
    ("EU AI Act", "欧盟人工智能法案：按风险分级监管 AI，高风险用途需合规评估与文档。"),
    ("PLr", "Required Performance Level，要求性能等级（ISO 13849）；PL 为实际达到的等级。"),
    ("SIL", "Safety Integrity Level，安全完整性等级（IEC 61508）。"),
    ("Corpus", "语料：训练/评估模型的样本集合；锻造（forge）即清洗、脱敏、补盲、合成的流水线。"),
    ("语料锻造", "CSV 等原始数据 → 脱敏 → 去重 → 质量门 → 覆盖度分析 → 针对性合成 → 报告的流水线。"),
    ("Flywheel", "飞轮：现场事件回流为语料、周度增量重训，让系统越用越准的闭环。"),
    ("飞轮", "数据回流 → 语料增量 → 再训练的闭环：项目用得越久，模型越贴合该客户。"),
    ("ISA-95", "企业系统与车间系统集成的国际标准，MES 数据模型的依据。"),
    ("MES", "Manufacturing Execution System，制造执行系统：工单、质量、停机等车间数据源。"),
    ("OPC UA", "工业自动化统一通信协议，可直接读取 PLC tag 数据。"),
    ("OPC", "腾讯云 OPC 从业者认证（Other Professional Certification）：面向渠道伙伴的产品能力考试。"),
    ("PLC", "Programmable Logic Controller，可编程逻辑控制器：产线设备的控制单元。"),
    ("MQTT-Sparkplug", "MQTT：轻量发布/订阅协议；Sparkplug B：规范其工业载荷语义。"),
    ("ROS2 Bag", "Robot Operating System 2 的录制回放格式，常用于机器人轨迹/传感数据。"),
    ("Historian", "时序历史数据库：存储生产过程历史数据（温度、节拍、报警等）。"),
    ("Zammad", "开源客服工单系统。"),
    ("Salesforce", "CRM 平台；此处为客户/工单相关数据源。"),
    ("ACA", "Alibaba Cloud Associate：阿里云大模型助理工程师认证（入门级，aca13）。"),
    ("ACP", "Alibaba Cloud Professional：阿里云大模型专业工程师认证（进阶，acp26）。"),
    ("RAG", "Retrieval-Augmented Generation，检索增强生成：先检索知识库再生成回答。"),
    ("stub", "占位实现：接口与数据模型就绪，但尚未接通真实系统。"),
    ("PII", "Personally Identifiable Information，个人身份信息（姓名/邮箱/电话）；锻造时自动脱敏。"),
    ("min_samples", "每个类别最少真实样本数，低于即判定为缺口并触发合成。"),
    ("synth_per_gap", "每个缺口类别补充合成的样本数量。"),
    ("JSONL", "每行一个 JSON 对象的文本格式，样本与评估数据常用。"),
    ("drift", "漂移：数据分布或质量随时间偏移，可能让模型失效；需持续检测并触发再训练。"),
    ("漂移", "数据分布/质量随时间偏移，模型效果随之衰减；监控项之一。"),
    ("bad case", "失败/低质样本挖掘：从评估结果中找出表现差的样本，归类归因。"),
    ("force", "强制推进：豁免拦截，但 gate 照常评估并留痕，例外进入审计日志。"),
    ("qualification", "问题框定：确认问题真实、客户有预算与意愿的阶段。"),
    ("stakeholder_map", "干系人地图：识别拍板人、使用者、反对者等角色及其诉求。"),
    ("prototype", "真实数据原型：用客户真实数据（非演示数据）搭建可验证原型。"),
    ("AgentState", "AgentScope 的智能体状态对象；权限上下文经其注入运行时。"),
    ("Toolkit", "AgentScope 的工具集合对象：把连接器/函数绑定为智能体可调用的工具。"),
    ("SubAgentTemplate", "AgentScope 的子智能体蓝图：预置角色、工具与提示词的模板。"),
    (
        "技能库",
        "沉淀的可复用方法论/经验文档，分 research / implementation / optimization / methodology 四类。",
    ),
    ("工作台", "跨项目总览：全局统计、项目矩阵与最近沉淀。"),
    ("现场记录", "Journal：research / implementation / optimization 三类现场笔记，可一键沉淀为技能草稿。"),
    ("沉淀", "把现场经验固化成可复用技能/文档，供后续项目检索复用。"),
    ("门禁", "当前阶段适用的 gate 校验结果（通过/拦截）。"),
]


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
    (
        "OPC",
        "Tencent Cloud OPC (Other Professional Certification): the product-competency "
        "exam for channel partners.",
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
    ("ACA", "Alibaba Cloud Associate: the entry-level LLM engineer certification (aca13)."),
    ("ACP", "Alibaba Cloud Professional: the advanced LLM engineer certification (acp26)."),
    (
        "RAG",
        "Retrieval-Augmented Generation: retrieve from a knowledge base first, then generate the answer.",
    ),
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
    # -- language chrome that is not part of the rail ------------------------
    # The four-band site tree itself is compiled per locale by
    # ``layout.side_nav`` (see the ``__SIDE_NAV__`` note in ``app.py``), so its
    # labels and paths have no pairs here on purpose. A pair list cannot express
    # ``/catalog/en/index.html`` — the English path is not ``/en`` plus a prefix
    # — and the 31 rows removed to get here are exactly how the eight hand-copied
    # rails drifted out of agreement with each other.
    ("切换深浅主题", "Toggle light/dark theme"),
    # -- overview: hero ------------------------------------------------------
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
    ('<div class="desc">关系库直连</div>', '<div class="desc">Direct relational-DB access</div>'),
    ('<div class="desc">工厂设备遥测</div>', '<div class="desc">Factory device telemetry</div>'),
    ('<div class="desc">工单/质量/停机</div>', '<div class="desc">Work orders / quality / downtime</div>'),
    (
        '<div class="desc">PLC tag 读取（asyncua 驱动）</div>',
        '<div class="desc">PLC tag reads (asyncua driver)</div>',
    ),
    ('<div class="desc">时序历史库</div>', '<div class="desc">Time-series historian</div>'),
    ('<div class="desc">工单系统</div>', '<div class="desc">Ticketing system</div>'),
    (
        '<div class="desc">PDF/Word/Excel/PPT 解析（agentscope.rag，延迟导入）</div>',
        '<div class="desc">PDF/Word/Excel/PPT parsing (agentscope.rag, lazy import)</div>',
    ),
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
        "CLI（Typer，全延迟导入）· Web 控制台（86 路由）· QwenPaw PawApp（18 路由 /api/fde-scope）· macOS App（DMG 双击即用，即本控制台）。",
        "CLI (Typer, fully lazy imports) · Web console (86 routes) · QwenPaw PawApp (18 routes /api/fde-scope) · "
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
    ("<h2>工程最佳实践 · 七条不变式</h2>", "<h2>Engineering best practices · seven invariants</h2>"),
    ("</span>Gate 实时重评估</div>", "</span>Live gate re-evaluation</div>"),
    ("</span>ID 服务端生成</div>", "</span>Server-generated IDs</div>"),
    ("</span>凭据只走环境变量</div>", "</span>Credentials via env vars only</div>"),
    ("</span>原子写盘</div>", "</span>Atomic writes</div>"),
    ("</span>规则授权是唯一通道</div>", "</span>Rule grants are the only channel</div>"),
    ("</span>实测版本窗口</div>", "</span>Measured version window</div>"),
    ("</span>Web 变更路由须过认证</div>", "</span>Web mutating routes require auth</div>"),
    (
        "新路由确认未被 auth 白名单误放；token 只从 FDE_SCOPE_API_TOKEN 环境变量读，不落文件/日志/响应。",
        "New routes must not slip into the auth allowlist by mistake; the token is read from the "
        "FDE_SCOPE_API_TOKEN env var only — never in files / logs / responses.",
    ),
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
    ("<h2>制造业 KPI（虚构演示数据）</h2>", "<h2>Manufacturing KPIs (fictional demo data)</h2>"),
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
        "<span>FDE Scope · 基于真实 AgentScope 2.0 API · MIT License</span>",
        "<span>FDE Scope · built on real AgentScope 2.0 APIs · MIT License</span>",
    ),
    (
        "<span>测试套件 CI 全绿（含架构守护测试 6 项契约）· 零配置可跑</span>",
        "<span>Test suite green in CI (including 6 architecture-guard contracts) · runs with zero config</span>",
    ),
    # -- dashboard: header ---------------------------------------------------------
    # The console's sidebar tree is compiled by ``layout.side_nav`` for both
    # locales, including the five ``go('…')`` view buttons, so nothing from the
    # rail is translated here (see the note above ``切换深浅主题``).
    # -- dashboard: new engagement form -------------------------------------------
    ("<label>客户</label>", "<label>Customer</label>"),
    (
        '<option value="ticket">ticket / 客服</option><option value="manufacturing">manufacturing / 制造业</option>',
        '<option value="ticket">ticket / support</option><option value="manufacturing">manufacturing / industrial</option>',
    ),
    (">+ 创建</button>", ">+ Create</button>"),
    ("+ 新建 Engagement", "+ New engagement"),
    # -- dashboard: workbench header ------------------------------------------------
    ("<h1>工作台</h1>", "<h1>Workbench</h1>"),
    (
        '<p class="wbh-sub">跨项目总览 · 阶段推进、门禁状态与最近沉淀</p>',
        '<p class="wbh-sub">Cross-project overview · phase progress, gates and recent captures</p>',
    ),
    ("报告归档</a>", "Report archive</a>"),
    ("查看 Profiles &amp; Phases</button>", "View Profiles &amp; Phases</button>"),
    # -- dashboard: getting-started checklist ----------------------------------------
    ("<h2>三步跑通第一条 SOP</h2>", "<h2>Three steps to your first SOP run</h2>"),
    ("创建第一个 Engagement", "Create your first engagement"),
    (
        "在左侧填写客户名，选择 profile（ticket 客服 / manufacturing 制造业）。",
        "Fill in the customer name and pick a profile (ticket/support or manufacturing).",
    ),
    (">开始填写</button>", ">Start here</button>"),
    ("推进 SOP 阶段，让门禁说话", "Advance SOP phases and let the gates decide"),
    (
        "18 个阶段、10 道门禁：每次推进都会重新校验当前阶段的 gate，通过才放行，force 推进也会留档。",
        "18 phases, 10 gates: every advance re-runs the current phase's gates — only a pass lets you "
        "through, and forced advances are recorded too.",
    ),
    ("沉淀第一条可复用技能", "Capture your first reusable skill"),
    (
        "把现场经验写成技能草稿，评审通过后发布，进入技能库供下一个项目复用。",
        "Turn field experience into a skill draft; once reviewed and published it joins the skills "
        "library for the next project.",
    ),
    (">去技能库</button>", ">Go to skills</button>"),
    # -- dashboard: JS workbench ----------------------------------------------------
    (
        "选择左侧的 engagement，查看阶段、门禁与 KPI",
        "Select an engagement on the left to inspect phases, gates and KPIs",
    ),
    ("function yn(ok){return dot(ok)+(ok?'是':'否')}", "function yn(ok){return dot(ok)+(ok?'Yes':'No')}"),
    ("// -- 工作台", "// -- Workbench"),
    ('<div class="k">进行中项目</div>', '<div class="k">Active projects</div>'),
    ('<div class="k">技能总数</div>', '<div class="k">Total skills</div>'),
    ('<div class="k">待审草稿</div>', '<div class="k">Drafts to review</div>'),
    (">阶段分布</span>", ">Phase mix</span>"),
    (
        '<h2>最近沉淀 <button class="ghost sm" style="margin-left:var(--sp2)" onclick="go(\'skills\')">去沉淀 →</button></h2>',
        '<h2>Recent skills <button class="ghost sm" style="margin-left:var(--sp2)" onclick="go(\'skills\')">Add skill →</button></h2>',
    ),
    (
        "还没有 engagement —— 用上面的表单创建第一条。",
        "No engagements yet — create your first one with the form above.",
    ),
    ("dot(true)+' 完成'", "dot(true)+' done'"),
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
    ("'适用: '", "'Applies to: '"),
    ("'导出: '", "'Exports: '"),
    ("` · 来源 ${", "` · source: ${"),
    (" · 创建于 ", " · created "),
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
    ('<div class="k">总条数</div>', '<div class="k">Entries</div>'),
    ('<div class="k">调研</div>', '<div class="k">Research</div>'),
    ('<div class="k">实施</div>', '<div class="k">Implementation</div>'),
    ('<div class="k">调优</div>', '<div class="k">Optimization</div>'),
    ('<div class="k">已沉淀技能</div>', '<div class="k">Captured skills</div>'),
    (">现场记录</button>", ">Field journal</button>"),
    ('<div class="k">现场记录</div>', '<div class="k">Journal</div>'),
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
        '<b style="color:var(--fg)">数据源优先级</b>：Agent 级 <code>toolkit.sources</code> → tenant <code>sources</code> → 隐式字段（ticket 下 <code>ticket_api</code> 隐式喂 zammad/salesforce）。三处都没配的工具诚实标注 <span class="pill bad">unbound</span>，不进 Toolkit、不假装可用。',
        '<b style="color:var(--fg)">Data-source precedence</b>: agent-level <code>toolkit.sources</code> → tenant '
        "<code>sources</code> → implicit fields (for ticket, <code>ticket_api</code> implicitly feeds "
        "zammad/salesforce). Tools configured nowhere are honestly marked "
        '<span class="pill bad">unbound</span> — they never enter the Toolkit, no pretending.',
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
    ("toast('请填写客户名','warn')", "toast('Please enter a customer name','warn')"),
    ("toast('已创建 engagement','ok')", "toast('Engagement created','ok')"),
    # -- dashboard: JS detail (tabs + overview) -------------------------------------------
    ('title="工业阶段"', 'title="Industrial phase"'),
    (">重新校验</button>", ">Re-check</button>"),
    (
        "'<div class=\"empty\">无适用 gate（当前 profile）</div>'",
        "'<div class=\"empty\">No applicable gates (current profile)</div>'",
    ),
    ("<h2>Gate 台账（历次校验记录）</h2>", "<h2>Gate ledger (every check)</h2>"),
    (
        "<thead><tr><th>Gate</th><th>结果</th><th>阻塞项</th><th>警告</th><th>备注</th><th>校验时间</th></tr></thead>",
        "<thead><tr><th>Gate</th><th>Result</th><th>Blockers</th><th>Warnings</th><th>Notes</th>"
        "<th>Checked at</th></tr></thead>",
    ),
    ("<h2>数据面板</h2>", "<h2>Data panel</h2>"),
    ('<div class="k">干系人</div>', '<div class="k">Stakeholders</div>'),
    ('<div class="k">成功标准</div>', '<div class="k">Success criteria</div>'),
    ('<div class="k">Gates 通过</div>', '<div class="k">Gates passed</div>'),
    (
        "<tr><th>资产</th><th>类型</th><th>厂商</th><th>协议</th><th>关键度</th></tr>",
        "<tr><th>Asset</th><th>Type</th><th>Vendor</th><th>Protocol</th><th>Criticality</th></tr>",
    ),
    (">概览</button>", ">Overview</button>"),
    (">SOP 阶段</button>", ">SOP phases</button>"),
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
        '\'<tr><td colspan="5" class="meta">未定义 SLO</td></tr>\'',
        '\'<tr><td colspan="5" class="meta">No SLOs defined</td></tr>\'',
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
        "<tr><th>名称</th><th>目标</th><th>错误预算</th><th>告警路由</th><th>窗口</th></tr>",
        "<tr><th>Name</th><th>Target</th><th>Error budget</th><th>Alert route</th><th>Window</th></tr>",
    ),
    ("<h2>功能安全</h2>", "<h2>Functional safety</h2>"),
    ("<h2>产物与交付</h2>", "<h2>Assets &amp; delivery</h2>"),
    ("<label>语料</label>", "<label>Corpus</label>"),
    ("<tr><th>评估指标</th><th>值</th></tr>", "<tr><th>Eval metric</th><th>Value</th></tr>"),
    ("<label>已知局限</label>", "<label>Known limitations</label>"),
    ("<label>数据漂移</label>", "<label>Data drift</label>"),
    ("<label>质量漂移</label>", "<label>Quality drift</label>"),
    ("' 启用 · 节奏 '", "' enabled · cadence '"),
    (" · 阈值 ", " · threshold "),
    ("||'每日'", "||'daily'"),
    ("||'每周'", "||'weekly'"),
    ("' 未启用'", "' off'"),
    (
        "<label>反馈时延</label>目标 ${esc(mon.feedback_latency.target_hours)}h 内闭环</div>",
        "<label>Feedback latency</label>within ${esc(mon.feedback_latency.target_hours)}h</div>",
    ),
    ("<label>看板</label>", "<label>Dashboards</label>"),
    ("||'看板'", "||'Dashboard'"),
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
    # -- dashboard: guided mode tab（领域数据——阶段说明/产出清单/blocker 建议——按规约保持中文） --
    ("""onclick="tab('guided',this)">引导</button>""", """onclick="tab('guided',this)">Guided</button>"""),
    (
        '引导数据不可用<div class="hint">可能是接口瞬时失败，重新进入该 engagement 详情会重试。</div>',
        'Guided data unavailable<div class="hint">The API may have failed transiently; re-opening this engagement retries.</div>',
    ),
    ("<h2>当前阶段：", "<h2>Current phase: "),
    ("<h2>本阶段要产出什么</h2>", "<h2>What to deliver in this phase</h2>"),
    (
        "产出写入 Context / assets 后，门禁会自动重评——引导不代替验收。",
        "Once deliverables land in Context / assets, gates re-evaluate automatically — guidance never replaces acceptance.",
    ),
    ('<div class="hint">下一步做什么</div>', '<div class="hint">Next steps</div>'),
    ("门禁已通过，可推进下一阶段。", "Gate passed — you may advance to the next phase."),
    (
        "'<div class=\"empty\">本阶段无门禁——完成产出清单后即可推进</div>'",
        "'<div class=\"empty\">No gate on this phase — finish the deliverables, then advance</div>'",
    ),
    ("<h2>相关阅读（技能手册库）</h2>", "<h2>Further reading (skills catalog)</h2>"),
    # -- guided mode: goal plan + AI draft cards --------------------------------------------------
    ("<h2>项目目标与任务清单</h2>", "<h2>Project goal & task plan</h2>"),
    (
        'placeholder="输入项目目标（例：把客服首响缩到 8s 内，坏例率降到 5% 以下）"',
        'placeholder="Project goal (e.g. cut first-response to <8s, bad-case rate below 5%)"',
    ),
    (">生成任务清单</button>", ">Generate task plan</button>"),
    (
        "目标会被拆解到 SOP 各阶段，勾选状态自动保存。",
        "The goal is broken down across SOP phases; checkbox state autosaves.",
    ),
    ("（规则版：未配置 AI key）", " (rule-based: no AI key configured)"),
    (">重新生成</button>", ">Regenerate</button>"),
    ("'AI 生成'", "'AI-generated'"),
    ("'规则生成'", "'Rule-based'"),
    ("覆盖现有任务清单？勾选状态会丢失。", "Replace the existing task plan? Checkbox state will be lost."),
    ("toast('请先输入项目目标','warn')", "toast('Enter a project goal first','warn')"),
    ("'任务清单已生成（AI）'", "'Task plan generated (AI)'"),
    ("'任务清单已生成（规则版）'", "'Task plan generated (rule-based)'"),
    ("toast('已重新生成','ok')", "toast('Regenerated','ok')"),
    ("toast('任务状态已保存','ok')", "toast('Task state saved','ok')"),
    ("toast('任务状态保存失败','bad')", "toast('Failed to save task state','bad')"),
    ("toast('生成失败：'", "toast('Generation failed: '"),
    ("<h2>AI 起草 Context</h2>", "<h2>Draft context with AI</h2>"),
    (
        "用自然语言描述业务，AI 起草 现场/干系人/成功标准/SLO 草稿。写入前逐项确认，门禁通过才算数。",
        "Describe the business in plain language; AI drafts site / stakeholders / success criteria / SLOs. "
        "Review every block before applying — only the gates make it count.",
    ),
    (
        "未配置 AI key（FDE_SCOPE_MIMO_API_KEY），可打开手动填写指引，按字段说明逐项录入。",
        "No AI key configured (FDE_SCOPE_MIMO_API_KEY) — open the manual field guide and fill in each field.",
    ),
    (
        'placeholder="例：我们是一家茶饮连锁，国内 2000 家门店，客服团队每天处理大量加盟咨询与客诉，希望用工单 AI 缩短首响时间…"',
        'placeholder="e.g. We are a tea chain with 2,000 stores; our support team handles heavy franchise and complaint volume daily — we want a ticket AI to cut first-response time…"',
    ),
    ("'✨ AI 起草'", "'✨ Draft with AI'"),
    ("'✍️ 手动填写指引'", "'✍️ Manual field guide'"),
    (
        "'<div class=\"hint\">由 MiMo 起草，待你确认。勾选要采纳的块后写入；写入后门禁会实时重评。</div>'",
        '\'<div class="hint">Drafted by MiMo, pending your review. Tick the blocks to adopt and apply; '
        "gates re-evaluate live afterwards.</div>'",
    ),
    ("toast('请先描述你的业务','warn')", "toast('Describe your business first','warn')"),
    (
        "'<div class=\"hint\">起草中（最长约 1 分钟）…</div>'",
        "'<div class=\"hint\">Drafting (up to ~1 minute)…</div>'",
    ),
    ("'AI 输出无法解析，已切换手动模式'", "'AI output unparsable — switched to manual mode'"),
    ("'AI 不可用，已切换手动模式'", "'AI unavailable — switched to manual mode'"),
    (
        "'按下面的字段说明手动录入，每块单独保存（同样要过门禁才算数）。'",
        "'Fill in each field below — every block saves separately (and still has to pass the gates).'",
    ),
    (
        "`地点 ${v.location} · 班次 ${v.shift_count||1} · 气隙 ${v.air_gapped?'是':'否'}`",
        "`Location ${v.location} · shifts ${v.shift_count||1} · air-gapped ${v.air_gapped?'yes':'no'}`",
    ),
    ("'未填写'", "'Not filled'"),
    ("+' 条：'+", "+' entries: '+"),
    (".join('，')", ".join(', ')"),
    (": '空';", ": 'empty';"),
    (
        "{site:'现场 / Site', stakeholders:'干系人', success_criteria:'成功标准', slos:'SLO'}",
        "{site:'Site', stakeholders:'Stakeholders', success_criteria:'Success criteria', slos:'SLO'}",
    ),
    ("`${block} 的 JSON 不合法：`", "`${block} has invalid JSON: `"),
    ("toast('没有勾选任何块','warn')", "toast('No blocks selected','warn')"),
    (" 格式：${esc(b.line_format", " Format: ${esc(b.line_format"),
    ("`（例：${esc(b.example)}）`", "` (e.g. ${esc(b.example)})`"),
    ("toast('格式错误：'", "toast('Format error: '"),
    ("toast('没有可写入的内容','warn')", "toast('Nothing to apply','warn')"),
    ("toast('已保存，门禁已重评','ok')", "toast('Saved — gates re-evaluated','ok')"),
    ("toast('保存失败：'", "toast('Save failed: '"),
    ('<span class="k">当前值</span>', '<span class="k">Current</span>'),
    ('<span class="k">起草值</span>', '<span class="k">Drafted</span>'),
    (">JSON 微调</summary>", ">Tweak JSON</summary>"),
    (">确认写入勾选项</button>", ">Apply selected</button>"),
    (">手动填写表单</button>", ">Manual entry form</button>"),
    (">保存${esc(b.label)}</button>", ">Save ${esc(b.label)}</button>"),
    ("'也可完全手动录入：'", "'Or enter everything manually:'"),
    ("起草请求失败", "Draft request failed"),
    (" —— 可重试，或改用手动填写。", " — retry, or switch to manual entry."),
    ("<label>目标</label>", "<label>Goal</label>"),
    ('<span class="pill">当前阶段</span>', '<span class="pill">current</span>'),
    # -- dashboard: engagement tabs added in P1 §1.1 (evidence / handoff / audit) ---------------
    (
        """onclick="tab('evidence',this)">证据</button>""",
        """onclick="tab('evidence',this)">Evidence</button>""",
    ),
    ("""onclick="tab('handoff',this)">交接</button>""", """onclick="tab('handoff',this)">Handoff</button>"""),
    ("""onclick="tab('audit',this)">审计</button>""", """onclick="tab('audit',this)">Audit</button>"""),
    ('askDeleteEng(this)">删除</button>', 'askDeleteEng(this)">Delete</button>'),
    (
        """askRollback()">${icon('i-refresh')} 回滚阶段</button>""",
        """askRollback()">${icon('i-refresh')} Roll back phase</button>""",
    ),
    # -- shared confirmation dialog plumbing ----------------------------------------------------
    ("ok.textContent = cfg.confirmLabel || '确定';", "ok.textContent = cfg.confirmLabel || 'Confirm';"),
    ("toast('操作失败：'+e.message,'bad',8000)", "toast('Action failed: '+e.message,'bad',8000)"),
    # -- advance: the two toasts the force dialog introduced ------------------------------------
    (
        "toast('已是最后阶段，无可推进目标','warn',6000)",
        "toast('Already at the last phase — nothing to advance to','warn',6000)",
    ),
    (
        "toast('已 force 推进（原因已入审计）','ok',6000)",
        "toast('Force-advanced (reason recorded in the audit log)','ok',6000)",
    ),
    # -- force advance dialog -------------------------------------------------------------------
    ("title:'force 推进',", "title:'Force advance',"),
    (
        "message:`force 会越过未通过的门禁把 <b>${escapeHtml(detailStatus.current_phase)}</b> 推进到下一阶段；"
        "<b>原因必填</b>，与操作人一并写入审计。`,",
        "message:`force bypasses the failing gates and moves <b>${escapeHtml(detailStatus.current_phase)}</b> "
        "to the next phase; the <b>reason is required</b> and is written to the audit log alongside the operator.`,",
    ),
    (
        "{name:'reason', label:'原因', placeholder:'为什么必须强制推进（必填）'},",
        "{name:'reason', label:'Reason', placeholder:'Why the forced advance is unavoidable (required)'},",
    ),
    (
        "{name:'operator', label:'操作人', placeholder:'可选'},",
        "{name:'operator', label:'Operator', placeholder:'optional'},",
    ),
    ("confirmLabel:'强制推进', danger:true,", "confirmLabel:'Force advance', danger:true,"),
    (
        "validate: v => v.reason.trim() ? null : '请填写强制推进的原因',",
        "validate: v => v.reason.trim() ? null : 'Enter a reason for the forced advance',",
    ),
    # -- rollback dialog ------------------------------------------------------------------------
    (
        "toast('已在可见阶段的最前面，无可回滚目标','warn',6000)",
        "toast('Already at the first visible phase — nothing to roll back to','warn',6000)",
    ),
    ("title:'回滚阶段',", "title:'Roll back phase',"),
    (
        "message:`当前阶段 <b>${escapeHtml(detailStatus.current_phase)}</b>。回滚只能往<b>更早</b>的阶段走，"
        "门禁会在下次推进时重新校验。`,",
        "message:`Current phase: <b>${escapeHtml(detailStatus.current_phase)}</b>. Rollback only moves "
        "<b>backwards</b>; the gates are re-evaluated on the next advance.`,",
    ),
    (
        "{name:'to_phase', label:'目标阶段', type:'select', options:opts},",
        "{name:'to_phase', label:'Target phase', type:'select', options:opts},",
    ),
    (
        "{name:'reason', label:'原因', placeholder:'写入审计（可选）'},",
        "{name:'reason', label:'Reason', placeholder:'written to the audit log (optional)'},",
    ),
    ("confirmLabel:'回滚', danger:true,", "confirmLabel:'Roll back', danger:true,"),
    (
        "toast(`已回滚 ${r.from_phase} → ${r.to_phase}`,'ok',6000);",
        "toast(`Rolled back ${r.from_phase} → ${r.to_phase}`,'ok',6000);",
    ),
    # -- archive dialog -------------------------------------------------------------------------
    ("title:'归档 engagement',", "title:'Archive engagement',"),
    (
        "message:`归档 <b>${escapeHtml(customer)}</b> 后它会离开所有列表（数据保留在归档目录，审计留痕）。`,",
        "message:`Archiving <b>${escapeHtml(customer)}</b> removes it from every list (the data stays in the "
        "archive directory and the audit trail survives).`,",
    ),
    ("confirmLabel:'归档', danger:true,", "confirmLabel:'Archive', danger:true,"),
    # -- delete dialog (GDPR right to erasure) --------------------------------------------------
    ("title:'删除 engagement（GDPR 删除权）',", "title:'Delete engagement (GDPR right to erasure)',"),
    (
        "message:`将永久删除 <b>${escapeHtml(customer)}</b> 的 engagement JSON 与全部证据文件，<b>不可恢复</b>。"
        "审计日志本身按合规要求保留。<br>请原样输入客户名以确认：`,",
        "message:`Permanently deletes the engagement JSON and every evidence file for "
        "<b>${escapeHtml(customer)}</b> — <b>unrecoverable</b>. The audit log itself is retained for "
        "compliance.<br>Type the customer name exactly to confirm:`,",
    ),
    (
        "fields:[{name:'confirm', label:'客户名', placeholder:customer}],",
        "fields:[{name:'confirm', label:'Customer name', placeholder:customer}],",
    ),
    ("confirmLabel:'永久删除', danger:true,", "confirmLabel:'Delete permanently', danger:true,"),
    (
        "validate: v => v.confirm === customer ? null : '客户名不一致，已取消',",
        "validate: v => v.confirm === customer ? null : 'Customer name does not match — cancelled',",
    ),
    ("toast('已删除','ok');", "toast('Deleted','ok');"),
    # -- evidence pane --------------------------------------------------------------------------
    (
        """box.innerHTML = '<div class="card"><div class="empty">加载中…</div></div>';""",
        """box.innerHTML = '<div class="card"><div class="empty">Loading…</div></div>';""",
    ),
    ("<h2>验收证据</h2>", "<h2>Acceptance evidence</h2>"),
    (
        '<div class="hint">FAT/SAT 签字扫描件等外部凭证；留存 sha256 摘要供完整性核对。<b>摘要不是数字签名</b>，'
        "也不构成链式审计——那两项在商业版路线上。</div>",
        '<div class="hint">External artefacts such as signed FAT/SAT scans; the sha256 digest is kept for '
        "integrity checks. <b>A digest is not a digital signature</b>, and this is not a chained audit log "
        "— both are on the commercial roadmap.</div>",
    ),
    (
        "<thead><tr><th>文件</th><th>sha256</th><th>大小</th><th>留存时间</th><th>操作人</th></tr></thead>",
        "<thead><tr><th>File</th><th>sha256</th><th>Size</th><th>Stored at</th><th>Operator</th></tr></thead>",
    ),
    ("""'<div class="empty">尚无证据</div>'""", """'<div class="empty">No evidence yet</div>'"""),
    (
        '<div class="row"><label>名称</label><input id="ev-name" placeholder="留空则用文件名"></div>',
        '<div class="row"><label>Name</label><input id="ev-name" placeholder="defaults to the file name"></div>',
    ),
    (
        '<div class="row"><label>操作人</label><input id="ev-op" placeholder="可选"></div>',
        '<div class="row"><label>Operator</label><input id="ev-op" placeholder="optional"></div>',
    ),
    (
        '<button onclick="uploadEvidence()">上传证据</button>',
        '<button onclick="uploadEvidence()">Upload evidence</button>',
    ),
    (
        '<div class="hint mt1">上传需要 pro / enterprise 许可（feature: evidence）；未授权时接口返回 402 与升级指引。</div>',
        '<div class="hint mt1">Uploading requires a pro / enterprise licence (feature: evidence); without it '
        "the API returns 402 with upgrade guidance.</div>",
    ),
    ("${icon('i-alert')}加载失败：", "${icon('i-alert')}Failed to load: "),
    ("toast('请选择文件','warn')", "toast('Pick a file first','warn')"),
    ("toast('证据已留存 '", "toast('Evidence stored '"),
    ("toast('留存失败：'", "toast('Failed to store: '"),
    # -- handoff pane ---------------------------------------------------------------------------
    ("<h2>交接包</h2>", "<h2>Handoff package</h2>"),
    (
        '<div class="hint">渲染 runbook、组装 handoff package JSON，并把两个文件的 sha256 写入审计'
        "（客户勾选验收时另记一条 handoff.accepted）。</div>",
        '<div class="hint">Renders the runbook, assembles the handoff package JSON and writes the sha256 of '
        "both files to the audit log (ticking customer acceptance records a separate handoff.accepted "
        "event).</div>",
    ),
    (
        '<div class="row" style="margin-top:10px"><label>操作人</label><input id="ho-op" placeholder="可选"></div>',
        '<div class="row" style="margin-top:10px"><label>Operator</label><input id="ho-op" placeholder="optional"></div>',
    ),
    (
        '<div class="row"><label>客户已验收</label><input type="checkbox" id="ho-accept"></div>',
        '<div class="row"><label>Customer accepted</label><input type="checkbox" id="ho-accept"></div>',
    ),
    (
        '<div class="row"><label>适用边界<br><span class="meta">G7③</span></label>'
        '<textarea id="ho-boundary" rows="2" placeholder="这套方案在哪些条件下不成立：未覆盖的门店类型、'
        '数据不回传的加盟商、历史样本不足的新品……留空则保留上次记录"></textarea></div>',
        '<div class="row"><label>Applicability boundary<br><span class="meta">G7③</span></label>'
        '<textarea id="ho-boundary" rows="2" placeholder="Where the solution stops holding: store types not '
        "covered, franchisees that never send POS data, SKUs without enough history… blank keeps the previous "
        'entry"></textarea></div>',
    ),
    (
        '<div class="row"><label>终止条件<br><span class="meta">G7④</span></label>'
        '<textarea id="ho-termination" rows="2" placeholder="什么情况下停用并回退、由谁判定：SLO 连续两个'
        '窗口破线、schema 变更后未重训……留空则保留上次记录"></textarea></div>',
        '<div class="row"><label>Termination condition<br><span class="meta">G7④</span></label>'
        '<textarea id="ho-termination" rows="2" placeholder="When to stop and roll back, and who decides: SLO '
        "breached in two consecutive windows, retrain missed after a schema change… blank keeps the previous "
        'entry"></textarea></div>',
    ),
    (
        '<div class="hint mt1">G7③④ 缺失不阻塞门禁，但 <code>gate check --gate handoff_signoff</code> '
        "会给出 ⚠️ 警告——接手方没人知道边界，等于没有边界。</div>",
        '<div class="hint mt1">Missing G7③/④ does not block the gate, but <code>gate check '
        "--gate handoff_signoff</code> raises a ⚠️ warning — if nobody on the receiving side knows the "
        "boundary, there is no boundary.</div>",
    ),
    ("${icon('i-rocket')} 生成交接包</button>", "${icon('i-rocket')} Build handoff package</button>"),
    (
        '<div class="hint">客户已验收：${yn(r.customer_accepted)}</div>',
        '<div class="hint">Customer accepted: ${yn(r.customer_accepted)}</div>',
    ),
    ("${icon('i-doc')} 交接包 JSON</a>", "${icon('i-doc')} Handoff package JSON</a>"),
    ("${icon('i-folder')} 报告目录</a>", "${icon('i-folder')} Reports directory</a>"),
    ("<summary>交接摘要</summary>", "<summary>Handoff summary</summary>"),
    ("toast('交接包已生成','ok')", "toast('Handoff package built','ok')"),
    # -- audit pane -----------------------------------------------------------------------------
    ("<h2>审计轨迹（append-only）</h2>", "<h2>Audit trail (append-only)</h2>"),
    (
        '<div class="hint">共 <b>${r.count||0}</b> 条本 engagement 事件，最新在前。日志为单文件 JSONL 追加写，'
        "<b>没有哈希链，也没有数字签名</b>——它证明「发生过什么」，不防篡改；防篡改在商业版路线上。</div>",
        '<div class="hint"><b>${r.count||0}</b> events for this engagement, newest first. The log is a single '
        "append-only JSONL file with <b>no hash chain and no digital signature</b> — it proves what happened, "
        "it does not resist tampering; tamper evidence is on the commercial roadmap.</div>",
    ),
    (
        "<thead><tr><th>时间</th><th>动作</th><th>来源</th><th>详情</th></tr></thead>",
        "<thead><tr><th>Time</th><th>Action</th><th>Actor</th><th>Detail</th></tr></thead>",
    ),
    ("""'<div class="empty">尚无审计事件</div>'""", """'<div class="empty">No audit events yet</div>'"""),
    ("${icon('i-doc')} 导出 Markdown</button>", "${icon('i-doc')} Export Markdown</button>"),
    (
        '<span class="hint">导出需要 pro / enterprise 许可（feature: audit_export）。</span>',
        '<span class="hint">Exporting requires a pro / enterprise licence (feature: audit_export).</span>',
    ),
    (
        "`已导出 ${r.count} 条 → <code>${escapeHtml(String(r.path||'').split('/').pop())}</code>（报告目录）`;",
        "`Exported ${r.count} events → <code>${escapeHtml(String(r.path||'').split('/').pop())}</code> "
        "(reports directory)`;",
    ),
    ("toast('审计已导出','ok')", "toast('Audit log exported','ok')"),
    ("toast('导出失败：'", "toast('Export failed: '"),
    # -- skills: facet filters wired up in P1 §1.2 ----------------------------------------------
    ("<label>适用画像</label>", "<label>Applies to</label>"),
    ("<label>门禁</label>", "<label>Gate</label>"),
    ("<label>阶段</label>", "<label>Phase</label>"),
    # -- deploy: server-side textarea parsing (P1 §1.2) ------------------------------------------
    (
        "<b>输入格式有误（${parsed.errors.length} 行）</b>",
        "<b>Input format errors (${parsed.errors.length} lines)</b>",
    ),
    (
        "<thead><tr><th>字段</th><th>行号</th><th>原始行</th><th>原因</th></tr></thead>",
        "<thead><tr><th>Field</th><th>Line</th><th>Raw line</th><th>Reason</th></tr></thead>",
    ),
    # -- ontology: diagram / validate / diff subviews (P1 §1.2) ----------------------------------
    (">类图</button>", ">Class diagram</button>"),
    (">校验</button>", ">Validate</button>"),
    ("<h2>版本 diff（D1-D4 + ABox 影响面）</h2>", "<h2>Version diff (D1-D4 + ABox impact)</h2>"),
    ("<label>旧 schema</label>", "<label>Old schema</label>"),
    ("<label>新 schema</label>", "<label>New schema</label>"),
    ("<h2>类图 · ", "<h2>Class diagram · "),
    (
        '<p class="meta">Mermaid 源码——控制台不打包渲染器；粘贴到任意 Mermaid 渲染器（或 CLI "fde-scope ontology diagram"）出图。</p>',
        '<p class="meta">Mermaid source — the console does not bundle a renderer; paste it into any Mermaid '
        'renderer (or the CLI "fde-scope ontology diagram") to get the picture.</p>',
    ),
    ('<div class="empty">校验中…</div>', '<div class="empty">Validating…</div>'),
    ("<h2>校验 · ", "<h2>Validation · "),
    (">通过（0 个 ONTO-* 错误）<", ">Pass (0 ONTO-* errors)<"),
    ("'无破坏性变更'", "'No breaking changes'"),
    ("<b>${(r.errors||[]).length} 个错误</b>", "<b>${(r.errors||[]).length} errors</b>"),
    (
        "<thead><tr><th>错误码</th><th>主体</th><th>说明</th></tr></thead>",
        "<thead><tr><th>Code</th><th>Subject</th><th>Message</th></tr></thead>",
    ),
    ("校验失败：", "Validation failed: "),
    ("toast('请选择两个 schema','warn')", "toast('Pick two schemas first','warn')"),
    ("toast('旧 schema 与新 schema 相同','warn')", "toast('Old and new schema are the same','warn')"),
    (
        "${(r.breaking||[]).length} 个破坏性变更（D1-D4）",
        "${(r.breaking||[]).length} breaking changes (D1-D4)",
    ),
    (
        "<thead><tr><th>级别</th><th>主体</th><th>说明</th></tr></thead>",
        "<thead><tr><th>Level</th><th>Subject</th><th>Detail</th></tr></thead>",
    ),
    (
        "ABox 影响面：${(r.impact||[]).length} 个个体引用了被变更元素",
        "ABox impact: ${(r.impact||[]).length} individuals touch changed elements",
    ),
    (
        "<thead><tr><th>个体</th><th>触及</th></tr></thead>",
        "<thead><tr><th>Individual</th><th>Touches</th></tr></thead>",
    ),
    (">diff 失败：", ">Diff failed: "),
    # -- context: read-only cards gained a JSON editor (P1 §1.2) ---------------------------------
    (
        "<summary>编辑上下文（JSON · 保存后门禁重评）</summary>",
        "<summary>Edit context (JSON · gates are re-evaluated on save)</summary>",
    ),
    (
        '<button onclick="saveContextJson()">保存并重评门禁</button>',
        '<button onclick="saveContextJson()">Save and re-evaluate gates</button>',
    ),
    (
        "可编辑键：site / safety / success_criteria / stakeholders / slos / assets；后端做字段级校验，错误带字段路径。",
        "Editable keys: site / safety / success_criteria / stakeholders / slos / assets; the backend validates "
        "per field and errors carry the field path.",
    ),
    ("JSON 解析失败：", "JSON parse failed: "),
    (
        "没有可保存的字段（仅 site / safety / success_criteria / stakeholders / slos / assets）",
        "nothing to save (only site / safety / success_criteria / stakeholders / slos / assets are editable)",
    ),
    ("<b>字段校验失败</b>", "<b>Field validation failed</b>"),
    # -- workbench: engagement list search + phase/zone filters (P1 §1.2) ------------------------
    ('placeholder="搜索客户 / engagement id"', 'placeholder="Search customer / engagement id"'),
    ('<option value="">全部阶段</option>', '<option value="">All phases</option>'),
    ('<option value="">全部分区</option>', '<option value="">All zones</option>'),
    ("<label>分区</label>", "<label>Zone</label>"),
    # -- ops view: connectors / eval / flywheel / license (P1 §1.3) ------------------------------
    (
        '\'<div class="card"><div class="empty">加载中…</div></div>\'',
        '\'<div class="card"><div class="empty">Loading…</div></div>\'',
    ),
    (
        "<h2>运维 · 连接器 / eval / flywheel / license</h2>",
        "<h2>Ops · connectors / eval / flywheel / license</h2>",
    ),
    ("<b>部分面板加载失败</b>", "<b>Some panels failed to load</b>"),
    ("<h2>连接器注册表</h2>", "<h2>Connector registry</h2>"),
    (
        '<p class="meta">导入级状态：注册表里 = 依赖齐；模块表有而注册表无 = 缺可选依赖。GET 不探测客户系统连通性——那是部署时的事。凭据 env 只显示名称与「是否已配置」，值不离开本进程。</p>',
        '<p class="meta">Import-level truth: in the registry = dependencies OK; in the module table but not the '
        "registry = missing an optional dependency. The GET does not probe customer systems — that is a "
        "deploy-time act. Credential env vars show their name and a configured flag only; values never leave "
        "the process.</p>",
    ),
    (
        "<th>Slug</th><th>状态</th><th>说明</th><th>凭据 env</th>",
        "<th>Slug</th><th>Status</th><th>Note</th><th>Credential env</th>",
    ),
    (">已注册</span>", ">registered</span>"),
    (">缺可选依赖</span>", ">missing optional dep</span>"),
    ('<td colspan="4" class="meta">无连接器</td>', '<td colspan="4" class="meta">No connectors</td>'),
    ("<h2>Eval 基准</h2>", "<h2>Eval benchmark</h2>"),
    (
        '<p class="meta">指标与评分口径：${esc(String(Object.keys(ev.metrics||{}).length))} 项，全部确定性打分（LLM 只出现在生成回复那一步）。</p>',
        '<p class="meta">${esc(String(Object.keys(ev.metrics||{}).length))} metrics, all deterministic scoring '
        "(the LLM only appears when generating the reply).</p>",
    ),
    (
        "<thead><tr><th>指标</th><th>说明</th></tr></thead>",
        "<thead><tr><th>Metric</th><th>Description</th></tr></thead>",
    ),
    ("<label>用例集</label>", "<label>Cases</label>"),
    (
        'placeholder=\'JSON 数组或 JSONL 路径，例：[{"id":"t1","input":"退款怎么走"}]\'',
        'placeholder=\'JSON array or JSONL path, e.g. [{"id":"t1","input":"how do refunds work"}]\'',
    ),
    (
        '<option value="mock">mock（规则，无需 LLM）</option>',
        '<option value="mock">mock (rule-based, no LLM)</option>',
    ),
    (
        '<option value="mimo">mimo（需 LLM env）</option>',
        '<option value="mimo">mimo (needs the LLM env)</option>',
    ),
    ('<button onclick="runEval()">运行</button>', '<button onclick="runEval()">Run</button>'),
    (
        "toast('请先粘贴用例（JSON 数组）或填 JSONL 路径','warn')",
        "toast('Paste cases (a JSON array) or fill a JSONL path first','warn')",
    ),
    ("toast('用例 JSON 解析失败：'", "toast('Cases JSON parse failed: '"),
    (
        "'<div class=\"empty\">运行中（每条用例一次回复）…</div>'",
        "'<div class=\"empty\">Running (one reply per case)…</div>'",
    ),
    ("运行失败：", "Run failed: "),
    (
        '<p class="meta">计数器是<b>本服务进程</b>内的（引擎在内存）；retrain 任务是<b>描述符</b>——本进程没有任何调度器在跑，交给外部编排器触发。</p>',
        '<p class="meta">The counters are <b>this server process</b> (the engine is in-memory); the retrain jobs '
        "are <b>descriptors</b> — no scheduler runs inside this process, an external orchestrator fires them.</p>",
    ),
    (
        "<thead><tr><th>任务</th><th>计划</th><th>门槛</th><th>类型</th></tr></thead>",
        "<thead><tr><th>Job</th><th>Schedule</th><th>Threshold</th><th>Kind</th></tr></thead>",
    ),
    (
        '<span class="pill bad">已过期 → community</span>',
        '<span class="pill bad">expired → community</span>',
    ),
    ("key 来源：", "Key source: "),
    ("（env / 文件 / 无——只报来源，不显示 key）", "(env / file / none — the source only, never the key)"),
    (
        "<thead><tr><th>Feature</th><th>开关</th></tr></thead>",
        "<thead><tr><th>Feature</th><th>Granted</th></tr></thead>",
    ),
    ("<label>席位</label>", "<label>Seats</label>"),
    (" · 到期 ", " · expires "),
    (
        "// -- 运维（连接器 / eval / flywheel / license） ---------------------------",
        "// -- ops (connectors / eval / flywheel / license) --------------------------",
    ),
    ("（只显示是否已配置，不显示值）", "(shows the configured flag only, never the value)"),
    (" 条用例跑完</div>", " cases completed</div>"),
    (
        "<thead><tr><th>指标</th><th>值</th><th>说明</th></tr></thead>",
        "<thead><tr><th>Metric</th><th>Value</th><th>Description</th></tr></thead>",
    ),
    ("<summary>bad cases（${bad.length}）</summary>", "<summary>bad cases (${bad.length})</summary>"),
    # -- sop tab: cross-link to the full SOP page ------------------------------------------------
    (
        "阅读 SOP 全文（含 18 阶段详解）",
        "Read the full SOP (including the 18-phase detail)",
    ),
    # -- homepage: registry-derived connector tiles + real-data pointer (P2 §2) -------------------
    (
        '<p class="meta" style="margin:6px 0 0">状态由连接器注册表在导入时生成（依赖齐 = 已注册）；运行时能力矩阵见 <a href="/console#ops">控制台运维面板</a>。</p>',
        '<p class="meta" style="margin:6px 0 0">Status is generated from the connector registry at import time '
        "(dependencies intact = registered); the runtime capability matrix lives in the "
        '<a href="/console#ops">console ops panel</a>.</p>',
    ),
    ("机器人轨迹回放（rosbags）", "robot trajectory replay (rosbags)"),
    ("已注册</span>", "registered</span>"),
    ("缺可选依赖</span>", "missing optional dep</span>"),
    (
        '<p class="meta" style="margin:6px 0 0">换成真实数据：在控制台创建 manufacturing engagement，门禁与 KPI 探索器（/console → KPI tab）会从真实 engagement 计算；本区数字仅作版式演示。</p>',
        '<p class="meta" style="margin:6px 0 0">To make these real: create a manufacturing engagement in the '
        "console — the gates and the KPI explorer (/console → KPI tab) compute from the real engagement. "
        "The numbers here only demonstrate the layout.</p>",
    ),
    ("核心可用 · 工业 IO 已接入", "core usable · industrial IO wired in"),
    # -- retrospective tab (复盘) ----------------------------------------------
    ("（", " ("),
    ("）", ")"),
    (">复盘</button>", ">Retro</button>"),
    # -- read-only share (干系人只读分享) ---------------------------------------
    ("<h2>只读分享</h2>", "<h2>Read-only share</h2>"),
    (">生成链接</button>", ">Create link</button>"),
    (">吊销链接</button>", ">Revoke link</button>"),
    ("已启用 · 前缀 ", "enabled · prefix "),
    (": '未启用';", ": 'not enabled';"),
    ("链接（只显示这一次）：", "Link (shown only once): "),
    (
        "复制给干系人后本页不再显示 token；重新生成即吊销旧链接。",
        "Share the link with the stakeholder; this page will not show the token again. "
        "Regenerating revokes the old link.",
    ),
    ("= '已吊销';", "= 'revoked';"),
    (
        "给干系人一条只读链接：进度 + SLA + 门禁现况 + 客户签收（签收是审计证据，不推进状态机）。token 只显示一次，落盘的是 sha256。",
        "Give stakeholders a read-only link: progress + SLA + gate status + customer "
        "acknowledgement (the acknowledgement is audit evidence, it never advances the state "
        "machine). The token is shown once; only its sha256 is stored.",
    ),
    ("契约覆盖", "asset override"),
    ("默认", "default"),
    ('<div class="k">已历时</div>', '<div class="k">Elapsed</div>'),
    ('<div class="k">gate 首过率</div>', '<div class="k">gate first-pass</div>'),
    ('<div class="k">推进/被拦/强制</div>', '<div class="k">adv/blocked/forced</div>'),
    ('<div class="k">回滚</div>', '<div class="k">rollbacks</div>'),
    ("<h2>SLA 时钟</h2>", "<h2>SLA clock</h2>"),
    ("<h2>阶段时间线</h2>", "<h2>Phase timeline</h2>"),
    ("<h2>Gate 统计</h2>", "<h2>Gate stats</h2>"),
    ("<th>里程碑</th>", "<th>Milestone</th>"),
    ("<th>契约</th>", "<th>Contract</th>"),
    ("<th>状态</th>", "<th>Status</th>"),
    ("<th>说明</th>", "<th>Note</th>"),
    ("<th>阶段</th>", "<th>Phase</th>"),
    ("<th>访问</th>", "<th>Visits</th>"),
    ("<th>累计</th>", "<th>Total</th>"),
    ("<th>首次进入</th>", "<th>First entered</th>"),
    ("<th>当前</th>", "<th>Current</th>"),
    ("<th>评估</th>", "<th>Evals</th>"),
    ("<th>首过</th>", "<th>First pass</th>"),
    ("<th>通过</th>", "<th>Passes</th>"),
    ("<th>最新</th>", "<th>Latest</th>"),
    ("<th>来源</th>", "<th>Source</th>"),
    ("时间锚: ", "Anchor: "),
    ("数据源: ", "Sources: "),
    (
        "审计流重放终态与当前阶段不一致——时间线可能缺失早期事件，以下数据仅供参考。",
        "The audit replay does not end at the engagement's current phase — the trail may be missing "
        "early events; treat the numbers below as indicative only.",
    ),
    (
        "评估次数与首过来自审计流（audit.jsonl）；无审计事件的历史项目只显示 context 里的最新状态（context-only），不编造历史。",
        "Evaluation counts and first-pass come from the audit trail (audit.jsonl); projects without audit "
        "events only show the latest state recorded in the context (context-only) — history is never invented.",
    ),
]

_PAIRS_SORTED = sorted(I18N_PAIRS, key=lambda pair: len(pair[0]), reverse=True)


def to_en(html: str) -> str:
    """Translate a zh UI template to its English variant (exact-substring pass)."""
    out = html
    for zh, en in _PAIRS_SORTED:
        if zh in out:
            out = out.replace(zh, en)
    return out

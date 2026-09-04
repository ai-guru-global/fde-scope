#!/usr/bin/env python3
"""把 docs/skills-catalog/ 构建成单文件门户（GTM 风格主页 + 全部页面跳转）。

    make build-site    # 等价 python3 scripts/build_catalog_site.py

输出两个纯语言版本：docs/skills-catalog/site/index.html（中文）与
site/en/index.html（英文）。零依赖、离线可用、双击即开。
数据源是 README 表格与各页 Markdown，所以门户永远和手册库同源；
改了 catalog 之后重新跑一次本脚本即可。

英文版覆盖：界面壳（导航/英雄区/分区/筛选/页脚）、大区标签、场景、
每页一句话简介（BLURB_EN，缺一条直接构建失败）。档案正文仍以中文
Markdown 为唯一事实源，英文版在正文页顶部显示语言提示条，不做机翻。
"""

from __future__ import annotations

import html
import json
import posixpath
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "docs" / "skills-catalog"
SITE = CATALOG / "site"
OUT = SITE / "index.html"

ZONES = [
    ("zone-a-pre-engagement", "Zone A · Pre-engagement", "调研 · 摸底 · 干系人 · 成功标准", "#6366f1"),
    ("zone-b-build", "Zone B · Build", "数据接入 · 语料 · 原型 · 验证 · 部署 · 评估", "#0ea5e9"),
    (
        "zone-c-operationalization",
        "Zone C · Operationalization",
        "SLO · 监控 · 排障 · 事件 · 训练迭代",
        "#f59e0b",
    ),
    ("zone-d-handoff", "Zone D · Handoff", "文档 · 培训 · 移交演示", "#10b981"),
    ("cross-cutting", "横切 · 元能力", "skill 工程 · 评审 · 计划 · 调度 · 平台套件", "#8b5cf6"),
    ("mcp", "MCP · 服务器", "浏览器 · 抓取 · 云端 · 桌面 · 知识库 · 文档", "#e11d48"),
    ("tools", "工具 · 内置", "执行层全景 · 使用纪律", "#64748b"),
]

# (标题, 说明, [(展示名, 相对 catalog 的页面路径)])；构建时校验目标存在
SCENARIOS = [
    (
        "新人第一周",
        "三层能力模型 → 工具纪律 → 会话方法论 → 按 Zone 补场景",
        [
            ("内置工具总览", "tools/overview.md"),
            ("使用纪律", "tools/discipline.md"),
            ("MCP 服务器总览", "mcp/overview.md"),
            ("skill-discovery", "cross-cutting/skill-discovery.md"),
            ("using-superpowers-family", "cross-cutting/using-superpowers-family.md"),
        ],
    ),
    (
        "接手陌生系统",
        "wiki 化摸底 → 证据建模 → 根因排查",
        [
            ("zread", "zone-a-pre-engagement/zread.md"),
            ("architecture-visualization 套件", "cross-cutting/architecture-visualization-suite.md"),
            ("investigate", "zone-c-operationalization/investigate.md"),
            ("qmind-knowledge", "zone-a-pre-engagement/qmind-knowledge.md"),
        ],
    ),
    (
        "客户调研摸底",
        "联网检索 → 抽取 → 入知识库 → 需求探索",
        [
            ("firecrawl-search", "zone-a-pre-engagement/firecrawl-search.md"),
            ("firecrawl-scrape", "zone-a-pre-engagement/firecrawl-scrape.md"),
            ("firecrawl-parse", "zone-a-pre-engagement/firecrawl-parse.md"),
            ("qmind-knowledge", "zone-a-pre-engagement/qmind-knowledge.md"),
            ("brainstorming", "zone-a-pre-engagement/brainstorming.md"),
        ],
    ),
    (
        "方案书与选型",
        "模型决策 → 讲清楚 → 画出来 → 交付格式",
        [
            ("huggingface-best", "zone-b-build/huggingface-best.md"),
            ("bailian-cli 家族", "cross-cutting/bailian-cli.md"),
            ("architecture-communicator", "zone-a-pre-engagement/architecture-communicator.md"),
            ("drawio", "zone-a-pre-engagement/drawio.md"),
            ("pptx", "zone-d-handoff/pptx.md"),
        ],
    ),
    (
        "数据接入与语料",
        "画像 → 转换 → 挂库 → 查询 → 协议接入",
        [
            ("read-file", "zone-b-build/read-file.md"),
            ("convert-file", "zone-b-build/convert-file.md"),
            ("attach-db", "zone-b-build/attach-db.md"),
            ("query", "zone-b-build/query.md"),
            ("mqtt-development", "zone-b-build/mqtt-development.md"),
            ("firecrawl-crawl", "zone-a-pre-engagement/firecrawl-crawl.md"),
        ],
    ),
    (
        "训练与评估",
        "数据集 → 嵌入训练 → 本地评测 → 闭环",
        [
            ("huggingface-datasets", "zone-b-build/huggingface-datasets.md"),
            ("train-sentence-transformers", "zone-b-build/train-sentence-transformers.md"),
            ("huggingface-community-evals", "zone-b-build/huggingface-community-evals.md"),
            ("phoenix-evals", "zone-b-build/phoenix-evals.md"),
            ("bailian-train-deploy", "zone-b-build/bailian-train-deploy.md"),
        ],
    ),
    (
        "部署上线",
        "本地推理 → 容器 → 编排 → IaC → 快速 demo",
        [
            ("huggingface-local-models", "zone-b-build/huggingface-local-models.md"),
            ("vllm-deploy-docker", "zone-b-build/vllm-deploy-docker.md"),
            ("docker-build-deploy", "zone-b-build/docker-build-deploy.md"),
            ("kubernetes-specialist", "zone-b-build/kubernetes-specialist.md"),
            ("alibabacloud-spec-ops-suite", "zone-b-build/alibabacloud-spec-ops-suite.md"),
            ("vercel-deploy", "zone-b-build/vercel-deploy.md"),
        ],
    ),
    (
        "运维与排障",
        "根因 → 浏览器取证 → 可观测性 → AIOps",
        [
            ("investigate", "zone-c-operationalization/investigate.md"),
            ("systematic-debugging", "zone-c-operationalization/systematic-debugging.md"),
            ("chrome-devtools", "zone-c-operationalization/chrome-devtools.md"),
            ("datadog", "zone-c-operationalization/datadog.md"),
            ("sentry-mcp", "zone-c-operationalization/sentry-mcp.md"),
            ("starops", "zone-c-operationalization/starops.md"),
        ],
    ),
    (
        "文档与移交",
        "补文档 → 出版级 PDF → 规范 → 课程 → 播客",
        [
            ("document-generate", "zone-d-handoff/document-generate.md"),
            ("make-pdf", "zone-d-handoff/make-pdf.md"),
            ("anthropic-documentation", "zone-d-handoff/anthropic-documentation.md"),
            ("slidev", "zone-d-handoff/slidev.md"),
            ("shifu", "zone-d-handoff/shifu.md"),
            ("podcast", "zone-d-handoff/podcast.md"),
        ],
    ),
    (
        "工程纪律（横切）",
        "计划 → 执行 → 评审 → 安全 → 生态与调度",
        [
            ("writing-plans", "cross-cutting/writing-plans.md"),
            ("executing-plans", "cross-cutting/executing-plans.md"),
            ("code-review", "cross-cutting/code-review.md"),
            ("security-scan", "cross-cutting/security-scan.md"),
            ("skill-discovery", "cross-cutting/skill-discovery.md"),
            ("using-git-worktrees", "cross-cutting/using-git-worktrees.md"),
            ("schedule", "cross-cutting/schedule.md"),
            ("cloud-agents", "cross-cutting/cloud-agents.md"),
        ],
    ),
]


# --------------------------------------------------------------------------- 英文文案（界面壳 + 大区 + 场景 + 简介翻译）

# zone_id -> (英文大区名, 英文副题)；缺省回退中文
ZONES_EN = {
    "zone-a-pre-engagement": ("Zone A · Pre-engagement", "research · discovery · stakeholders · success criteria"),
    "zone-b-build": ("Zone B · Build", "data ingest · corpus · prototype · validation · deploy · evaluation"),
    "zone-c-operationalization": ("Zone C · Operationalization", "SLO · monitoring · incidents · training iteration"),
    "zone-d-handoff": ("Zone D · Handoff", "docs · training · handover demo"),
    "cross-cutting": ("Cross-cutting · Meta-skills", "skill engineering · review · planning · scheduling · platform suites"),
    "mcp": ("MCP · Servers", "browser · scraping · cloud · desktop · knowledge · docs"),
    "tools": ("Tools · Built-in", "execution-layer panorama · usage discipline"),
}

# 中文场景标题 -> (英文标题, 英文说明)
SCENARIOS_EN = {
    "新人第一周": ("First Week", "three-layer capability model → tool discipline → session methodology → fill scenarios by zone"),
    "接手陌生系统": ("Taking Over an Unfamiliar System", "wiki recon → evidence modeling → root-cause investigation"),
    "客户调研摸底": ("Customer Discovery", "web search → extraction → knowledge base → requirement exploration"),
    "方案书与选型": ("Proposals & Model Selection", "model decisions → explain clearly → draw it → delivery formats"),
    "数据接入与语料": ("Data Ingest & Corpus", "profile → convert → attach DB → query → protocol ingest"),
    "训练与评估": ("Training & Evaluation", "datasets → embedding training → local evals → closed loop"),
    "部署上线": ("Deploy to Production", "local inference → containers → orchestration → IaC → quick demo"),
    "运维与排障": ("Ops & Troubleshooting", "root cause → browser forensics → observability → AIOps"),
    "文档与移交": ("Docs & Handoff", "fill docs → publication-grade PDF → standards → courses → podcast"),
    "工程纪律（横切）": ("Engineering Discipline (Cross-cutting)", "plan → execute → review → security → ecosystem & scheduling"),
}

# 页面路由（不含 .md）-> 英文一句话；英文构建缺任一条即失败
BLURB_EN = {
    # Zone A
    "zone-a-pre-engagement/firecrawl-search": "Live web search with full-page extraction",
    "zone-a-pre-engagement/firecrawl-scrape": "Any URL → clean Markdown",
    "zone-a-pre-engagement/firecrawl-crawl": "Bulk extraction across whole sites or doc sections",
    "zone-a-pre-engagement/firecrawl-parse": "Local files (PDF/DOCX/spreadsheets) → Markdown",
    "zone-a-pre-engagement/zread": "One-shot wiki for an unfamiliar codebase",
    "zone-a-pre-engagement/qmind-knowledge": "Knowledge-base retrieval / upload / compile",
    "zone-a-pre-engagement/brainstorming": "Requirements exploration before creative work",
    "zone-a-pre-engagement/architecture-communicator": "Explain architecture per audience",
    "zone-a-pre-engagement/drawio": "Editable delivery diagrams",
    "zone-a-pre-engagement/pdf": "PDF parsing / generation / forms",
    "zone-a-pre-engagement/docx": "Word parsing / generation / processing",
    "zone-a-pre-engagement/xlsx": "Excel parsing / generation / formulas",
    "zone-a-pre-engagement/grill-me": "Interrogates vague requirements into a spec before you build (mattpocock/skills, 1M installs)",
    "zone-a-pre-engagement/crm-lookup": "HubSpot official CLI for contacts / deals / associations (agent-cli-skills)",
    # Zone B
    "zone-b-build/read-file": "Profile any data file",
    "zone-b-build/convert-file": "Convert between data file formats",
    "zone-b-build/attach-db": "Attach databases to a DuckDB session",
    "zone-b-build/query": "DuckDB SQL / natural-language queries",
    "zone-b-build/spatial": "Geospatial data analysis",
    "zone-b-build/mqtt-development": "MQTT development patterns reference",
    "zone-b-build/bailian-train-deploy": "Bailian data → train → deploy loop",
    "zone-b-build/huggingface-datasets": "HF Datasets Viewer API workflows",
    "zone-b-build/train-sentence-transformers": "Embedding / reranker model training",
    "zone-b-build/rag-agent-builder": "Build RAG agents",
    "zone-b-build/frontend-design": "High-design-quality frontend",
    "zone-b-build/ui-designer": "UI design systems + prototypes",
    "zone-b-build/shadcn": "shadcn/ui component system",
    "zone-b-build/vercel-deploy": "Ship demos fast",
    "zone-b-build/cloudflare": "Workers / Pages / KV platform",
    "zone-b-build/kubernetes-specialist": "K8s field delivery / troubleshooting",
    "zone-b-build/docker-build-deploy": "Docker productionization",
    "zone-b-build/alibabacloud-workbench-cli": "ECS ops without public IPs",
    "zone-b-build/alibabacloud-core-suite": "Alibaba Cloud OpenAPI/CLI 9-piece suite (cross-account query / SDK gen / TF import)",
    "zone-b-build/alibabacloud-spec-ops-suite": "Alibaba Cloud IaC pipeline 6-piece suite (plan → codegen → validate → apply)",
    "zone-b-build/vllm-deploy-docker": "Official vLLM container deployment",
    "zone-b-build/vllm-ascend": "Ascend NPU vLLM adaptation (registry name `vllm-ascend-deploy`)",
    "zone-b-build/huggingface-local-models": "llama.cpp + GGUF local inference (air-gapped / intranet / Mac demos)",
    "zone-b-build/huggingface-best": "Open-model selection decisions (complements bailian-model-recommend)",
    "zone-b-build/huggingface-community-evals": "Local evals with inspect-ai / lighteval",
    "zone-b-build/phoenix-evals": "Arize Phoenix evaluator development (rules + LLM judge)",
    "zone-b-build/evaluating-llms-harness": "lm-evaluation-harness wrapper",
    "zone-b-build/huggingface-spaces": "HF Spaces demo hosting (Gradio / Docker / ZeroGPU)",
    "zone-b-build/postman": "Collection / Mock / agent-ready API lifecycle (3 skills)",
    "zone-b-build/bigquery-basics": "Official Google BigQuery basics (`bq` CLI + SQL)",
    "zone-b-build/using-dbt-for-analytics-engineering": "Official dbt analytics-engineering workflow (models / tests / breaking-change process)",
    "zone-b-build/airflow": "Official Astronomer Airflow DAG orchestration (`af` CLI)",
    "zone-b-build/qdrant-clients-sdk": "Official Qdrant vector-DB SDKs in six languages",
    "zone-b-build/langgraph-persistence": "Official LangGraph checkpoint persistence (customer-stack fit; complements the AgentScope base)",
    "zone-b-build/building-pydantic-ai-agents": "Official Pydantic AI agent building (`@agent.tool` / TestModel; pydantic v2 kinship)",
    "zone-b-build/mlflow-agent-evaluation": "Official MLflow LLM evaluation / tracing (registry name `agent-evaluation`)",
    "zone-b-build/wandb-primary": "Official W&B experiment-tracking entry (wandb/skills)",
    "zone-b-build/playwright-cli": "Official Microsoft Playwright test-run CLI (137K installs; debugging defers to chrome-devtools)",
    "zone-b-build/prompt-engineering-patterns": "Prompt-engineering pattern library (CoT / structured output / routing / guardrails)",
    "zone-b-build/openapi-spec-generation": "OpenAPI 3.1 spec generation with Spectral / Redocly linting",
    "zone-b-build/modbus-debug": "Register-level Modbus RTU/TCP line debugging (low-install community skill; gate before installing)",
    # Zone C
    "zone-c-operationalization/starops": "Alibaba Cloud AIOps diagnostics",
    "zone-c-operationalization/investigate": "Root-cause-driven systematic investigation",
    "zone-c-operationalization/systematic-debugging": "Debugging methodology (locate first, then fix)",
    "zone-c-operationalization/troubleshooting": "Browser connection / target issues",
    "zone-c-operationalization/chrome-devtools": "DevTools debugging & automation",
    "zone-c-operationalization/sentry-mcp": "Sentry error / performance tracing",
    "zone-c-operationalization/datadog": "Official Datadog MCP observability (ddsetup / ddconfig / ddtoolsets)",
    "zone-c-operationalization/sre-runbooks": "SRE runbook templates (registry name `knowledge-work-plugins@runbook`)",
    "zone-c-operationalization/incident-response": "Official Anthropic incident response",
    "zone-c-operationalization/gke-observability": "GKE / K8s observability",
    "zone-c-operationalization/firecrawl-monitor": "Web change monitoring & alerts",
    "zone-c-operationalization/deploy-checklist": "Pre-launch verification checklist (registry name `knowledge-work-plugins@deploy-checklist`; source-verified)",
    "zone-c-operationalization/huggingface-llm-trainer": "SFT / DPO / GRPO on HF Jobs",
    "zone-c-operationalization/huggingface-vision-trainer": "Detection / classification / segmentation training",
    "zone-c-operationalization/trl-training": "Local training with TRL CLI",
    "zone-c-operationalization/web-perf": "Core Web Vitals analysis",
    "zone-c-operationalization/debug-optimize-lcp": "LCP-focused optimization",
    "zone-c-operationalization/memory-leak-debugging": "JS / Node memory leaks",
    "zone-c-operationalization/grafana-dashboarding": "Official Grafana dashboards-as-code (registry name `dashboarding`; self-managed stack delivery)",
    "zone-c-operationalization/llm-evaluation": "LLM evaluation methodology (metric choice / judges / consistency checks)",
    "zone-c-operationalization/gdpr-data-handling": "GDPR data-processing compliance (Art. 6/9/17; one-month DSAR deadline)",
    "zone-c-operationalization/terraform-style-guide": "Official HashiCorp Terraform style guide (`for_each` over count; keep state out of git)",
    # Zone D
    "zone-d-handoff/document-generate": "Generate missing docs from scratch",
    "zone-d-handoff/document-release": "Post-release doc sync",
    "zone-d-handoff/make-pdf": "Markdown → publication-grade PDF",
    "zone-d-handoff/anthropic-documentation": "Documentation writing standards (registry name `knowledge-work-plugins@documentation`)",
    "zone-d-handoff/shifu": "Knowledge base → teaching course",
    "zone-d-handoff/remember": "K8s networking flashcards (scoped to K8s networking)",
    "zone-d-handoff/visual-deck-builder": "Image-model-driven PPT decks",
    "zone-d-handoff/pptx": "PowerPoint manipulation",
    "zone-d-handoff/slidev": "Developer slides (Markdown / Vue)",
    "zone-d-handoff/notion-infographic": "Docs → infographic series",
    "zone-d-handoff/podcast": "Knowledge base → two-host podcast audio",
    "zone-d-handoff/lark-openapi-explorer": "Official Feishu/Lark OpenAPI explorer (635.6K installs; owner is domain `open.feishu.cn`)",
    # Cross-cutting
    "cross-cutting/skill-discovery": "`find-skills`: search / install / audit the skill ecosystem (source of this catalog's 📦 items)",
    "cross-cutting/create-skill": "Create new Qoder Agent Skills",
    "cross-cutting/writing-skills": "Skill writing & deployment verification",
    "cross-cutting/create-plugin": "Skills / external sources → distributable plugins",
    "cross-cutting/skill-criticagent": "Pre-install skill vetting",
    "cross-cutting/mcp-criticagent": "MCP server evaluation",
    "cross-cutting/architecture-visualization-suite": "Architecture-visualization 13-piece suite (router + scenarios + foundations)",
    "cross-cutting/code-review": "CodeRabbit code review",
    "cross-cutting/security-scan": "Security scanning (L2/L3)",
    "cross-cutting/writing-plans": "Plan first for multi-step tasks",
    "cross-cutting/executing-plans": "Execute plans with review checkpoints",
    "cross-cutting/dispatching-parallel-agents": "Dispatch independent tasks in parallel",
    "cross-cutting/using-git-worktrees": "Isolated workspaces",
    "cross-cutting/schedule": "Scheduled / recurring tasks",
    "cross-cutting/cloud-agents": "Always-on cloud agents (**two plugins**: REST v1.1.0 + MCP v0.1.0)",
    "cross-cutting/bailian-cli": "Bailian `bl` family hub (9 skills via `bl skill init`)",
    "cross-cutting/using-superpowers-family": "Superpowers **14**-piece set (methodology family with session-start hooks)",
    "cross-cutting/gstack-suite": "GStack bundled **53**-piece set / 43 registered-callable today (full YC dev workflow)",
    "cross-cutting/knowledge-work-suite": "anthropics/knowledge-work-plugins: **230** skills / 497.5K installs (**install individually as needed, not wholesale**)",
    "cross-cutting/anthropics-official-skills": "Anthropic official skills repo profile (19 skills; skill-creator at 367K installs; **install individually, not wholesale**)",
    "cross-cutting/trailofbits-security-suite": "Trail of Bits security suite, 43 plugins (static analysis / differential audit / supply chain, via plugin marketplace)",
    # MCP
    "mcp/overview": "Three-layer capability model + panorama of 9 servers / 178 tools (start here)",
    "mcp/cloud-agents-qca": "82 tools across the cloud-agent lifecycle (environments / sessions / files / memory / credentials / deploys)",
    "mcp/chrome-devtools-mcp": "29 tools for full-stack browser debugging (perf / network / AX snapshots / heap snapshots)",
    "mcp/firecrawl-mcp": "27 tools for web data (search / scrape / crawl / monitor / paper research)",
    "mcp/browser-use": "16 lightweight browser-interaction tools (no perf/emulation; heavy work defers to chrome-devtools)",
    "mcp/computer-use": "10 tools automating macOS native apps via the AX tree",
    "mcp/qmind-mcp": "7 tools for QMind knowledge-base retrieval / ingest",
    "mcp/record-and-replay": "Record human workflows → generate skills (3 tools)",
    "mcp/extension-market": "Official extension-market search / install (2 tools; evaluate before installing)",
    "mcp/cloudflare-docs-mcp": "Official Cloudflare docs retrieval / migration guides (2 tools; retrieval-first)",
    # Tools
    "tools/overview": "Built-in tool panorama: files / search / execution / web / tasks / delegation / MCP meta-tools / multi-session",
    "tools/discipline": "Usage discipline: Read-before-Edit, dedicated tools first, parallel/background, risk & verification",
}

# 各语言界面固定文案；JS 经 DATA.l10n 读取
L10N = {
    "zh": {
        "htmlLang": "zh-CN",
        "docTitle": "FDE Skills 手册库 · 门户",
        "brandSuffix": "手册库",
        "gtaText": "GTM 官网 ↗",
        "gtaHref": "../../../GTM/index.html",
        "langHref": "./en/",
        "langLabel": "ENGLISH",
        "searchPh": "搜索 {n} 页 skills / tools / MCP…",
        "heroH1": "FDE Skills 手册库",
        "heroP": "每个能力一页档案：能做什么 · 何时用（含反向边界）· 最佳实践 · 在 fde-scope 项目中的应用位点。覆盖三层——skills（按 FDE 四 Zone + 横切）、MCP 服务器工具面、内置工具——先选场景，再进页面。",
        "statUnits": {"pages": "页能力档案", "installed": "已安装", "installable": "可安装", "zones": "大区", "scenarios": "场景入口"},
        "secTaskT": "按任务开始",
        "secTaskD": "GTM 场景速查：从任务进入，而不是从目录进入",
        "secPhaseT": "按阶段浏览",
        "secPhaseD": "FDE 四 Zone + 横切元能力 + MCP 服务器 + 内置工具",
        "secAllT": "全部能力档案",
        "secAllD": "支持搜索与状态筛选",
        "filterAll": "全部",
        "nohit": "没有匹配的 skill",
        "itemsSuffix": "项",
        "badgeTxt": {"ok": "已安装", "pkg": "可安装", "dead": "已移除"},
        "crumbHome": "主页",
        "langNote": "",
        "footer1": "FDE Skills 手册库 · {total} 页（✅ {installed} · 📦 {installable}）· 建档 2026-08-27 · 数据源 README + 各页 Markdown",
        "footer2": "一致性门禁 <code>make check-catalog</code> · 本地对账 <code>make check-local</code> · 改目录后 <code>make build-site</code> 重新生成本页",
    },
    "en": {
        "htmlLang": "en",
        "docTitle": "FDE Skills Handbook · Portal",
        "brandSuffix": "Handbook",
        "gtaText": "GTM Site ↗",
        "gtaHref": "../../../../GTM/index.html",
        "langHref": "../",
        "langLabel": "中文",
        "searchPh": "Search {n} skills / tools / MCP pages…",
        "heroH1": "FDE Skills Handbook",
        "heroP": "One profile page per capability: what it does · when to use it (including anti-boundaries) · best practices · where it plugs into the fde-scope project. Three layers — skills (FDE four zones + cross-cutting), MCP server surfaces, built-in tools. Pick a scenario first, then open a page.",
        "statUnits": {"pages": "capability profiles", "installed": "installed", "installable": "installable", "zones": "zones", "scenarios": "scenario entries"},
        "secTaskT": "Start by Task",
        "secTaskD": "GTM scenario shortcuts: enter by task, not by catalog",
        "secPhaseT": "Browse by Phase",
        "secPhaseD": "FDE four zones + cross-cutting meta-skills + MCP servers + built-in tools",
        "secAllT": "All Capability Profiles",
        "secAllD": "searchable, filterable by status",
        "filterAll": "All",
        "nohit": "No matching skill",
        "itemsSuffix": "items",
        "badgeTxt": {"ok": "installed", "pkg": "installable", "dead": "removed"},
        "crumbHome": "Home",
        "langNote": "The profile body below is maintained in Chinese (single source of truth) — navigation, blurbs and metadata on this site are English.",
        "footer1": "FDE Skills Handbook · {total} profiles (✅ {installed} · 📦 {installable}) · est. 2026-08-27 · sourced from README + per-page Markdown",
        "footer2": "Consistency gate <code>make check-catalog</code> · local reconciliation <code>make check-local</code> · regenerate with <code>make build-site</code> after editing the catalog",
    },
}


# --------------------------------------------------------------------------- README 解析


def parse_readme() -> dict[str, list[tuple[str, str, str, str]]]:
    """分区标题 -> [(名称, 相对路径, 状态, 一句话)]，按 README 表格顺序；key 是目录 id。"""
    text = (CATALOG / "README.md").read_text(encoding="utf-8")
    sections: dict[str, list[tuple[str, str, str, str]]] = {}
    current: str | None = None
    row_re = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(✅|📦|⚰️)\s*\|\s*(.+?)\s*\|\s*$")
    head_re = re.compile(r"^##\s+(Zone [A-D]|横切|MCP · 服务器工具面|工具 · 内置)")
    head_key = {
        "Zone A": "zone-a-pre-engagement",
        "Zone B": "zone-b-build",
        "Zone C": "zone-c-operationalization",
        "Zone D": "zone-d-handoff",
        "横切": "cross-cutting",
        "MCP · 服务器工具面": "mcp",
        "工具 · 内置": "tools",
    }
    for line in text.splitlines():
        m = head_re.match(line)
        if m:
            current = head_key[m.group(1)]
            sections.setdefault(current, [])
            continue
        if current:
            rm = row_re.match(line)
            if rm:
                sections[current].append((rm.group(1), rm.group(2), rm.group(3), rm.group(4)))
    return sections


# --------------------------------------------------------------------------- 极简 Markdown 渲染

CODE_FENCE = re.compile(r"^```")


def render_inline(text: str, page_rel: str, page_set: set[str]) -> str:
    """行内文本 -> HTML：先整体转义，再做代码/加粗/链接变换（escape-then-transform）。"""
    parts = re.split(r"(`[^`]+`)", text)
    out: list[str] = []
    for part in parts:
        part = html.escape(part, quote=True)
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{part[1:-1]}</code>")
            continue
        part = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: _link(m, page_rel, page_set), part)
        out.append(part)
    return "".join(out)


def _link(m: re.Match, page_rel: str, page_set: set[str]) -> str:
    label, target = m.group(1), m.group(2)
    if target.startswith(("http://", "https://", "mailto:")):
        return f'<a href="{target}" target="_blank" rel="noopener">{label}</a>'
    base = posixpath.dirname(page_rel)
    resolved = posixpath.normpath(posixpath.join(base, target))
    if resolved.endswith(".md") and resolved[:-3] in page_set:
        return f'<a href="#/{resolved[:-3]}">{label}</a>'
    from_site = posixpath.relpath(resolved, "site")
    return f'<a href="{from_site}" target="_blank" rel="noopener">{label}</a>'


def render_markdown(md: str, page_rel: str, page_set: set[str]) -> str:
    """覆盖本库页面实际用到的 Markdown 子集，够用且无依赖。"""
    html: list[str] = []
    para: list[str] = []
    quote: list[str] = []
    table: list[str] = []
    ul: list[str] = []
    fence = False

    def flush_para():
        nonlocal para
        if para:
            body = "<br>".join(render_inline(ln, page_rel, page_set) for ln in para)
            html.append(f"<p>{body}</p>")
            para = []

    def flush_quote():
        nonlocal quote
        if quote:
            body = "<br>".join(render_inline(ln, page_rel, page_set) for ln in quote)
            html.append(f'<div class="page-meta">{body}</div>')
            quote = []

    def flush_table():
        nonlocal table
        if not table:
            return
        rows = [r for r in table if not re.match(r"^\|[\s:|-]+\|$", r)]
        parsed = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
        if parsed:
            head, *body = parsed
            thead = "".join(f"<th>{render_inline(c, page_rel, page_set)}</th>" for c in head)
            trs = "".join(
                "<tr>" + "".join(f"<td>{render_inline(c, page_rel, page_set)}</td>" for c in r) + "</tr>"
                for r in body
            )
            html.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{trs}</tbody></table>")
        table = []

    def flush_ul():
        nonlocal ul
        if ul:
            html.append("<ul>" + "".join(f"<li>{i}</li>" for i in ul) + "</ul>")
            ul = []

    def flush_all():
        flush_para()
        flush_quote()
        flush_table()
        flush_ul()

    def flush_text():
        flush_para()
        flush_ul()

    for raw in md.splitlines():
        line = raw.rstrip()
        if fence:
            html.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            if CODE_FENCE.match(line):
                html.append("</code></pre>")
                fence = False
            continue
        if CODE_FENCE.match(line):
            flush_all()
            html.append("<pre><code>")
            fence = True
            continue
        if line.startswith("|"):
            flush_text()
            table.append(line)
            continue
        flush_table()
        if line.startswith("> "):
            flush_text()
            quote.append(line[2:])
            continue
        flush_quote()
        if not line:
            flush_text()
            continue
        if line.startswith("### "):
            flush_text()
            html.append(f"<h3>{render_inline(line[4:], page_rel, page_set)}</h3>")
            continue
        if line.startswith("## "):
            flush_text()
            html.append(f"<h2>{render_inline(line[3:], page_rel, page_set)}</h2>")
            continue
        if line.startswith("# "):
            flush_text()
            html.append(f"<h1>{render_inline(line[2:], page_rel, page_set)}</h1>")
            continue
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            flush_para()
            ul.append(render_inline(m.group(2), page_rel, page_set))
            continue
        m = re.match(r"^\d+\.\s+(.*)$", line)
        if m:
            flush_para()
            ul.append(render_inline(m.group(1), page_rel, page_set))
            continue
        para.append(line)
    flush_all()
    return "\n".join(html)


# --------------------------------------------------------------------------- 组装数据


def build_data(lang: str) -> dict:
    readme = parse_readme()
    zone_rows = {zone_id: readme.get(zone_id, []) for zone_id, *_ in ZONES}
    page_set = {path[:-3] for rows in zone_rows.values() for _, path, _, _ in rows}

    zones = []
    all_pages: list[dict] = []
    for zone_id, label, tag, accent in ZONES:
        if lang == "en":
            label, tag = ZONES_EN[zone_id]
        skills = []
        for name, rel, status, blurb in zone_rows[zone_id]:
            page_file = CATALOG / rel
            md = (
                page_file.read_text(encoding="utf-8")
                if page_file.exists()
                else f"# {name}\n\n页面缺失：{rel}"
            )
            page_rel = posixpath.splitext(rel)[0]
            if lang == "en":
                if page_rel not in BLURB_EN:
                    raise SystemExit(f"BLURB_EN 缺少英文一句话：{page_rel}")
                blurb = BLURB_EN[page_rel]
            # name/blurb 转录自 README（含第三方 skill 简介），route 进 href 与
            # JS 模板串：统一在此处转义，portal JS 直接注入，不再有第二层转义。
            skills.append(
                {
                    "name": html.escape(name),
                    "route": html.escape(page_rel),
                    "status": status,
                    "blurb": html.escape(blurb),
                }
            )
            all_pages.append(
                {
                    "route": html.escape(page_rel),
                    "zone": label,
                    "zoneId": zone_id,
                    "status": status,
                    "html": render_markdown(md, page_rel, page_set),
                }
            )
        zones.append({"id": zone_id, "label": label, "tag": tag, "accent": accent, "skills": skills})

    scenarios = []
    for title, desc, items in SCENARIOS:
        missing = [rel for _, rel in items if rel[:-3] not in page_set]
        if missing:
            raise SystemExit(f"场景「{title}」引用了不存在的页面：{missing}")
        if lang == "en":
            title, desc = SCENARIOS_EN[title]
        scenarios.append(
            {
                "title": title,
                "desc": desc,
                "items": [{"name": n, "route": rel[:-3]} for n, rel in items],
            }
        )

    installed = sum(1 for p in all_pages if p["status"] == "✅")
    installable = sum(1 for p in all_pages if p["status"] == "📦")
    return {
        "lang": lang,
        "l10n": L10N[lang],
        "zones": zones,
        "scenarios": scenarios,
        "pages": all_pages,
        "stats": {
            "total": len(all_pages),
            "installed": installed,
            "installable": installable,
            "zoneCount": len(zones),
            "scenarioCount": len(scenarios),
        },
    }


# --------------------------------------------------------------------------- HTML 模板

CSS = """
:root{--bg:oklch(0.973 0.003 255);--card:oklch(1 0 0);--ink:oklch(0.225 0.014 255);--muted:oklch(0.47 0.016 255);
--line:oklch(0.9 0.006 255);--border-strong:oklch(0.8 0.01 255);
--accent:oklch(0.5 0.095 235);--accent-2:oklch(0.44 0.095 235);--accent-ink:oklch(0.99 0.002 255);
--ok:oklch(0.51 0.12 152);--warn:oklch(0.53 0.11 75);--bad:oklch(0.55 0.17 25);--radius:12px;--mono:ui-monospace,SFMono-Regular,Menlo,monospace;
color-scheme:light}
*{box-sizing:border-box;margin:0;padding:0}
html,body{overflow-x:clip}
body{font-family:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
background:var(--bg);color:var(--ink);line-height:1.65}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.nav{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:18px;padding:12px 28px;
background:color-mix(in oklab,var(--card) 88%,transparent);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.nav .brand{font-weight:700;font-size:16px;color:var(--ink);cursor:pointer;white-space:nowrap;letter-spacing:-.01em}
.nav .brand span{color:var(--accent)}
.nav .gta{font:600 11px/1 var(--mono);letter-spacing:.1em;color:var(--accent);background:color-mix(in oklab,var(--accent) 9%,transparent);
padding:5px 10px;border-radius:999px;white-space:nowrap;text-decoration:none}
.nav .gta:hover{background:color-mix(in oklab,var(--accent) 16%,transparent);text-decoration:none}
.nav .zlinks{display:flex;gap:14px;overflow-x:auto}
.nav .zlinks a{color:var(--muted);font-size:13px;white-space:nowrap}
.nav input{margin-left:auto;width:230px;padding:7px 12px;border:1px solid var(--line);border-radius:99px;
font-size:13px;outline:none;background:var(--card);font-family:inherit}
.nav input:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in oklab,var(--accent) 12%,transparent)}
.hero{background:linear-gradient(160deg,oklch(0.35 0.07 255) 0%,oklch(0.5 0.095 235) 62%,oklch(0.44 0.095 235) 100%);
color:#fff;padding:60px 28px 52px;text-align:center}
.hero h1{font-size:34px;letter-spacing:-.015em;line-height:1.15;overflow-wrap:anywhere}
.hero p{margin:14px auto 0;max-width:760px;color:rgba(255,255,255,.84);font-size:15px}
.hero .stats{display:flex;justify-content:center;gap:14px;margin-top:28px;flex-wrap:wrap}
.stat{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.3);border-radius:99px;
padding:7px 18px;font-size:13px;color:#fff}
.stat b{font-size:16px;margin-right:4px}
.wrap{max-width:1120px;margin:0 auto;padding:36px 24px 72px}
.section-h{display:flex;align-items:baseline;gap:12px;margin:8px 0 18px}
.section-h h2{font-size:21px;letter-spacing:-.01em}
.section-h p{color:var(--muted);font-size:13px}
.scen-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px}
.scen{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;
transition:box-shadow .15s,border-color .15s}
.scen:hover{box-shadow:0 10px 26px -14px rgba(15,30,60,.3);border-color:var(--border-strong)}
.scen h3{font-size:15px;margin-bottom:4px}
.scen .d{color:var(--muted);font-size:12.5px;margin-bottom:12px}
.scen .links{display:flex;flex-wrap:wrap;gap:8px}
.scen .links a{font-size:12.5px;background:color-mix(in oklab,var(--accent) 8%,var(--card));border:1px solid color-mix(in oklab,var(--accent) 20%,var(--card));color:var(--accent-2);
padding:4px 11px;border-radius:99px;text-decoration:none}
.scen .links a:hover{background:color-mix(in oklab,var(--accent) 16%,var(--card));text-decoration:none}
.zone-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px;margin-top:6px}
.zone{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;
display:flex;flex-direction:column}
.zone .zh{padding:16px 20px 12px;border-top:3px solid var(--accent)}
.zone .zh h3{font-size:15.5px}
.zone .zh p{color:var(--muted);font-size:12.5px;margin-top:2px}
.zone .zs{padding:6px 14px 16px;display:flex;flex-wrap:wrap;gap:7px}
.zone .zs a{font-size:12.5px;padding:4px 10px;border-radius:8px;background:color-mix(in oklab,var(--ink) 4%,var(--card));color:var(--ink);
border:1px solid var(--line);text-decoration:none}
.zone .zs a:hover{text-decoration:none;border-color:var(--accent);color:var(--accent)}
.zone .zs a .st{font-size:11px;margin-right:3px}
.toolbar{display:flex;gap:10px;align-items:center;margin:4px 0 16px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:var(--card);border-radius:99px;padding:5px 14px;font-size:12.5px;
cursor:pointer;color:var(--muted);font-family:inherit}
.chip:hover{border-color:var(--border-strong);color:var(--ink)}
.chip.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.all-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.sk{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px;display:block;color:var(--ink);
transition:box-shadow .15s,border-color .15s}
.sk:hover{box-shadow:0 8px 22px -14px rgba(15,30,60,.3);border-color:var(--border-strong);text-decoration:none}
.sk .t{display:flex;align-items:center;gap:8px;font-weight:650;font-size:14px}
.sk .b{color:var(--muted);font-size:12.5px;margin-top:4px}
.sk .z{font-size:11px;color:var(--muted);margin-top:6px}
.badge{font-size:11px;border-radius:99px;padding:2px 9px;font-weight:600}
.badge.ok{background:color-mix(in oklab,var(--ok) 14%,var(--card));color:oklch(0.35 0.1 152)}
.badge.pkg{background:color-mix(in oklab,var(--warn) 14%,var(--card));color:oklch(0.38 0.09 75)}
.badge.dead{background:color-mix(in oklab,var(--muted) 10%,var(--card));color:var(--muted)}
.crumb{font-size:13px;color:var(--muted);margin-bottom:6px}
.crumb a{color:var(--muted)}
.article{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
padding:36px 44px;max-width:900px;margin:0 auto}
.article h1{font-size:24px;margin:4px 0 14px;letter-spacing:-.01em;overflow-wrap:anywhere}
.article h2{font-size:17px;margin:26px 0 10px;padding-left:10px;border-left:3px solid var(--accent)}
.article h3{font-size:15px;margin:18px 0 8px}
.article p{margin:8px 0}
.article ul{margin:8px 0 8px 22px}
.article li{margin:4px 0}
.article code{font-family:var(--mono);font-size:.86em;background:color-mix(in oklab,var(--ink) 4%,var(--card));border:1px solid var(--line);
border-radius:5px;padding:1px 5px;word-break:break-all}
.article pre{background:oklch(0.22 0.015 255);color:oklch(0.93 0.006 255);border-radius:10px;padding:14px 16px;overflow-x:auto;margin:10px 0}
.article pre code{background:none;border:none;color:inherit;padding:0;font-size:12.5px;line-height:1.55}
.article table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}
.article th,.article td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
.article th{background:color-mix(in oklab,var(--ink) 3%,var(--card))}
.article .page-meta{background:color-mix(in oklab,var(--accent) 6%,var(--card));border:1px solid color-mix(in oklab,var(--accent) 20%,var(--card));border-left:3px solid var(--accent);
border-radius:10px;padding:12px 16px;margin:6px 0 16px;font-size:13px;color:var(--ink)}
.pager{display:flex;justify-content:space-between;gap:16px;max-width:900px;margin:14px auto 0}
.pager a{font-size:13px;color:var(--muted);border:1px solid var(--line);background:var(--card);
border-radius:10px;padding:8px 14px;max-width:46%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-decoration:none}
.pager a:hover{color:var(--accent);text-decoration:none;border-color:var(--accent)}
.empty{display:none;text-align:center;color:var(--muted);padding:40px 0}
footer{border-top:1px solid var(--line);margin-top:56px;padding:26px 28px 40px;color:var(--muted);
font-size:12.5px;text-align:center}
footer code{font-family:var(--mono);background:color-mix(in oklab,var(--ink) 4%,var(--card));border-radius:5px;padding:1px 5px}
.nav .lang{font:600 12px/1 var(--mono);letter-spacing:.06em;color:var(--muted);border:1px solid var(--line);
border-radius:99px;padding:6px 12px;white-space:nowrap;text-decoration:none}
.nav .lang:hover{color:var(--accent);border-color:var(--accent);text-decoration:none}
.lang-note{background:color-mix(in oklab,var(--warn) 8%,var(--card));border:1px solid color-mix(in oklab,var(--warn) 25%,var(--card));
border-left:3px solid var(--warn);border-radius:10px;padding:10px 14px;margin:0 auto 10px;max-width:900px;font-size:13px;color:var(--ink)}
@media(max-width:720px){.article{padding:22px 18px}.nav .zlinks{display:none}.nav input{width:150px}.nav{gap:10px}}
"""

JS = r"""
const DATA = JSON.parse(document.getElementById('catalog-data').textContent);
const L = DATA.l10n;
const PAGES = {}; DATA.pages.forEach((p,i)=>{PAGES[p.route]=i;});
const app = document.getElementById('app');

function badge(st){
  const cls = st==='✅' ? 'ok' : (st==='📦' ? 'pkg' : 'dead');
  const txt = st==='✅' ? L.badgeTxt.ok : (st==='📦' ? L.badgeTxt.pkg : L.badgeTxt.dead);
  return `<span class="badge ${cls}">${st} ${txt}</span>`;
}
function nav(){
  return `<nav class="nav">
    <div class="brand" onclick="location.hash='#/'">FDE Skills <span>${L.brandSuffix}</span></div>
    <a class="gta" href="${L.gtaHref}">${L.gtaText}</a>
    <a class="lang" href="${L.langHref}" hreflang="${DATA.lang==='zh'?'en':'zh-CN'}">${L.langLabel}</a>
    <div class="zlinks">${DATA.zones.map(z=>`<a href="#/" onclick="goZone('${z.id}')">${z.label.split('·')[0].trim()}</a>`).join('')}</div>
    <input id="q" type="search" placeholder="${L.searchPh.replace('{n}',DATA.stats.total)}" oninput="onSearch(this.value)">
  </nav>`;
}
function goZone(id){ location.hash='#/'; setTimeout(()=>{const el=document.getElementById('zone-'+id); if(el) el.scrollIntoView({behavior:'smooth'});},30); }

function home(){
  const s = DATA.stats, u = L.statUnits;
  return `${nav()}
  <header class="hero">
    <h1>${L.heroH1}</h1>
    <p>${L.heroP}</p>
    <div class="stats">
      <span class="stat"><b>${s.total}</b> ${u.pages}</span>
      <span class="stat"><b>${s.installed}</b> ${u.installed}</span>
      <span class="stat"><b>${s.installable}</b> ${u.installable}</span>
      <span class="stat"><b>${s.zoneCount}</b> ${u.zones}</span>
      <span class="stat"><b>${s.scenarioCount}</b> ${u.scenarios}</span>
    </div>
  </header>
  <div class="wrap">
    <div id="scen-sec">
      <div class="section-h"><h2>${L.secTaskT}</h2><p>${L.secTaskD}</p></div>
      <div class="scen-grid">
        ${DATA.scenarios.map(sc=>`<div class="scen"><h3>${sc.title}</h3><div class="d">${sc.desc}</div>
          <div class="links">${sc.items.map(i=>`<a href="#/${i.route}">${i.name}</a>`).join('')}</div></div>`).join('')}
      </div>
    </div>
    <div id="zones-sec" style="margin-top:40px">
      <div class="section-h"><h2>${L.secPhaseT}</h2><p>${L.secPhaseD}</p></div>
      <div class="zone-grid">
        ${DATA.zones.map(z=>`<div class="zone" id="zone-${z.id}">
          <div class="zh" style="--accent:${z.accent}"><h3>${z.label}</h3><p>${z.tag} · ${z.skills.length} ${L.itemsSuffix}</p></div>
          <div class="zs">${z.skills.map(k=>`<a href="#/${k.route}"><span class="st">${k.status}</span>${k.name}</a>`).join('')}</div>
        </div>`).join('')}
      </div>
    </div>
    <div id="all-sec" style="margin-top:40px">
      <div class="section-h"><h2>${L.secAllT}</h2><p>${L.secAllD}</p></div>
      <div class="toolbar">
        <button class="chip on" data-f="all" onclick="setFilter(this)">${L.filterAll}</button>
        <button class="chip" data-f="✅" onclick="setFilter(this)">✅ ${L.badgeTxt.ok}</button>
        <button class="chip" data-f="📦" onclick="setFilter(this)">📦 ${L.badgeTxt.pkg}</button>
        <span id="hit" style="color:var(--muted);font-size:12.5px"></span>
      </div>
      <div class="all-grid" id="all-grid"></div>
      <div class="empty" id="nohit">${L.nohit}</div>
    </div>
  </div>
  ${footer()}`;
}

let statusFilter='all';
function setFilter(btn){
  document.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  btn.classList.add('on'); statusFilter=btn.dataset.f; renderAll();
}
function renderAll(){
  const q=(document.getElementById('q')?.value||'').toLowerCase();
  const grid=document.getElementById('all-grid'); if(!grid) return;
  const items=[];
  DATA.zones.forEach(z=>z.skills.forEach(k=>{
    if(statusFilter!=='all' && k.status!==statusFilter) return;
    if(q && !(k.name+' '+k.blurb+' '+z.label).toLowerCase().includes(q)) return;
    items.push({k,z});
  }));
  grid.innerHTML=items.map(({k,z})=>`<a class="sk" href="#/${k.route}">
    <div class="t">${k.name} ${badge(k.status)}</div><div class="b">${k.blurb}</div>
    <div class="z">${z.label}</div></a>`).join('');
  document.getElementById('nohit').style.display=items.length?'none':'block';
  const hit=document.getElementById('hit'); if(hit) hit.textContent=`${items.length} ${L.itemsSuffix}`;
}
function onSearch(v){
  const hasQ=!!v;
  ['scen-sec','zones-sec','hero'].forEach(id=>{const el=document.getElementById(id)||document.querySelector('.hero'); if(el) el.style.display=(hasQ&&id!=='all-sec')?'none':'';});
  const allSec=document.getElementById('all-sec');
  if(hasQ && allSec) allSec.scrollIntoView({behavior:'smooth'});
  renderAll();
}

function page(route){
  const i=PAGES[route]; if(i===undefined){location.hash='#/';return '';}
  const p=DATA.pages[i];
  const prev=DATA.pages[i-1], next=DATA.pages[i+1];
  const note = L.langNote ? `<div class="lang-note">${L.langNote}</div>` : '';
  return `${nav()}
  <div class="wrap">
    <div class="crumb"><a href="#/">${L.crumbHome}</a> › ${p.zone} › <b style="color:var(--ink)">${route.split('/').pop()}</b></div>
    ${note}
    <article class="article">${p.html}</article>
    <div class="pager">
      ${prev?`<a href="#/${prev.route}">← ${prev.route.split('/').pop()}</a>`:'<span></span>'}
      ${next?`<a href="#/${next.route}">${next.route.split('/').pop()} →</a>`:'<span></span>'}
    </div>
  </div>
  ${footer()}`;
}

function footer(){
  const s=DATA.stats;
  const f1=L.footer1
    .replace('{total}',s.total).replace('{installed}',s.installed).replace('{installable}',s.installable);
  return `<footer>
    <div>${f1}</div>
    <div style="margin-top:6px">${L.footer2}</div>
  </footer>`;
}

function render(){
  const h=location.hash.replace(/^#\/?/,'');
  app.innerHTML = h ? page(h) : home();
  renderAll();
  window.scrollTo(0,0);
}
window.addEventListener('hashchange',render);
render();
"""


def build_html(data: dict) -> str:
    # <script id="catalog-data"> 的 JSON 块里不能出现任何裸 `<`：否则 `</script>`
    # 提前闭合、`<!--` + `<script` 吞掉整页。`\u003c` 是合法 JSON 转义，parse 后还原。
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    l10n = data["l10n"]
    return f"""<!DOCTYPE html>
<html lang="{l10n["htmlLang"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{l10n["docTitle"]}</title>
<style>{CSS}</style>
</head>
<body>
<div id="app"></div>
<script id="catalog-data" type="application/json">{payload}</script>
<script>{JS}</script>
</body>
</html>
"""


def main() -> None:
    outputs = (("zh", OUT), ("en", SITE / "en" / "index.html"))
    for lang, out in outputs:
        data = build_data(lang)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_html(data), encoding="utf-8")
        s = data["stats"]
        print(
            f"OK {out.relative_to(ROOT)} ｜ {s['total']} 页（✅ {s['installed']} / 📦 {s['installable']}）｜ {out.stat().st_size // 1024} KB"
        )


if __name__ == "__main__":
    main()

# FDE Skills 手册库

> 本地维护的 skill 档案库：**每个 skill 一页 Markdown**，记录基本信息、触发时机、最佳实践、在 fde-scope 项目中的应用位点。
> 建档日期：2026-08-27 · 2026-08-31 行业调研扩编（+21 📦）· **共 122 页**：Zone A 14 / Zone B 41 / Zone C 22 / Zone D 12 / 横切 21 / MCP 10 / 工具 2
> 一致性门禁：`make check-catalog`（当前全绿）
> **门户主页**：`site/index.html` —— GTM 风格单文件导航（场景入口 + 全部页面跳转 + 搜索），双击即开；改完本库跑 `make build-site` 重新生成

## 目录结构

```
docs/skills-catalog/
├── README.md                        # 本文件：索引 + 维护规约
├── zone-a-pre-engagement/           # 调研、摸底、干系人、成功标准
├── zone-b-build/                    # 数据接入、语料、原型、验证、部署、评估
├── zone-c-operationalization/       # SLO、runbook、监控漂移、变更、飞轮重训
├── zone-d-handoff/                  # 文档产出、培训、移交演示
├── cross-cutting/                   # skill 工程、评审、计划、架构、调度
├── mcp/                             # MCP 服务器工具面（每个已连接 server 一页）
├── tools/                           # 内置工具总览与使用纪律
└── site/index.html                  # 门户主页（make build-site 生成）

校验脚本（不在本目录，但属于本库的维护面）：
scripts/check_skills_catalog.py      # 页数/六段/索引/状态/断链 + （--local）与本机安装对账
```

## 页面模板（每页固定六段）

1. **头部元信息**：状态（✅ 已安装 / 📦 可安装）、类型、FDE 阶段位点、来源与安装命令、详情链接
2. **能做什么**：一段话能力边界
3. **何时使用**：触发场景列表（写清反向边界：什么时候*不*用）
4. **新人上手**：触发说法 → 第一步 → 常见坑（新人 30 秒定位到"怎么用起来"）
5. **最佳实践**：dos & don'ts，成本/风险注意
6. **项目应用位点 + 相关 skills**：映射到 fde-scope 的哪个阶段/gate/模块

## Zone A · Pre-engagement

| Skill | 状态 | 一句话 |
|---|---|---|
| [firecrawl-search](zone-a-pre-engagement/firecrawl-search.md) | ✅ | 带全文抽取的实时联网搜索 |
| [firecrawl-scrape](zone-a-pre-engagement/firecrawl-scrape.md) | ✅ | 任意 URL → 干净 Markdown |
| [firecrawl-crawl](zone-a-pre-engagement/firecrawl-crawl.md) | ✅ | 整站/文档分区批量抽取 |
| [firecrawl-parse](zone-a-pre-engagement/firecrawl-parse.md) | ✅ | 本地文件（PDF/DOCX/表格）→ Markdown |
| [zread](zone-a-pre-engagement/zread.md) | ✅ | 陌生代码库一键生成 wiki |
| [qmind-knowledge](zone-a-pre-engagement/qmind-knowledge.md) | ✅ | 知识库检索/上传/编译 |
| [brainstorming](zone-a-pre-engagement/brainstorming.md) | ✅ | 创造性工作前的需求探索 |
| [architecture-communicator](zone-a-pre-engagement/architecture-communicator.md) | ✅ | 按受众讲架构 |
| [drawio](zone-a-pre-engagement/drawio.md) | ✅ | 可编辑交付图 |
| [pdf](zone-a-pre-engagement/pdf.md) | ✅ | PDF 解析/生成/表单 |
| [docx](zone-a-pre-engagement/docx.md) | ✅ | Word 解析/生成/处理 |
| [xlsx](zone-a-pre-engagement/xlsx.md) | ✅ | Excel 解析/生成/公式 |
| [grill-me](zone-a-pre-engagement/grill-me.md) | 📦 | 动手前把模糊需求盘问成规格（mattpocock/skills，1M 装机） |
| [crm-lookup](zone-a-pre-engagement/crm-lookup.md) | 📦 | HubSpot 官方 CLI 查客户/商机/关联（agent-cli-skills） |

## Zone B · Build

| Skill | 状态 | 一句话 |
|---|---|---|
| [read-file](zone-b-build/read-file.md) | ✅ | 任意数据文件画像 |
| [convert-file](zone-b-build/convert-file.md) | ✅ | 数据文件格式互转 |
| [attach-db](zone-b-build/attach-db.md) | ✅ | DuckDB 会话挂库 |
| [query](zone-b-build/query.md) | ✅ | DuckDB SQL/自然语言查询 |
| [spatial](zone-b-build/spatial.md) | ✅ | 地理空间数据分析 |
| [mqtt-development](zone-b-build/mqtt-development.md) | 📦 | MQTT 开发模式参考 |
| [bailian-train-deploy](zone-b-build/bailian-train-deploy.md) | ✅ | 百炼 数据→训练→部署 闭环 |
| [huggingface-datasets](zone-b-build/huggingface-datasets.md) | ✅ | HF 数据集 Viewer API |
| [train-sentence-transformers](zone-b-build/train-sentence-transformers.md) | ✅ | 嵌入/重排模型训练 |
| [rag-agent-builder](zone-b-build/rag-agent-builder.md) | 📦 | RAG 智能体搭建 |
| [frontend-design](zone-b-build/frontend-design.md) | ✅ | 高设计质量前端 |
| [ui-designer](zone-b-build/ui-designer.md) | ✅ | UI 设计系统+原型 |
| [shadcn](zone-b-build/shadcn.md) | ✅ | shadcn/ui 组件体系 |
| [vercel-deploy](zone-b-build/vercel-deploy.md) | ✅ | 快速上线 demo |
| [cloudflare](zone-b-build/cloudflare.md) | ✅ | Workers/Pages/KV 平台 |
| [kubernetes-specialist](zone-b-build/kubernetes-specialist.md) | 📦 | K8s 现场交付/排障 |
| [docker-build-deploy](zone-b-build/docker-build-deploy.md) | 📦 | Docker 生产化 |
| [alibabacloud-workbench-cli](zone-b-build/alibabacloud-workbench-cli.md) | ✅ | 无公网 IP 的 ECS 运维 |
| [alibabacloud-core-suite](zone-b-build/alibabacloud-core-suite.md) | ✅ | 阿里云 OpenAPI/CLI 9 件套（跨账号查询/SDK 生成/TF 导入） |
| [alibabacloud-spec-ops-suite](zone-b-build/alibabacloud-spec-ops-suite.md) | ✅ | 阿里云 IaC 流水线 6 件套（plan→codegen→validate→apply） |
| [vllm-deploy-docker](zone-b-build/vllm-deploy-docker.md) | 📦 | vLLM 官方容器部署 |
| [vllm-ascend](zone-b-build/vllm-ascend.md) | 📦 | 昇腾 vLLM 适配（registry 真名 `vllm-ascend-deploy`） |
| [huggingface-local-models](zone-b-build/huggingface-local-models.md) | ✅ | llama.cpp+GGUF 本地推理（air-gap/内网/Mac 演示） |
| [huggingface-best](zone-b-build/huggingface-best.md) | ✅ | 开源模型选型决策（与 bailian-model-recommend 互补） |
| [huggingface-community-evals](zone-b-build/huggingface-community-evals.md) | ✅ | inspect-ai/lighteval 本地评估 |
| [phoenix-evals](zone-b-build/phoenix-evals.md) | 📦 | Arize Phoenix 评估器开发（规则 + LLM judge） |
| [evaluating-llms-harness](zone-b-build/evaluating-llms-harness.md) | 📦 | lm-evaluation-harness 封装 |
| [huggingface-spaces](zone-b-build/huggingface-spaces.md) | ✅ | HF Spaces demo 托管（Gradio/Docker/ZeroGPU） |
| [postman](zone-b-build/postman.md) | ✅ | Collection/Mock/agent-ready API 生命周期（3 skill） |
| [bigquery-basics](zone-b-build/bigquery-basics.md) | 📦 | Google 官方 BigQuery 基础（`bq` CLI + SQL） |
| [using-dbt-for-analytics-engineering](zone-b-build/using-dbt-for-analytics-engineering.md) | 📦 | dbt 官方分析工程工作流（模型/测试/breaking change 流程） |
| [airflow](zone-b-build/airflow.md) | 📦 | Astronomer 官方 Airflow DAG 编排（`af` CLI） |
| [qdrant-clients-sdk](zone-b-build/qdrant-clients-sdk.md) | 📦 | Qdrant 官方向量库六语言 SDK 接入 |
| [langgraph-persistence](zone-b-build/langgraph-persistence.md) | 📦 | LangGraph 官方 checkpoint 持久化（客户栈适配，与 AgentScope 底座互补） |
| [building-pydantic-ai-agents](zone-b-build/building-pydantic-ai-agents.md) | 📦 | Pydantic AI 官方 agent 构建（`@agent.tool`/TestModel，pydantic v2 亲缘） |
| [mlflow-agent-evaluation](zone-b-build/mlflow-agent-evaluation.md) | 📦 | MLflow 官方 LLM 评估/tracing（registry 真名 `agent-evaluation`） |
| [wandb-primary](zone-b-build/wandb-primary.md) | 📦 | W&B 官方实验追踪主入口（wandb/skills） |
| [playwright-cli](zone-b-build/playwright-cli.md) | 📦 | 微软官方 Playwright 测试执行 CLI（137K 装机；调试向让位 chrome-devtools） |
| [prompt-engineering-patterns](zone-b-build/prompt-engineering-patterns.md) | 📦 | 提示工程模式库（CoT/结构化输出/路由/guardrails） |
| [openapi-spec-generation](zone-b-build/openapi-spec-generation.md) | 📦 | OpenAPI 3.1 规范生成与 Spectral/Redocly 校验 |
| [modbus-debug](zone-b-build/modbus-debug.md) | 📦 | Modbus RTU/TCP 寄存器级产线联调（低装机社区件，装前过门禁） |

## Zone C · Operationalization

| Skill | 状态 | 一句话 |
|---|---|---|
| [starops](zone-c-operationalization/starops.md) | ✅ | 阿里云 AIOps 诊断 |
| [investigate](zone-c-operationalization/investigate.md) | ✅ | 根因导向的系统排查 |
| [systematic-debugging](zone-c-operationalization/systematic-debugging.md) | ✅ | 调试方法论（先定位后修） |
| [troubleshooting](zone-c-operationalization/troubleshooting.md) | ✅ | 浏览器连接/目标问题 |
| [chrome-devtools](zone-c-operationalization/chrome-devtools.md) | ✅ | DevTools 调试与自动化 |
| [sentry-mcp](zone-c-operationalization/sentry-mcp.md) | ✅ | Sentry 错误/性能追踪 |
| [datadog](zone-c-operationalization/datadog.md) | ✅ | Datadog 官方 MCP 可观测性（ddsetup/ddconfig/ddtoolsets） |
| [sre-runbooks](zone-c-operationalization/sre-runbooks.md) | 📦 | SRE runbook 模板（registry 真名 `knowledge-work-plugins@runbook`） |
| [incident-response](zone-c-operationalization/incident-response.md) | 📦 | Anthropic 官方事件响应 |
| [gke-observability](zone-c-operationalization/gke-observability.md) | 📦 | GKE/K8s 可观测性 |
| [firecrawl-monitor](zone-c-operationalization/firecrawl-monitor.md) | ✅ | 网页变更监测告警 |
| [deploy-checklist](zone-c-operationalization/deploy-checklist.md) | 📦 | 上线前核验清单（registry 真名 `knowledge-work-plugins@deploy-checklist`，已源码取证） |
| [huggingface-llm-trainer](zone-c-operationalization/huggingface-llm-trainer.md) | ✅ | HF Jobs 上 SFT/DPO/GRPO |
| [huggingface-vision-trainer](zone-c-operationalization/huggingface-vision-trainer.md) | ✅ | 检测/分类/分割训练 |
| [trl-training](zone-c-operationalization/trl-training.md) | ✅ | TRL CLI 本地训练 |
| [web-perf](zone-c-operationalization/web-perf.md) | ✅ | Core Web Vitals 分析 |
| [debug-optimize-lcp](zone-c-operationalization/debug-optimize-lcp.md) | ✅ | LCP 专项优化 |
| [memory-leak-debugging](zone-c-operationalization/memory-leak-debugging.md) | ✅ | JS/Node 内存泄漏 |
| [grafana-dashboarding](zone-c-operationalization/grafana-dashboarding.md) | 📦 | Grafana 官方看板即代码（registry 真名 `dashboarding`，自建栈交付） |
| [llm-evaluation](zone-c-operationalization/llm-evaluation.md) | 📦 | LLM 评估方法论（指标选型/judge/一致性检验） |
| [gdpr-data-handling](zone-c-operationalization/gdpr-data-handling.md) | 📦 | GDPR 数据处理合规（Art.6/9/17、DSAR 一个月时限） |
| [terraform-style-guide](zone-c-operationalization/terraform-style-guide.md) | 📦 | HashiCorp 官方 Terraform 风格指南（`for_each`>count/state 禁入 git） |

## Zone D · Handoff

| Skill | 状态 | 一句话 |
|---|---|---|
| [document-generate](zone-d-handoff/document-generate.md) | ✅ | 从零补缺失文档 |
| [document-release](zone-d-handoff/document-release.md) | ✅ | 发布后文档同步 |
| [make-pdf](zone-d-handoff/make-pdf.md) | ✅ | Markdown → 出版级 PDF |
| [anthropic-documentation](zone-d-handoff/anthropic-documentation.md) | 📦 | 文档写作规范（registry 真名 `knowledge-work-plugins@documentation`） |
| [shifu](zone-d-handoff/shifu.md) | ✅ | 知识库→教学课程 |
| [remember](zone-d-handoff/remember.md) | ✅ | K8s 网络概念闪卡（范围仅限 K8s 网络） |
| [visual-deck-builder](zone-d-handoff/visual-deck-builder.md) | ✅ | 图像模型驱动 PPT |
| [pptx](zone-d-handoff/pptx.md) | ✅ | PowerPoint 操作 |
| [slidev](zone-d-handoff/slidev.md) | ✅ | 开发者幻灯（Markdown/Vue） |
| [notion-infographic](zone-d-handoff/notion-infographic.md) | ✅ | 文档→信息图系列 |
| [podcast](zone-d-handoff/podcast.md) | ✅ | 知识库→对话播客音频 |
| [lark-openapi-explorer](zone-d-handoff/lark-openapi-explorer.md) | 📦 | 飞书/Lark 官方 OpenAPI 探索（635.6K 装机，owner 为域名 `open.feishu.cn`） |

## 横切 · 元能力

| Skill | 状态 | 一句话 |
|---|---|---|
| [skill-discovery](cross-cutting/skill-discovery.md) | ✅ | `find-skills`：检索/安装/巡检 skill 生态（本库 📦 项的来源） |
| [create-skill](cross-cutting/create-skill.md) | ✅ | 新建 Qoder Agent Skill |
| [writing-skills](cross-cutting/writing-skills.md) | ✅ | skill 写作与部署校验 |
| [create-plugin](cross-cutting/create-plugin.md) | ✅ | skill/外部源 → 可分发插件 |
| [skill-criticagent](cross-cutting/skill-criticagent.md) | ✅ | 装前 skill 质检 |
| [mcp-criticagent](cross-cutting/mcp-criticagent.md) | ✅ | MCP server 评估 |
| [architecture-visualization-suite](cross-cutting/architecture-visualization-suite.md) | ✅ | 架构可视化 13 件套（路由+场景+基础） |
| [code-review](cross-cutting/code-review.md) | ✅ | CodeRabbit 代码评审 |
| [security-scan](cross-cutting/security-scan.md) | ✅ | 安全扫描（L2/L3） |
| [writing-plans](cross-cutting/writing-plans.md) | ✅ | 多步任务先写计划 |
| [executing-plans](cross-cutting/executing-plans.md) | ✅ | 按评审点执行计划 |
| [dispatching-parallel-agents](cross-cutting/dispatching-parallel-agents.md) | ✅ | 并行派发独立任务 |
| [using-git-worktrees](cross-cutting/using-git-worktrees.md) | ✅ | 隔离工作区 |
| [schedule](cross-cutting/schedule.md) | ✅ | 定时/周期任务 |
| [cloud-agents](cross-cutting/cloud-agents.md) | ✅ | 云端常驻 agent（**两个插件**：REST v1.1.0 + MCP v0.1.0） |
| [bailian-cli](cross-cutting/bailian-cli.md) | ✅ | 百炼 `bl` 家族 hub（9 skill 整包 `bl skill init`） |
| [using-superpowers-family](cross-cutting/using-superpowers-family.md) | ✅ | superpowers **14** 件套（方法论族，带 session-start hooks） |
| [gstack-suite](cross-cutting/gstack-suite.md) | ✅ | GStack 打包 **53** 件套 / 当前注册可调用 43（YC 开发全流程） |
| [knowledge-work-suite](cross-cutting/knowledge-work-suite.md) | 📦 | anthropics/knowledge-work-plugins：**230** skill / 497.5K 安装（**按需单装，勿整包**） |
| [anthropics-official-skills](cross-cutting/anthropics-official-skills.md) | 📦 | Anthropic 官方 skills 仓库档案（19 skill，skill-creator 367K 装机；**按需单装，勿整包**） |
| [trailofbits-security-suite](cross-cutting/trailofbits-security-suite.md) | 📦 | Trail of Bits 安全套件 43 插件（静态分析/差分审计/供应链，plugin marketplace 通道） |

## MCP · 服务器工具面

> 已连接 server 的工具面底账：每个 server 一页，记录工具清单、与 skill 的分工、调用坑。
> 工具数是快照（2026-08-31），以 `mcp_list` 实测为准；sentry / datadog / postman 按**插件维度**建在 Zone B/C，不重复立页。

| Server | 状态 | 一句话 |
|---|---|---|
| [overview](mcp/overview.md) | ✅ | 三层能力模型 + 9 个 server / 178 工具全景（新人从这里开始） |
| [cloud-agents-qca](mcp/cloud-agents-qca.md) | ✅ | 云端 agent 全生命周期 82 工具（环境/会话/文件/记忆/凭据/部署） |
| [chrome-devtools-mcp](mcp/chrome-devtools-mcp.md) | ✅ | 浏览器调试全栈 29 工具（性能/网络/AX 快照/堆快照） |
| [firecrawl-mcp](mcp/firecrawl-mcp.md) | ✅ | 网页数据 27 工具（搜索/抓取/爬站/监测/论文研究） |
| [browser-use](mcp/browser-use.md) | ✅ | 轻量浏览器交互 16 工具（无性能/仿真，重活让位 chrome-devtools） |
| [computer-use](mcp/computer-use.md) | ✅ | macOS 原生应用 AX 树自动化 10 工具 |
| [qmind-mcp](mcp/qmind-mcp.md) | ✅ | QMind 知识库检索/入库 7 工具 |
| [record-and-replay](mcp/record-and-replay.md) | ✅ | 录制真人操作流 → 生成 skill（3 工具） |
| [extension-market](mcp/extension-market.md) | ✅ | 官方插件市场搜索/安装（2 工具，先评估后装） |
| [cloudflare-docs-mcp](mcp/cloudflare-docs-mcp.md) | ✅ | CF 官方文档检索/迁移指南（2 工具，retrieval-first） |

## 工具 · 内置

> 不需要安装的执行层：总览建三层模型，纪律页是新人第一周必读的行为规约。

| Page | 状态 | 一句话 |
|---|---|---|
| [overview](tools/overview.md) | ✅ | 内置工具全景：文件/搜索/执行/Web/任务/委派/MCP 元工具/多会话 |
| [discipline](tools/discipline.md) | ✅ | 使用纪律：Read-before-Edit、专用工具优先、并行/后台、风险与验证 |

## 维护规约

0. **命名一致性**：📦 项的文件名与 registry 真实 skill 名对齐；若建档名与 registry 不同（如 `sre-runbooks`、`anthropic-documentation`、`vllm-ascend`），页内必须写明真实条目与更正原因，且**本 README 对应行也要标出 registry 真名**。已核对更正：`phoenix-evals`（原记 `phoenix-evals-new-metric`，registry 无该名）、`runbook`、`documentation`、`vllm-ascend-deploy`、`agent-evaluation`（mlflow-agent-evaluation，mlflow/skills 官方名不带前缀）、`dashboarding`（grafana-dashboarding，grafana/skills 同理）。
1. **新增 skill 时**：复制任一页面的六段模板建档，并在本 README 对应表加一行；📦 项安装后把头部的 📦 改成 ✅ 并补安装日期。
2. **季度巡检**：`npx skills check` / `npx skills update` 更新可安装项；已安装插件在 Quest Marketplace 检查版本。
3. **装前门禁**：所有 📦 项先用 `skill-criticagent`（skill）或 `mcp-criticagent`（MCP）评估，通过才安装，评估结论写进该页"最佳实践"段。
4. **删除/降级**：skill 卸载或失效时不删页，改状态为 `⚰️ 已移除` 并注明原因——保留决策记录。
5. **与 fde_scope/skills/ 的关系**：本目录是**外部生态**的手册；现场经验沉淀产物走 `.fde_scope/skills/` 文件库，二者互不覆盖。
6. **机器校验（改完必跑）**：`make check-catalog`（等价 `python3 scripts/check_skills_catalog.py`）。它校验六件事：README 头部页数 vs 磁盘实际、每页六段结构与「> 状态：」行齐全、README 索引与页面一一对应且不重复、页内状态与 README 行一致、catalog 内相对链接无断链。该校验已挂进 CI（`.github/workflows/ci.yml` 的 `skills-catalog` job），所以**断链或漏登记会让 PR 变红**，不靠人脑记。
7. **本地对账（季度巡检、装/卸后跑）**：`make check-local`。它扫 `~/.qoder/skills/` 与 `~/.qoder/plugins/cache/`，把页内状态与真实安装对齐：标 ✅ 但盘上找不到 = 硬错；标 📦 但已装 = 提醒回填 ✅ + 安装日期；页内声明的插件版本与实装版本不一致也会提醒。仅本地跑（CI 上无 `~/.qoder`）。“建档名 ≠ 安装名”与套件页已在脚本的 `IDENTITY` 表里登记（如 `sre-runbooks`→`runbook`、`skill-discovery`→`find-skills`、`vercel-deploy`→`deployments-cicd`）；MCP 区的 server 页对账到提供方插件（如 `firecrawl-mcp`→`plugin:firecrawl`）或标 `builtin`（客户端内置无磁盘痕迹）；总览/规约页标 `meta` 静默跳过。**新建页若 slug 与真实目录名不同，记得同步补一行**。（2026-08-27 首次对账 0 漂移；2026-08-31 复核：78 页 ✅ 已核实、6 页 builtin（create-skill / schedule 与 MCP 区 4 个客户端内置 server）、0 页漂移。）

## 审计排除清单（2026-08-27 全量盘点已核，非遗漏）

以下已安装能力经盘点**有意不建档**，下次盘点不必重新纠结；若 FDE 场景变化可推翻：

- **research-copilot 插件**（论文检索/学术写作/实验设计）：偏科研流程，Zone A 调研已由 firecrawl-\* / zread / qmind-knowledge 覆盖
- **design-taste 系**（hallmark / impeccable / gpt-taste / brandkit / ui-ux-pro-max / industrial-brutalist-ui 等 10+ 件）：与已建档的 frontend-design / ui-designer / shadcn 同类，按需安装即可，不重复建档
- **agent-browser**：与 chrome-devtools、gstack `browse`/`qa` 场景重叠
- **数据库开发参考系**（mongodb-agent-skills / redis-development / polardb-\* / supabase）：数据接入面已由 connectors + DuckDB（attach-db / query）覆盖，这些是通用开发参考
- **平台工作流件**（better-harness / qoder-canvas / create-command / qoder-find-extensions）：随客户端按需触发，非 FDE 交付技能。例外：record-and-replay 与 computer-use 的 **MCP 工具面**已在 MCP 区建档（[record-and-replay](mcp/record-and-replay.md) / [computer-use](mcp/computer-use.md)），其 skill 本身仍不建档
- **个人向**（weread-skills / yeye / fomo / podcast 生成器之外的娱乐类）：与交付无关

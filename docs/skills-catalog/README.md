# FDE Skills 手册库

> 本地维护的 skill 档案库：**每个 skill 一页 Markdown**，记录基本信息、触发时机、最佳实践、在 fde-scope 项目中的应用位点。
> 建档日期：2026-08-27 · **共 82 页**：Zone A 12 / Zone B 23 / Zone C 17 / Zone D 11 / 横切 19
> 一致性门禁：`make check-catalog`（当前全绿）

## 目录结构

```
docs/skills-catalog/
├── README.md                        # 本文件：索引 + 维护规约
├── zone-a-pre-engagement/           # 调研、摸底、干系人、成功标准
├── zone-b-build/                    # 数据接入、语料、原型、验证、部署、评估
├── zone-c-operationalization/       # SLO、runbook、监控漂移、变更、飞轮重训
├── zone-d-handoff/                  # 文档产出、培训、移交演示
└── cross-cutting/                   # skill 工程、评审、计划、架构、调度

校验脚本（不在本目录，但属于本库的维护面）：
scripts/check_skills_catalog.py      # 页数/五段/索引/状态/断链 + （--local）与本机安装对账
```

## 页面模板（每页固定五段）

1. **头部元信息**：状态（✅ 已安装 / 📦 可安装）、类型、FDE 阶段位点、来源与安装命令、详情链接
2. **能做什么**：一段话能力边界
3. **何时使用**：触发场景列表（写清反向边界：什么时候*不*用）
4. **最佳实践**：dos & don'ts，成本/风险注意
5. **项目应用位点 + 相关 skills**：映射到 fde-scope 的哪个阶段/gate/模块

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
| [vllm-deploy-docker](zone-b-build/vllm-deploy-docker.md) | 📦 | vLLM 官方容器部署 |
| [vllm-ascend](zone-b-build/vllm-ascend.md) | 📦 | 昇腾 vLLM 适配（registry 真名 `vllm-ascend-deploy`） |
| [huggingface-community-evals](zone-b-build/huggingface-community-evals.md) | ✅ | inspect-ai/lighteval 本地评估 |
| [phoenix-evals](zone-b-build/phoenix-evals.md) | 📦 | Arize Phoenix 评估器开发（规则 + LLM judge） |
| [evaluating-llms-harness](zone-b-build/evaluating-llms-harness.md) | 📦 | lm-evaluation-harness 封装 |

## Zone C · Operationalization

| Skill | 状态 | 一句话 |
|---|---|---|
| [starops](zone-c-operationalization/starops.md) | ✅ | 阿里云 AIOps 诊断 |
| [investigate](zone-c-operationalization/investigate.md) | ✅ | 根因导向的系统排查 |
| [systematic-debugging](zone-c-operationalization/systematic-debugging.md) | ✅ | 调试方法论（先定位后修） |
| [troubleshooting](zone-c-operationalization/troubleshooting.md) | ✅ | 浏览器连接/目标问题 |
| [chrome-devtools](zone-c-operationalization/chrome-devtools.md) | ✅ | DevTools 调试与自动化 |
| [sentry-mcp](zone-c-operationalization/sentry-mcp.md) | ✅ | Sentry 错误/性能追踪 |
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

## 维护规约

0. **命名一致性**：📦 项的文件名与 registry 真实 skill 名对齐；若建档名与 registry 不同（如 `sre-runbooks`、`anthropic-documentation`、`vllm-ascend`），页内必须写明真实条目与更正原因，且**本 README 对应行也要标出 registry 真名**。已核对更正：`phoenix-evals`（原记 `phoenix-evals-new-metric`，registry 无该名）、`runbook`、`documentation`、`vllm-ascend-deploy`。
1. **新增 skill 时**：复制任一页面的五段模板建档，并在本 README 对应表加一行；📦 项安装后把头部的 📦 改成 ✅ 并补安装日期。
2. **季度巡检**：`npx skills check` / `npx skills update` 更新可安装项；已安装插件在 Quest Marketplace 检查版本。
3. **装前门禁**：所有 📦 项先用 `skill-criticagent`（skill）或 `mcp-criticagent`（MCP）评估，通过才安装，评估结论写进该页"最佳实践"段。
4. **删除/降级**：skill 卸载或失效时不删页，改状态为 `⚰️ 已移除` 并注明原因——保留决策记录。
5. **与 fde_scope/skills/ 的关系**：本目录是**外部生态**的手册；现场经验沉淀产物走 `.fde_scope/skills/` 文件库，二者互不覆盖。
6. **机器校验（改完必跑）**：`make check-catalog`（等价 `python3 scripts/check_skills_catalog.py`）。它校验五件事：README 头部页数 vs 磁盘实际、每页五段结构与「> 状态：」行齐全、README 索引与页面一一对应且不重复、页内状态与 README 行一致、catalog 内相对链接无断链。该校验已挂进 CI（`.github/workflows/ci.yml` 的 `skills-catalog` job），所以**断链或漏登记会让 PR 变红**，不靠人脑记。
7. **本地对账（季度巡检、装/卸后跑）**：`make check-local`。它扫 `~/.qoder/skills/` 与 `~/.qoder/plugins/cache/`，把页内状态与真实安装对齐：标 ✅ 但盘上找不到 = 硬错；标 📦 但已装 = 提醒回填 ✅ + 安装日期；页内声明的插件版本与实装版本不一致也会提醒。仅本地跑（CI 上无 `~/.qoder`）。“建档名 ≠ 安装名”与套件页已在脚本的 `IDENTITY` 表里登记（如 `sre-runbooks`→`runbook`、`skill-discovery`→`find-skills`、`vercel-deploy`→`deployments-cicd`）；**新建页若 slug 与真实目录名不同，记得同步补一行**。（2026-08-27 首次对账：68 个 ✅ 页中 66 页已在盘上核实、两个是客户端内置无文件可核（create-skill / schedule）、 0 页漂移。）

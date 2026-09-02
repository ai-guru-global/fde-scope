# knowledge-work 套件（anthropics/knowledge-work-plugins）

> 状态：📦 可安装（**未装**，且建议**按需单装、不要整包装**）· 类型：套件档案 · FDE 位点：横切（Zone A 调研 ~ Zone D 交付）
> 来源：`anthropics/knowledge-work-plugins`（Anthropic 官方 org）· 上游：https://github.com/anthropics/knowledge-work-plugins
> 规模事实（skills.sh，2026-08-27 抓取）：**230 个 skill / 497.5K 总安装量** —— 不是"40+ 件套"，早期建档的估计严重偏低，已在本页与 README 更正
> 单装：`npx skills add anthropics/knowledge-work-plugins@<skill> --directory ~/.qoder/skills -y`
> 本 catalog 已有 4 个 📦 条目的**真实来源就是本仓库**：[deploy-checklist](../zone-c-operationalization/deploy-checklist.md) · [sre-runbooks](../zone-c-operationalization/sre-runbooks.md)（真名 `runbook`）· [incident-response](../zone-c-operationalization/incident-response.md) · [anthropic-documentation](../zone-d-handoff/anthropic-documentation.md)（真名 `documentation`）
> 仓库结构（2026-08-27 用 GitHub API 核对）：**18 个子插件包**——`bio-research` `cowork-plugin-management` `customer-support` `data` `design` `engineering` `enterprise-search` `finance` `human-resources` `legal` `marketing` `operations` `partner-built` `pdf-viewer` `product-management` `productivity` `sales` `small-business`；路径统一为 `<plugin>/skills/<name>/SKILL.md`。
> 安全事实：上游对每个条目跑**强制 Claude policy scan**（`.github/workflows/scan-plugins.yml`，按 (plugin, sha) 缓存判定，不通过则被 `revert-failed-bumps.yml` 自动剔除）——这是选它而不选个人作者的实质理由。

## 能做什么
把"知识工作"按岗位拆成 skill：工程（`system-design` `architecture` `tech-debt` `testing-strategy` `debug` `code-review` `deploy-checklist`）、数据（`explore-data` `analyze` `sql-queries` `write-query` `validate-data` `statistical-analysis` `create-viz` `data-visualization` `data-context-extractor`）、文档与研究（`documentation` `knowledge-synthesis` `research-synthesis` `synthesize-research` `search-strategy` `search` `source-management` `view-pdf` `write-spec`）、运维（`incident-response` `runbook` `ticket-triage` `status-report` `daily-briefing` `standup`）、产品与设计（`product-brainstorming` `design-critique` `design-system` `design-handoff` `ux-copy` `accessibility-review` `user-research`）、以及大量非技术岗位（法务 `review-contract` `legal-risk-assessment`、财务 `financial-statements` `variance-analysis` `reconciliation`、HR `interview-prep` `performance-review`、市场 `brand-*` `campaign-plan` `seo-audit`）。

与 GStack/superpowers 的差别：那两个管**工程流程纪律**，这一个管**岗位化产出物**——它的 skill 输出往往是文档、看板、分析报告，而不是代码路径。

## 何时使用（FDE 视角的高价值子集）
| 需求 | 装这个 | 热度 | 对应 FDE 位点 |
|---|---|---|---|
| 客户看板/指标可视化 | `data-visualization` / `build-dashboard` / `create-viz` | 11.5K / 7.8K / 4.7K | Zone B 演示、Zone C 运维大屏 |
| 交付文档写作规范 | [documentation](../zone-d-handoff/anthropic-documentation.md) | 8.8K | Zone D（已有页，见上） |
| 现场数据探查 | `explore-data` / `analyze` / `sql-queries` | 5.2K / 5.1K / 3.8K | Zone B，配合 [query](../zone-b-build/query.md) |
| 架构与技术债评估 | `architecture` / `system-design` / `tech-debt` | 5.7K / 6.6K / 5.7K | Zone A 摸底遗留系统 |
| 事件响应与 runbook | [incident-response](../zone-c-operationalization/incident-response.md) / [runbook](../zone-c-operationalization/sre-runbooks.md) / `ticket-triage` | 5.3K / 2.6K / 2.6K | Zone C（前两页已建） |
| 上线清单 | [deploy-checklist](../zone-c-operationalization/deploy-checklist.md) | 4.9K | Zone B→C 交界，正好补 gate 证据模板 |
| 客户资料综合 | `knowledge-synthesis` / `research-synthesis` | 5.9K / 3.3K | Zone A，配合 [firecrawl-crawl](../zone-a-pre-engagement/firecrawl-crawl.md) |
| PDF 读取 | `view-pdf` | 5.8K | Zone A 客户文档（与本地 [pdf](../zone-a-pre-engagement/pdf.md) 重叠） |

**不用于**：
- **整包安装 230 个 skill** —— 会严重污染 skill 触发空间（描述互相抢、上下文膨胀、定位变慢），并且其中大半是法务/财务/HR/市场岗，与 FDE 交付无关
- 写代码的流程纪律 → [using-superpowers-family](using-superpowers-family.md)；发布/QA/安全审计流水线 → [gstack-suite](gstack-suite.md)
- 已有本地等价物时：`documentation` vs [document-generate](../zone-d-handoff/document-generate.md)、`view-pdf` vs [pdf](../zone-a-pre-engagement/pdf.md)、`code-review` vs [code-review](code-review.md)、`search` vs [firecrawl-search](../zone-a-pre-engagement/firecrawl-search.md)

## 新人上手

- **触发**：先确认没装——本套件 230 件**未整包安装**（也禁止整包：会污染触发空间）；想用某件直接对 agent 点名，如「用 deploy-checklist 出上线清单」「用 runbook 写 XX 的运维手册」
- **第一步**：install-first——按需单装：`npx skills add anthropics/knowledge-work-plugins@<skill> --directory ~/.qoder/skills -y`（推荐顺序：`deploy-checklist` → `runbook` → `documentation`，三者已源码取证），装完再点名调用
- **常见坑**：`--directory ~/.qoder/skills` 必须带——这些 skill 源自 Claude 生态，缺这个参数会装进 `.claude/skills/`，Qoder 看不到
- **常见坑**：同仓库条目也会抢触发——实测 `documentation` 的 description 含 `"write a runbook"`、与 `runbook` 直接重叠；`architecture` / `debug` / `analyze` 这类极通用名易与其他来源撞车，装前过 skill-criticagent 门禁并写清"它替代了谁的哪部分"

## 最佳实践
- **一次只装一个，并写清"它替代了谁的哪部分职责"**——这是本 catalog 维护规约第 3 条（装前门禁）的落地点：先跑 [skill-criticagent](skill-criticagent.md) 评估，通过才装
- 装完把该页从 📦 改 ✅、补安装日期，并在本页表格对应行标注"已装"
- 官方 skill 的产出偏"通用企业知识工作"，用于制造业/具身客户时要**换术语**：把它的模板里的 SaaS 指标替换成现场指标（OEE、停机时长、缺陷率、节拍）
- 平台适配：这些 skill 源自 Claude 生态，安装时务必指定 `--directory ~/.qoder/skills`（否则只会活在 `.claude/skills/`，Qoder 看不到）
- 版本巡检用 `npx skills check` / `update`（见 [skill-discovery](skill-discovery.md)），季度一次，只处理真在用的
- **同仓库条目之间也会抢触发**：已实测 `documentation` 的 description 含 `"write a runbook"`，与 `runbook` 直接重叠——同时装就必须按页内约定切开职责（前者管文档体系，后者管单份手册）
- 取证方式：不要只看 skills.sh（页面 JS 渲染，常常抓不到正文），直接读 GitHub 上的原始 `SKILL.md`。本仓库四个候选均已按此核实为**单文件、无 `scripts/`、无网络调用**的纯模板 skill
- 注意命名冲突：本仓库里 `architecture`、`debug`、`analyze`、`search`、`update`、`start`、`standup` 这类**极通用名**与其他来源的 skill 高概率撞车——装前确认目录与触发描述是否已被占用

## 项目应用位点
- 若只装 3 个的推荐顺序：[deploy-checklist](../zone-c-operationalization/deploy-checklist.md)（直接补 gate 证据模板）→ [runbook](../zone-c-operationalization/sre-runbooks.md)（Zone C 交付物）→ [documentation](../zone-d-handoff/anthropic-documentation.md)（Zone D 写作规范）——三者均已完成源码取证，风险面同为“纯模板”，可按此顺序直接安装
- fde-scope 的 `docs/fde_playbook.md` / `fde_sop_full.md` 结构与 `runbook`、`deploy-checklist` 的输出模板可互相校准
- 与 `fde_scope/skills/` 的关系：这里是外部生态手册；现场沉淀的自制 skill 走 `.fde_scope/skills/` 文件库，二者不覆盖（维护规约第 5 条）

## 相关
[skill-discovery](skill-discovery.md) · [skill-criticagent](skill-criticagent.md) · [sre-runbooks](../zone-c-operationalization/sre-runbooks.md) · [incident-response](../zone-c-operationalization/incident-response.md) · [anthropic-documentation](../zone-d-handoff/anthropic-documentation.md)

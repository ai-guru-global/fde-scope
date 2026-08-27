# anthropic-documentation 📦

> 状态：📦 可安装（未装）· 类型：写作规范 · FDE 位点：Zone D handoff
> 真实条目：`anthropics/knowledge-work-plugins@documentation`（官方 org）· 热度：8.8K installs · https://skills.sh/anthropics/knowledge-work-plugins/documentation
> 安装：`npx skills add anthropics/knowledge-work-plugins@documentation --directory ~/.qoder/skills -y`
> 说明：早期建档记作 `anthropic-documentation`，registry 无该名；已更正为官方 `documentation`。
> 取证（2026-08-27）：源文件 `engineering/skills/documentation/SKILL.md`（49 行，**单文件**，无 `scripts/`、无 `references/`）· https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/documentation/SKILL.md
> 安全：同仓库其他条目一样受上游**强制 Claude policy scan**（`scan-plugins.yml`）保护。风险面极小。
> ⚠️ 命名陷阱：它的触发词里包含 `"write a runbook"` —— 与 [runbook](../zone-c-operationalization/sre-runbooks.md) **抢触发**。两个都装时必须先定分工（见最佳实践）。
> 同类备选：`sammcj/agentic-coding@writing-documentation-with-diataxis`（573，Diátaxis 四象限写作法）

## 能做什么
按官方写作规范产出工程文档（已读源文件确认其真实结构，**不是** Diátaxis 四象限）：五类文档模板 —— README（是什么/为什么 + <5 分钟 quick start + 配置与用法 + 贡献指南）、API Documentation（端点 + 请求/响应例 + 鉴权与错误码 + 限流与分页 + SDK 例）、Runbook（何时用 + 前置权限 + 逐步操作 + 回滚 + 升级路径）、Architecture Doc（背景与目标 + 高层设计与图 + 关键决策与 trade-off + 数据流与集成点）、Onboarding Guide（环境搭建 + 系统如何连接 + 常见任务走查 + 该问谁）；配五条原则：为读者写 / 最有用的信息放前面 / 用代码与截图而不是干说 / 保持新鲜（过期文档比没有更糟）/ 链接而非复制。

## 何时使用
- 交付文档要成体系（README + API 参考 + 架构说明 + runbook + onboarding）而不是散装 README
- 客户方要接手维护，需要他们能持续沿用同一写作标准
- 本仓库文档风格需要统一（现有 `docs/` 文件风格并不完全一致）

**不用于**：文档内容的技术正确性校验（→ [architecture-health](../cross-cutting/architecture-visualization-suite.md)）；PPT/演示（→ [visual-deck-builder](visual-deck-builder.md)）；一次性内部备忘。

## 最佳实践
- **它不是 Diátaxis**：本 skill 是“按文档类型给骨架 + 五条原则”。真要四象限约束，用备选 `sammcj/agentic-coding@writing-documentation-with-diataxis`（573），**两者只选一个**
- **与 runbook 的抢触发如何共处**：`documentation` 管“整套交付文档体系”，[runbook](../zone-c-operationalization/sre-runbooks.md) 管“单份运维手册”；只装一个的话选 `runbook`（它的模板更深：逐步 Expected result / If it fails）
- 它的 Architecture Doc 模板与架构可视化插件的 `architecture-communicator` 重叠：后者带受众分层与证据链，**架构部分优先用后者**
- 与客户确认术语表（工单/缺陷/告警/停机 等中文术语），避免同物不同名
- 规范落地为仓库内 checklist（`docs/writing-style.md`），比装第三个写作 skill 更有效
- 判断是否值得安装：若 [document-generate](document-generate.md) + 项目自身规范已够用，**可以长期不装**——避免 skill 功能重叠导致路由抖动
- 装后回填本页：安装日期、实际用法、与 document-generate 的分工

## 项目应用位点
- Zone D：交付文档体系标准
- 与本仓库既有文档骨架（`docs/fde_playbook.md`、`docs/skills.md`、`docs/code_review_checklist.md`）对齐风格，形成写作 + 落位双约束

## 相关
[document-generate](document-generate.md) · [document-release](document-release.md) · [make-pdf](make-pdf.md)

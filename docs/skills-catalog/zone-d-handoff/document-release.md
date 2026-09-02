# document-release

> 状态：✅ 已安装（gstack 插件 v1.58.5）· 类型：文档同步 · FDE 位点：Zone D handoff + 每次发布

## 能做什么
"Ship 之后"的文档更新：把本次变更同步进 changelog、版本说明、受影响页面的文档，防止文档与实现漂移。与 `ship`（版本/CHANGELOG/PR 流程）配套。

## 何时使用
- 每次功能合并后，同步版本说明与受影响文档段落（本仓库当前**没有** `CHANGELOG.md`，属待建项）
- 交接前最后一个冲刺：把散在对话/PR 描述里的说明收敛成正式文档
- 修完 bug 后确认文档里的行为描述还成立（尤其 gate 与指标口径）

**不用于**：从零补缺失文档（→ [document-generate](document-generate.md)）；代码评审（→ gstack `review` 或 [code-review](../cross-cutting/code-review.md)）；架构性变更的模型更新（→ [architecture-health](../cross-cutting/architecture-visualization-suite.md)）。

## 新人上手

- **触发**：对 agent 说 "post-ship docs" / "update docs after ship" / "document what changed"（SKILL.md triggers 原词），或中文"同步一下本次改动涉及的文档"
- **第一步**：先切到 feature 分支再让它跑——在基线分支上它会直接中止（"Run from a feature branch"）；随后它拉 `git diff <base>...HEAD` 建 Diataxis 覆盖表，逐文件审计并直接修正明显的事实性漂移
- **常见坑**：
  - CHANGELOG 只润色不重写：它对 `CHANGELOG.md` 只做精确匹配的局部编辑、保留全部历史条目，别指望它重排或重新生成 changelog；本仓库还没有 `CHANGELOG.md`，首次需新建并全项目统一一种格式（如 Keep a Changelog）
  - VERSION 不会被悄悄 bump：它一定会先问你；文档覆盖缺口只标记进 PR 描述并建议跑 document-generate，不会自动补写缺失页面

## 最佳实践
- 把"文档同步"当作 Definition of Done 的一条，而不是"有空再做"——交付项目里文档滞后就是验收阻滞
- 与 [architecture-health](../cross-cutting/architecture-visualization-suite.md) 协作：改了架构事实（模块/路由/连接器/gate）必须同时更新 `docs/architecture.md` 与 `docs/architecture-model/`
- CHANGELOG 按"客户能感知的变化"分组，内部重构单独一类或省略
- 版本号与发布物一致：若要新建 changelog，采用 Keep a Changelog 格式并全项目统一，不要混用多种格式
- 每次同步顺手做一次"数字复跑"（路由数、测试数），避免像 `26 vs 27 routes` 这类陈旧声明再次出现

## 项目应用位点
- Zone D `handoff`：交付包文档一致性维护
- 与 fde-scope 的 `docs/architecture.md` 同步：架构事实变更必须同时更新 `docs/architecture.md` 与 `docs/architecture-model/`（注意：仓库当前无 AGENTS.md / `docs/evidence-templates.md`，文档落点靠本 catalog 与 README 约定）

## 相关
[document-generate](document-generate.md) · [make-pdf](make-pdf.md) · [architecture-health](../cross-cutting/architecture-visualization-suite.md)

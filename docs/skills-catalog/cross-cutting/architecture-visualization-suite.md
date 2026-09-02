# architecture-visualization 套件（架构可视化 13 件套）

> 状态：✅ 已安装（Quest Marketplace 插件 v0.1.0，无 MCP / 无 commands / 无 agents）· 类型：套件档案 · FDE 位点：横切（Zone A~D 全用）
> 本地路径：`~/.qoder/plugins/cache/qoder-marketplace/architecture-visualization/0.1.0`

## 能做什么
证据优先的架构理解/建模/评审/演进工具箱。**三层 MECE 结构**：

| 层 | Skill | 回答的问题 |
|---|---|---|
| 路由 | `explore` | 宽泛架构请求 → 选最小技能集 |
| 场景 | `system-modeler` | 系统现在长什么样（结构/边界） |
| 场景 | `flow-visualizer` | 业务/调用/数据/事件怎么流动 |
| 场景 | `dependency-impact-analyzer` | 谁依赖谁、改动影响什么（blast radius） |
| 场景 | `deployment-topology-analyzer` | 在哪运行、如何发布运维 |
| 场景 | `evolution-planner` | 该怎么演进、为什么（ADR + 迁移切片） |
| 场景 | `risk-quality-reviewer` | 风险够不够低、质量够不够（含业务适配度） |
| 场景 | `legacy-system-visualizer` | 低证据老系统如何理解与安全迁移切片 |
| 场景 | `architecture-communicator` | 向这个受众怎么讲（客户高管 vs 车间） |
| 场景 | `architecture-health` | 图/文档是否新鲜、可追溯（含 skill 激活冒烟） |
| 基础 | `c4model` | Structurizr DSL / C4 视图 |
| 基础 | `graphviz` | 密集关系 DOT（依赖/血缘/风险/影响） |
| 基础 | `drawio` | 可编辑交付格式（仅显式请求时） |

## 何时使用（按 FDE 阶段）
- Zone A 现场调研 → `system-modeler`（客户系统摸底）+ `architecture-communicator`（对客户讲）
- Zone B 实施 → `dependency-impact-analyzer`（改动前评估）+ `flow-visualizer`（数据链路）
- Zone C 运维 → `deployment-topology-analyzer`（拓扑/发布）+ `risk-quality-reviewer`（上线风险）
- Zone D 交接 → `architecture-health`（文档与代码一致性）+ `drawio`（客户可编辑交付图）
- 遗留系统接手 → `legacy-system-visualizer` + `evolution-planner`

## 新人上手

- **触发**：宽泛架构请求直接说「帮我理解这个系统的架构」「画出这个 repo 的架构图」「这次改动会影响什么」——入口是 `explore` 路由（13 件套的 router，"Use this skill first"），由它按场景选最小技能集
- **第一步**：对 agent 说「用 explore 帮我建模 fde-scope 的当前架构」；路由器先读共享门禁 references（`architecture-contract.md` / `architecture-evidence-model.md` / `diagram-output-formats.md`），再按场景表路由到 `system-modeler`、`flow-visualizer` 等具体 skill
- **常见坑**：绕过 `explore` 直接点某个场景 skill，容易产出与问题不匹配的视图——路由原则是"先定架构任务、再定图格式"，不按产物类型选 skill
- **常见坑**：每个节点/边必须有 `sourceRefs` 指向代码/配置/文档等证据，低置信度必须显式标注——这是插件的硬门禁，无证据的图过不了 `architecture-health` 校验

## 最佳实践
- **先 `explore` 再选场景**：直接点某个场景 skill 容易产出不匹配问题的视图
- 视图分级不要越界：L1 上下文 / L2 容器 / L3 代码 / L4 运行时 / L5 演进；问错层就是噪声
- 每个节点/边要有 `sourceRefs`，低置信度必须显式标注（该插件的硬门禁，也是它最有价值的纪律）
- 按需加载 references（`architecture-contract.md`、`architecture-evidence-model.md`、`diagram-output-formats.md`、`structurizr-canvas-pipeline.md`），别一次读全部
- 边界纪律：本套件的 skill 会互相路由——风险发现交 `risk-quality-reviewer`，修复方案交 `evolution-planner`，新鲜度交 `architecture-health`，不要指望一张图解决所有问题
- 格式选择：C4 用 DSL、密集关系用 DOT、轻量内联用 Mermaid（适合直接写在 Markdown 里的小图）

## 项目应用位点（已发生）
- `docs/architecture-model/`：`fde-scope.structurizr.dsl`（L1/L2）、`module-dependency.dot`（L3 模块依赖）、`system-model.evidence.md`、`system-model.summary.md`
- `docs/architecture-model/architecture-health-report.md`：校验 `docs/architecture.md`，发现 1 处陈旧声明（flywheel 不导入 agentscope）+ 1 处拼写错误，已修正
- 待办：`docs/architecture.md` 只描述到 `web/app.py`，未包含 `pawapp/`（文档缺口）

## 相关
[system-modeler 用法示例](../zone-a-pre-engagement/zread.md) · [drawio](../zone-a-pre-engagement/drawio.md) · [document-release](../zone-d-handoff/document-release.md)

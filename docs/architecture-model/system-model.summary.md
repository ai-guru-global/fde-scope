# FDE Scope 现状架构模型 — 总结

> 由「架构可视化」插件的 `explore` → `system-modeler` + `c4model` + `graphviz` + `architecture-health` 工作流产出。

## 系统边界一句话

FDE Scope 是 FDE（Forward Deployed Engineer）在客户现场的**操作系统**：把 18 阶段标准作业流程（4 zones）变成可执行、可被 10 个 gate 拦截的状态机，覆盖客服工单（ticket）与制造业/具身机器人（manufacturing）双场景。

## 结构速览

- **3 个使用入口**：Typer CLI（`fde-scope` 命令，全函数内延迟导入）、FastAPI Web 控制台（27 路由，三视图）、QwenPaw PawApp 桌面插件（18 路由挂载 `/api/fde-scope`，薄封装复用宿主 LLM/沙箱/存储）。
- **1 个核心引擎包 `fde_scope`**：SOP 层（engagement + gates）、场景层（profiles）、能力层（connectors/corpus/deploy/eval/flywheel/integrations/skills）、横切层（llm/config/templates/paths）。
- **1 个零数据库文件事实源 `.fde_scope/`**：engagement 快照、技能库（draft→published→archived）、uploads；`reports/` 存 HTML 报告与 runbook。
- **3 个可选外部依赖**：MiMo LLM（标准库 urllib、失败回退规则）、AgentScope 2.0.x（optional extra，实测窗口 `>=2.0.4.post1,<3`，**deploy/ 三支柱 5 模块 + connectors/documents.py 延迟导入**）、QwenPaw 宿主。

## 关键架构事实（均有证据）

1. **零配置可跑**：agentscope 为 optional extra 且全函数内延迟导入（deploy/ 三支柱 + connectors/documents.py rag 解析器），未安装时 `pip install -e ".[dev]"` + pytest 全绿；兼容窗口逐版本实测并由架构守护测试钉住。
2. **SOP 即工程物**：`Engagement.advance()` 在 gate 未通过时拒绝推进并返回 blockers；10 gate 中 7 个为制造业专属（FAT/SAT、功能安全、CE、works council、air-gap、班次交接、site survey）。
3. **依赖方向健康**：UI → 能力、能力 → 横切，未发现跨模块组循环依赖；唯一值得注意的跨层边是 `profiles.manufacturing → eval.manufacturing_metrics`（KPI 定义复用）。
4. **LLM 诚实降级**：所有 `llm=None` 可选注入，回退后不声称 LLM 生成；凭据仅走环境变量。

## 产物清单

| 文件 | 作用 | 查看方式 |
|---|---|---|
| [`fde-scope.structurizr.dsl`](fde-scope.structurizr.dsl) | C4 系统上下文 + 容器视图（可维护事实源） | Qoder 打开该文件用 Structurizr DSL 格式查看器预览 |
| [`module-dependency.dot`](module-dependency.dot) | 模块依赖图（分层聚类，虚线=延迟/可选导入） | Qoder 打开该文件用 DOT Canvas 预览，或 `dot -Tsvg` 渲染 |
| [`system-model.evidence.md`](system-model.evidence.md) | 节点/边证据索引、置信度、未知项、再生成命令 | 直接阅读 |
| [`architecture-health-report.md`](architecture-health-report.md) | `docs/architecture.md` 与代码的逐项一致性校验 | 直接阅读 |
| [`architecture-map.md`](architecture-map.md) | 通读版整合视图（Mermaid 内嵌 + 证据表 + 2026-08-28 复核结论） | 直接阅读 |

## 已知缺口（验证任务）

- Zammad/Salesforce/ROS2/Historian 连接器的真实连接深度（部分为 JSONL 模式）——跑带 `mysql`/`opcua` 标记的真机测试确认。
- 无运行时观测数据；本模型为静态结构模型，不含流量/时序/部署拓扑。

## 下一步建议

- ~~固化架构守护测试~~ **已完成**：`tests/test_architecture_guard.py` 6 项（18 阶段 / 10 gate / 连接器卫生 / extras 完整性 / 安装文档一致 / agentscope 窗口见文档）。
- 需要业务流视角（connect→corpus→deploy→eval→flywheel 全链路）时，用本插件 `flow-visualizer` 继续。

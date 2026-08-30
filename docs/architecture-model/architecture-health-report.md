# Architecture Health 报告 — docs/architecture.md 一致性校验

- 校验日期：2026-08-26
- 被检文档：[`docs/architecture.md`](../architecture.md)
- 校验方法：文档声明 → 代码证据逐项比对（计数用 grep，导入用全库扫描）
- 产出技能：`architecture-health`（架构可视化插件）

## 结论

文档整体**可信（10/12 项一致）**，发现 **1 处陈旧声明 + 1 处拼写错误**，均不影响架构理解，建议随手修正。

## 逐项比对

| # | 文档声明 | 代码证据 | 判定 |
|---|---|---|---|
| 1 | 4 zones / 18 阶段状态机 | `engagement/phases.py` 中 `Phase(` 计数 = 18 | ✅ 一致 |
| 2 | 10 个可执行 gate | `engagement.py` `_default_gate_registry` 注册 10 个 `Gate()`（SiteSurvey/SuccessCriteria/FatSat/FunctionalSafety/Conformity/WorksCouncil/AirGap/ShiftHandover/SLO/HandoffSignoff） | ✅ 一致 |
| 3 | 工业并行 gate 表列 7 个 | `engagement/gates/` 下 7 个文件与表一一对应 | ✅ 一致 |
| 4 | Layer 1 连接器清单（CSV·Zammad·Salesforce·MySQL + OPC UA·MQTT·ROS2·MES·Historian） | `connectors/` 恰 10 个连接器模块 + base/_registry/schema | ✅ 一致 |
| 5 | 核心数据层 + SOP + Profiles + Web 完全不依赖 agentscope | 全库 `import agentscope` 扫描仅命中 `deploy/`（sandbox_config.py:65、tenant_manager.py:64/156-157/195、permission_builder.py:99，均为函数内延迟导入） | ✅ 一致 |
| 6 | "仅 deploy / **flywall** 延迟导入 agentscope（optional extra）" | flywheel 代码（engine/collectors/event_mapping）**无任何 agentscope 导入**；且 "flywall" 为拼写错误（应为 flywheel） | ⚠️ **陈旧**：实际仅 `deploy/` 导入；建议改为"仅 deploy 延迟导入 agentscope" |
| 7 | PawApp 后端 17 路由挂载 `/api/fde-scope` | `pawapp/backend/main.py` 路由装饰器计数 = 17 | ✅ 一致 |
| 8 | Web 三视图控制台（workbench + journal + skills） | `web/app.py` 存在三类端点（路由总数 26，文档未声称具体数字，不冲突） | ✅ 一致 |
| 9 | MiMo 横切：可选注入、失败回退、凭据仅走环境变量 | `llm.py` 实现 + `cli.py/_maybe_llm`、corpus `--llm`、handoff `--llm` 注入点 | ✅ 一致（"6 接入点"数量未逐一计数，medium） |
| 10 | Corpus 规则为底、LLM 可选增强（同签名换内核） | `corpus/pipeline.py` 接受 `llm=None`，synthesizer 延迟导入 MiMoClient | ✅ 一致 |
| 11 | 多 Agent 拓扑：manifest `agents` + `subagent_templates` | `deploy/tenant_manager.py:195` 导入 `SubAgentTemplate`；config.AgentSpec 存在 | ✅ 一致 |
| 12 | CLI 命令族 engage/gate/status/handoff/connect/corpus/… | `cli.py` 定义 connect/corpus/deploy/eval/flywheel/engage-*/gate-*/handoff/kpi/profiles/web/qwenpaw-*/skill-* | ✅ 一致（"…"兜底） |

## 建议修正（一行级改动）

`docs/architecture.md` 第 96 行：

```diff
-- 仅 deploy / flywall 延迟导入 agentscope（optional extra）。
+- 仅 deploy 延迟导入 agentscope（optional extra）；flywheel 已为纯规则实现。
```

## 后续 living architecture 建议

1. 将本次的计数命令（阶段数 / gate 数 / 路由数 / agentscope 导入位置）固化为 `tests/` 中的一个架构守护测试，防止文档再漂移。
2. `docs/architecture-model/` 下的 DSL/DOT/evidence 三件套与 `docs/architecture.md` 同源维护：改模块结构时同步再生成（再生成命令见 [`system-model.evidence.md`](system-model.evidence.md#再生成方式)）。
3. 若引入真实运行时观测（trace/日志），再补 runtime topology 视图，勿与静态结构混画。

---

## 复核附录（2026-08-28，基线 090ff68）

- 触发：b24b714 之后的 7 个提交（deploy 三支柱、B1 数据根、B5 权限管线、agentscope 窗口实测、skills catalog 守护）未同步进架构产物。
- 方法：全库 import 扫描 + 计数 grep + git log --follow 漂移窗口分析；整合结论沉淀于 [`architecture-map.md`](architecture-map.md)。

### 发现并已修正（canonical 图源与文档同步回写）

| # | 陈旧声明 | 现状 | 回写位置 |
|---|---|---|---|
| 1 | 仅 deploy/ 延迟导入 agentscope | deploy/ 5 模块（app_service/permission_builder/sandbox_config/tenant_manager/toolkit）+ **connectors/documents.py**（`agentscope.rag`，b24b714 引入），全为函数内延迟导入 | DSL、DOT、summary、architecture.md §4 |
| 2 | "AgentScope 2.0.5" 硬编码 | 实测窗口 `agentscope[ollama,service]>=2.0.4.post1,<3`（2.0.4 缺 ExcelParser 不可用） | DSL、DOT、summary、architecture.md §6 |
| 3 | Web 控制台 26 路由 | 27 路由 | DSL、DOT、summary |
| 4 | PawApp 17 路由 | 18 路由 | DSL、DOT、summary |
| 5 | 文件事实源位置未提解析语义 | `fde_scope/paths.py::data_root()` 四级解析（FDE_SCOPE_HOME > 项目 .fde_scope > ~/Documents/FDE Scope > CWD），tests/test_paths.py 钉契约 | DSL、architecture-map.md §6 |

### 新增确认事实

- 架构守护测试已落地：`tests/test_architecture_guard.py` 6 项（本报告 2026-08-26 版的建议 1 已完成）；复核当日 6/6 绿。
- 技能目录一致性守护：`scripts/check_skills_catalog.py`；工作树含未提交的 zone-b/zone-c 目录扩充（docs 级）。
- B5 权限管线行为（read-only 上游自动放行 → build_toolkit 不打 `is_read_only`）已进入 AGENTS.md 不变式。

### 剩余待办

- 连接器真机深度（`mysql`/`opcua` 标记测试）。
- 引入运行时观测后再补 runtime topology 视图。

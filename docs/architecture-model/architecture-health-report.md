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

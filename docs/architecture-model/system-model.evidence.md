# FDE Scope 现状架构模型 — 证据索引

- 生成日期：2026-08-26
- 状态：**current-state**（不含路线图/目标态）
- 产出技能：`system-modeler` + `c4model` + `graphviz`（架构可视化插件）
- 配套图源：[`fde-scope.structurizr.dsl`](fde-scope.structurizr.dsl)（L1 系统上下文 / L2 容器）、[`module-dependency.dot`](module-dependency.dot)（L3 模块依赖）

## 节点证据

| 节点 | 类型 | 置信度 | sourceRefs |
|---|---|---|---|
| FDE（使用者） | actor | high | README.md、docs/fde_sop_full.md |
| CLI 工作台 | module | high | [pyproject.toml `fde-scope = fde_scope.cli:app`](../../pyproject.toml)、fde_scope/cli.py |
| Web 控制台（26 路由） | module | high | fde_scope/web/app.py（grep `@app.*` 计数 26） |
| PawApp（17 路由 @ /api/fde-scope） | module | high | pawapp/backend/main.py（路由计数 17）、pawapp/plugin.json |
| 核心引擎 fde_scope | module | high | fde_scope/__init__.py、pyproject.toml dependencies |
| engagement（18 阶段/4 zones/10 gate） | module | high | fde_scope/engagement/phases.py（`Phase(` 计数 18）、engagement/engagement.py `_default_gate_registry`（10 个 Gate） |
| connectors（10 个） | module | high | fde_scope/connectors/*.py（csv_fallback/mysql_generic/opcua/mqtt_sparkplug/ros2_bag/mes_isa95/historian/zammad/salesforce + base/_registry/schema） |
| corpus 语料引擎 | module | high | fde_scope/corpus/pipeline.py、docs/architecture.md |
| deploy 多租户组装 | module | high | fde_scope/deploy/tenant_manager.py、sandbox_config.py、permission_builder.py |
| eval 评估 | module | high | fde_scope/eval/benchmark.py、manufacturing_metrics.py |
| flywheel 数据飞轮 | module | high | fde_scope/flywheel/engine.py、collectors.py、event_mapping.py |
| integrations 导出 | module | high | fde_scope/integrations/qwenpaw_exporter.py、validator.py、acp.py |
| profiles 场景选择 | module | high | fde_scope/profiles/base.py、ticket.py、manufacturing.py |
| skills 技能沉淀库 | module | high | fde_scope/skills/service.py、store.py、exporters.py、docs/skills.md |
| llm.py 横切层 | module | high | fde_scope/llm.py、docs/llm_integration.md |
| 文件事实源 .fde_scope/ | database(file) | high | fde_scope/config.py、cli.py `_engagement_path`、目录树 |
| AgentScope 2.0.5 | external-system | high | pyproject.toml `[project.optional-dependencies].agentscope`；实际 `import agentscope` 仅见 deploy/（sandbox_config.py:65、tenant_manager.py:64/156/195、permission_builder.py:99） |
| MiMo Token Plan | external-system | high | fde_scope/llm.py、docs/llm_integration.md；凭据走 `FDE_SCOPE_MIMO_API_KEY` |
| 客户数据源 | external-system | medium | connectors 各实现的协议/文件读取代码；真实远端连接需环境变量（pyproject pytest markers：mysql/opcua） |
| QwenPaw 宿主 | external-system | high | pawapp/README.md、docs/qwenpaw_integration.md、pawapp/plugin.json |

## 边证据（关键关系）

| 边 | 类型 | 置信度 | sourceRefs |
|---|---|---|---|
| cli → 全部能力模块 | depends-on（函数内延迟导入） | high | fde_scope/cli.py（40+ 处 `from .xxx import` 于函数体内） |
| web → engagement/profiles/skills（顶层）+ 其余延迟 | depends-on | high | fde_scope/web/app.py:26-28（顶层）、208-456（延迟） |
| pawapp → fde_scope 全栈薄封装 | depends-on | high | pawapp/backend/main.py（30+ 处延迟导入） |
| corpus → connectors/llm | depends-on（TYPE_CHECKING / 可选注入） | high | corpus/pipeline.py:24-26、synthesizer.py:27 |
| eval → corpus/llm | depends-on | high | eval/benchmark.py:19-20 |
| deploy → agentscope | depends-on（延迟，唯一真实导入处） | high | deploy/*.py 见上 |
| flywheel → corpus.types | depends-on | high | flywheel/collectors.py:15 |
| integrations → config/corpus/skills | depends-on | high | integrations/qwenpaw_exporter.py:19-21、98 |
| profiles.manufacturing → eval.manufacturing_metrics | depends-on（跨层） | high | profiles/manufacturing.py:11 |
| engagement → llm/templates | depends-on（可选 runbook 起草） | high | engagement/operationalization.py:43、templates/runbook.md.j2 |
| connectors → 客户数据源 | reads | medium | 各 connector 实现；OPC UA/MySQL 真实连接依赖外部环境变量 |
| llm → MiMo | calls（HTTP/urllib） | high | fde_scope/llm.py |
| 核心层零 agentscope | 架构约束 | high | 全库 `import agentscope` 扫描仅命中 deploy/（2026-08-26） |

## 假设与未知

| 项 | 级别 | 说明 / 验证任务 |
|---|---|---|
| Zammad/Salesforce/ROS2/Historian 的真实连接深度 | assumed | 记忆与 docs 路线图表明部分为 JSONL/stub 模式；验证：逐个运行对应 tests/test_*_connector.py 真机标记用例 |
| MiMo "6 接入点" 精确数量 | medium | docs 声称 6 接入点；本次仅验证存在性，未逐一计数 |
| 运行时调用频率/时序 | unknown | 本模型为静态结构模型，无运行时观测数据 |
| 数据敏感度/租户隔离的运行时有效性 | unknown | 三层隔离为 AgentScope 类型组装，真实运行时验证见 docs 与测试 |

## 再生成方式

```bash
# 模块导入边（DOT 图的证据来源）
for f in $(find fde_scope pawapp/backend -name '*.py' ! -name '__init__.py' ! -path '*__pycache__*'); do
  grep -nE '(^|\s)(from|import) ' "$f" | grep -E 'from \.\.|from fde_scope|from \.[a-z]|import fde_scope'
done
# gate / 阶段 / 路由计数
grep -c 'Gate()' fde_scope/engagement/engagement.py
grep -cE '^\s*Phase\(' fde_scope/engagement/phases.py
grep -cE '@(app|router)\.(get|post|put|delete|patch)' fde_scope/web/app.py pawapp/backend/main.py
```

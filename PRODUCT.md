# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated: 静态 HTML/CSS/JS（无构建链，浏览器直接打开，可放 GitHub Pages）— 与仓库零构建约定一致；用户确认。

## Users

四类受众兼顾（用户确认），页面按优先级分层说服：

1. FDE 团队负责人 / Founder — 组建或运营 FDE 团队，痛点：每次进场从零搭流程；目标是认可并安装这套 SOP 引擎。
2. 一线 FDE 从业者 — 在客户现场工作，想要立刻可用的工作台。
3. 开源社区开发者 — 关注 AI 工程方法论，目标是 Star / 试用 / 贡献。
4. 企业决策者 — 评估引入 AI 交付能力的制造/软件企业，需要合规与安全的证据。

## Product Purpose

FDE Scope 是 Forward Deployed Engineer 的完整现场操作系统：把 FDE 的完整 SOP（4 zones、18 phases）固化为可执行、门禁强制的状态机，覆盖软件/SaaS 与具身机器人/制造两类场景。构建在 AgentScope 2.0 之上，交付形态为 CLI + Web 控制台 + Python 库。成功 = 一支 FDE 团队用同一套受门禁强制的流程跑完从首次现场调研到签收交接的全过程。

## Positioning

唯一把 FDE 全生命周期（不止 Build 区段）做成可执行门禁的开源工具：10 个门禁全部是可执行代码 `Gate.check()`，含真实工业 overlay（FAT/SAT、ISO 13849 / IEC 61508 / ISO 10218 功能安全、CE/EU-AI-Act 合规、德国劳资共决 BetrVG §87、气隙部署、换班交接）。相邻产品（agent 框架、eval 工具）只建模 Build 半程；FDE Scope 拥有整个 engagement 弧线。

## Operating Context

- 现场场景：客户工厂/办公地（gemba walk）、车间 FAT/SAT 验收、换班交接、客户签收。
- 工作流：4 zones（Pre-engagement → Build → Operationalization → Handoff）、18 phases、10 gates、2 profiles（ticket / manufacturing）。
- 工件：runbook、corpus report、eval metrics、SLO、handoff package、技能沉淀库（skills）。
- 运行环境：Python ≥3.11、`pip install -e ".[dev]"`、零 LLM key 可跑、`fde-scope web` 打开控制台。

## Capabilities and Constraints

- 确认能力：18-phase 状态机 + 10 gates；ticket/manufacturing 双 profile；CSV/Zammad/Salesforce/MySQL + OPC UA/MQTT/ROS2/MES/Historian 连接器（部分为接口）；corpus forge；eval + 工业 KPI（OEE/MTBF/FPY…）；flywheel；QwenPaw 导出；技能库双格式导出；MiMo Token Plan 可选接入；多 Agent 生产——每个 AgentSpec 装配为真实 AgentScope 2.0 Agent（模型 wiring + 角色 Toolkit + PermissionContext 注入），FDE 三通道自开 Agent（CLI `--agent 名字:角色[:模型]` / YAML agents 段 / 单 Agent toolkit 覆盖），SubAgentTemplate 蓝图 + AgentCreate/TeamSay 官方协调，`deploy --serve` 起真实服务（需 Redis + 可达模型）。
- 约束：MIT 开源；GitHub 仓库 `ai-guru-global/fde-scope`；无 LLM key/Docker 也能跑核心层。
- 未决：无真实商务联系渠道（不得虚构邮箱/表单后端）；无真实客户授权（README 中为 mock 数据，需标注）。

## Brand Commitments

- 用户确认：页面文案中英双语。
- README 主线语言为英文；代码/CLI 名 `fde-scope`；基于 AgentScope 2.0。
- 未确认 logo/品牌资产；未确认视觉基调（由 new-work 决定）。

## Evidence on Hand

- 可用真实素材：4 zones/18 phases/10 gates 清单；2 profiles；10 门禁的检查语义（README 表格）；6 个 mock engagement（古茗、一汽-大众、广汽、一汽、曹操出行、易点天下——README 声明为 engine 生成的 mock 数据）；quick start 命令；`docs/fde_sop_full.md`（18 阶段 + 12 反模式）；`docs/manufacturing_scenario.md`；CI/coverage 徽章（~89% 覆盖率）。
- 多 Agent 素材：`--agent 名字:角色[:模型]` CLI 通道（中文角色名实测可用）；真实 Toolkit 广播绑定工具（如 csv_sample/csv_schema）；SubAgentTemplate 蓝图注册进真实 create_app（CI 真库测试）；未配数据源的工具在 manifest 诚实标注 unbound。
- 不得虚构：真实客户署名与评价、真实基准数据、下载量、联系渠道；mock 数据引用处需可辨识为演示数据。

## Product Principles

1. 门禁是工程，不是清单 — 一切主张落为可执行检查。
2. 全程覆盖 — 交付价值由 Pre-engagement/Operationalization/Handoff 区段决定，不止 Build。
3. 现场优先 — 工厂、车间、换班、合规是第一等公民，不是事后补丁。
4. 零门槛可验证 — 无 key、无 Docker 即可安装并跑通证据链。

## Accessibility & Inclusion

- 中英双语并存时两者都必须可读（无灰字小号中文）。
- WCAG AA 对比度；键盘可达；语义化 HTML。

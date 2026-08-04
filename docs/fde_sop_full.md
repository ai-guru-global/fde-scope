# FDE 完整 SOP — 4 Zones / 18 阶段

> 本文是 FDE Scope 的方法论核心。它把"FDE 在现场到底做什么"从口号变成
> **可执行、可被 gate 拦截的工程化流程**。依据见文末来源；工业 overlay 部分
> 是合成的（公开无工业 FDE SOP——这是项目的领先性，不是缺陷）。

## 为什么不是 5 步

naive 的 5 步模型（connect → corpus → deploy → eval → flywheel）只覆盖 **Build zone**，
约占真实 engagement 的一半。完整生命周期有 **4 zones / 18 阶段**，其中
Pre-engagement（4 阶段）+ Operationalization（5 阶段）+ Handoff（3 阶段）是
naive 模型完全缺失、却决定 engagement 成败的部分。

## 4 Zones

```
Zone A · Pre-engagement      ① qualification  ② site-survey(gemba)  ③ stakeholder-map  ④ success-criteria
        │
Zone B · Build               ⑤ connect  ⑥ corpus  ⑦ prototype-on-real-data  ⑧ validate  ⑨ deploy  ⑩ eval
        │
Zone C · Operationalization  ⑪ slo-sla  ⑫ runbook  ⑬ monitoring-drift  ⑭ change-mgmt-training  ⑮ flywheel→productization
        │
Zone D · Handoff/Exit        ⑯ ops-handoff  ⑰ knowledge-transfer  ⑱ disengage
```

## 18 阶段详解

### Zone A · Pre-engagement
| # | 阶段 | gate | 工业? | 要点 |
|---|---|---|---|---|
| 1 | qualification | — | — | 客户带着问题而非平台来。判定是否 FDE-worthy：高价值、数据难、客户集中。**拒绝商品化用例。** |
| 2 | site_survey | site_survey | 🏭 | gemba walk：物理环境、OT 网络、资产清单、安全约束。SaaS 无此阶段。 |
| 3 | stakeholder_map | — | — | 识别执行发起人 + **第二发起人**（防 Sponsor Collapse）。统一成功标准。 |
| 4 | success_criteria | success_criteria | — | 可度量结果 + 书面 done（≤14d 集成、≤90d 上线、≤120d 交接）。**防无限 pilot。** |

### Zone B · Build
| # | 阶段 | gate | 工业? | 要点 |
|---|---|---|---|---|
| 5 | connect | — | — | 连接器接入（OPC UA / MQTT / CSV / Zammad…）。"数据千奇百怪"的现实。 |
| 6 | corpus | — | — | 清洗 → 覆盖度 → 合成补盲 → 报告。核心差异化。 |
| 7 | prototype_real_data | — | — | 在**生产形态的真实未策展数据**上原型——不用策展测试集。这是 demo→production 落差的主因。 |
| 8 | validate | — | — | 与真实干系人（含冲突成功指标的）验证。 |
| 9 | deploy | fat_sat | 🏭 | 工业：FAT→发货→SAT→commissioning。SaaS：直接上线。 |
| 10 | eval | — | — | 用评估框架证明价值。bad cases 是持续调优抓手。 |

### Zone C · Operationalization
| # | 阶段 | gate | 工业? | 要点 |
|---|---|---|---|---|
| 11 | slo_sla | slo | — | 错误预算、告警路由、含 FDE 的 on-call 轮值。 |
| 12 | runbook | — | — | 事件响应、回滚、安全失败模式。 |
| 13 | monitoring_drift | — | — | AI 是概率性的，暴露在生产数据上会退化。 |
| 14 | change_mgmt_training | works_council | 🏭 | 工业现场含工会/works-council 共决（德国 BetrVG §87）。 |
| 15 | flywheel_productization | — | — | 现场学习回流核心产品（每周产品化评审，≥1 个特性产品化）。 |

### Zone D · Handoff / Exit
| # | 阶段 | gate | 工业? | 要点 |
|---|---|---|---|---|
| 16 | ops_handoff | — | — | 所有权转交 Customer Success / 客户运维。 |
| 17 | knowledge_transfer | — | — | 文档包：runbook + eval 报告 + SLO + 模型卡 + 培训材料。 |
| 18 | disengage | handoff_signoff | — | 上线后 ≤120d 转交。**无限 pilot 是反模式。** |

## 工业 Overlay（manufacturing/robotics profile 启用）

SaaS FDE 不需要、但工业 FDE 必须的并行 gate：

| gate | 标准/依据 | 拦截条件 |
|---|---|---|
| site_survey | gemba walk | location 未记录 |
| fat_sat | FAT/SAT 验收 | FAT 或 SAT 未执行/未通过/未签字 |
| functional_safety | ISO 13849 PL 等级 / IEC 61508 SIL / ISO 10218 | 达成 PL < PLr；SIL 不足；未做危险分析 |
| conformity | EU AI Act Art.48 / CE marking | 高风险系统未 CE / 缺技术构造文件 |
| works_council | 德国 BetrVG §87(1) No.1 & No.6 | works council 在场但无审批记录 |
| air_gap | air-gapped 部署 | edge 硬件/离线模型更新缺失；遥测出网 |
| shift_handover | 24/7 生产 | 多班次但未集成数字交接 |

## 12 大反模式（gate 直接守卫）

1. Consulting Trap — FDE 漂成定制咨询，饿死平台。
2. Snowflake-Per-Customer — 每客户一套，单位经济腐烂。
3. Hero Engineer — 单人英雄主义，知识孤岛。
4. Demo-Debt Spiral — demo 演的平台做不到。
5. Sponsor Collapse — 唯一发起人离职即死。
6. Burnout Death Spiral — 高级 IC 先走。
7. Probabilistic Degradation — 无飞轮，线上退化无人知。
8. Infinite Pilots — 没人定义 done，飘过 180 天。
9. Data Quality Surprises — 假设数据已集中。
10. Scope Creep — 无时间盒 SLA。
11. No HITL — 缺人机协作。
12. Safety Incidents — 工业现场未经功能安全验证。

## 工程化映射

每个阶段在 `fde_scope/engagement/phases.py` 里是一个 `Phase` 数据类；
推进由 `Engagement.advance()` 强制当前阶段的 gate 通过；
gate 在 `fde_scope/engagement/gates/` 是 `Gate.check(ctx) -> GateResult`。
Web UI 和 CLI 都消费同一套状态机。

## 来源（真实依据）

- **Palantir**：FDE 模型鼻祖（blog.palantir.com "A Day in the Life"）
- **perspective.ai**：FDE Founder Playbook 2026（≤14d/≤90d/≤120d SLA、产品化强制）
- **FDE Academy**：10 大问题（stakeholder disagreement、adoption、data surprise）
- **Insight Partners**："Demystifying the FDE"
- **ISO/IEC/VDMA**：ISO 13849 / IEC 61508 / ISO 10218-1:2025 / VDA 5050 / ISA-95
- **EU AI Act** Art.48 CE marking；德国 BetrVG §87
- 工业现场协议：OPC UA (IEC 62541)、MQTT Sparkplug B、UR RTDE 500Hz、ABB EGM、KUKA RSI、FANUC FOCAS
- KPI 基准：oee.com（OEE 85% world-class）、Six Sigma（3.4 DPMO）、NIST/DexNet（抓取率 ~80%）

**诚实声明**：人形机器人 telemetry schema、车间语音 copilot at-scale 等，公开无标准；
本项目按 per-vendor adapter 建模，不假设 OPC UA/ROS 现成可用。

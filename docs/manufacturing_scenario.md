# 具身机器人工厂场景 — 端到端走查

> 场景：一个整车厂车身+总装车间，5 个工位（焊装×2 / 涂装 / 协作机器人装配 /
> 人形机器人装配），部署一个"故障诊断 + 任务规划"AI agent。
> 本文演示 FDE Scope 的工业 profile 如何走完整 18 阶段 SOP。

## 工位画像（examples/quickstart_manufacturing/station_samples.jsonl）

| 工位 | 类型 | OEE | 抓取率 | 干预率 | 画像 |
|---|---|---|---|---|---|
| BODY-WELD-01/02 | 焊装（PLC） | ~0.78 | — | ~0.6% | 成熟，OEE 中等 |
| PAINT-01 | 涂装 | ~0.87 | — | ~0.1% | 高 OEE，稳定 |
| ASSY-COBOT-01 | 协作机器人 | ~0.70 | 79% | 1.5% | 抓取爬坡中 |
| ASSY-HUMANOID-01 | 人形机器人 | ~0.51 | 73% | 3.2% | 新部署，明显爬坡期 |

人形机器人/协作机器人工位是 AI agent 价值最高的地方（抓取率、干预率都有提升空间），
也是功能安全 / CE / 工会最敏感的地方。

## 走查：18 阶段

### Zone A · Pre-engagement
- **① qualification**：痛点是 ASSY 线抓取失败率与干预率高，导致节拍失衡。FDE-worthy：高价值（节拍每秒都在烧钱）、数据可接（OPC UA + rosbag）、客户集中。
- **② site_survey (🏭)**：gemba walk 发现——OT/IT 分离、3 班次、works council 在场、人形机器人工位靠近人工工位（安全关注）。**填 site_survey gate。**
- **③ stakeholder_map**：发起人 = 生产总监 + IT 总监（双 sponsor）。
- **④ success_criteria**：抓取率 73% → 85%（6 个月）、干预率 3.2% → 1.5%、OEE +5pp。**写进 success_criteria gate。**

### Zone B · Build
- **⑤ connect**：OPC UA 接 PLC tag（节拍/报警）、MQTT-Sparkplug 接 AMR、rosbag2 接机器人抓取轨迹、MES 接工单/停机码、Historian 接振动/电流时序。（连接器 stub 已就位；真实 IO 路线图。）
- **⑥ corpus**：rosbag 抓取轨迹 + 报警日志 → 锻造语料 → 覆盖度报告发现"人形机器人碰撞后恢复"语料极少（缺口）→ 合成补盲。
- **⑦ prototype_real_data**：在**真实未策展的** rosbag 上原型任务规划，不用 curated demo。
- **⑧ validate**：与生产总监 + 班组长验证（班组长关心干预率，总监关心 OEE）。
- **⑨ deploy (🏭 fat_sat gate)**：FAT 在 integrator 现场测 → 发货 → SAT 在客户车间复测。**gate 拦截：FAT/SAT 未签字前不上电。**
- **⑩ eval**：跑制造业 KPI——见下。

### Zone C · Operationalization
- **⑪ slo_sla (slo gate)**：抓取成功率 SLO ≥85%、干预率 ≤1.5%、错误预算、FDE on-call。
- **⑫ runbook**：生成 runbook（含安全事件处置：e-stop 立即停用 agent）。
- **⑬ monitoring_drift**：振动/电流分布漂移检测（PSI > 0.2 告警）。
- **⑭ change_mgmt_training (🏭 works_council gate)**：works council 已在场 → 必须有共决审批记录，否则 deployment 可被吊销。
- **⑮ flywheel_productization**：把"人形机器人碰撞恢复"语料回流核心产品。

### Zone D · Handoff / Exit
- **⑯ ops_handoff** → **⑰ knowledge_transfer**（移交包：runbook+eval+SLO+模型卡+培训）→ **⑱ disengage (handoff_signoff gate)**：客户书面接受后 ≤120d 退场。

## KPI 实测（profile=manufacturing）

上传 `station_samples.jsonl` 到 Web UI 的 KPI tab，或：

```bash
fde-scope kpi <engagement-id> --samples examples/quickstart_manufacturing/station_samples.jsonl
```

5 个工位聚合后的典型输出（具体数值取决于聚合逻辑）：
- OEE ≈ 0.65-0.70（典型工厂水平，距 0.85 世界级有空间）
- MTBF ≈ 30-40h（焊装高、人形机器人低）
- 抓取率 ≈ 0.76（人形机器人拉低均值，距 DexNet 0.80 基准有空间）
- 干预率 ≈ 1.7%（人形机器人 3.2% 是主要改善目标）

## 合规 gate 实测（manufacturing profile）

在 Web UI 的 Gates tab 可见 10 个 gate。典型拦截：
- `fat_sat`：未填 FAT/SAT 记录 → blocker
- `functional_safety`：人形机器人协作工位 PLr=d 但未记录达成 PL → blocker
- `works_council`：现场有 works council 但无审批 → blocker
- `air_gap`：若现场 air-gapped 但 plan 允许遥测出网 → blocker

补齐后 gate 转绿，engagement 可推进。

## 这套场景的差异化

1. **数据栈可信**：OPC UA / MQTT-Sparkplug / ROS2 / MES / Historian，KPI 用真实公式与基准。
2. **SOP 完整**：18 阶段 + 工业 overlay，不漏 pre-engagement / ops / handoff。
3. **合规可执行**：功能安全 / CE / 工会 / air-gap 是能跑能拦的 gate，不是文档勾选。
4. **诚实**：人形机器人 telemetry / 车间语音 copilot at-scale 等无公开标准的部分，
   明确标为 per-vendor adapter 与路线图，不假装已解决。

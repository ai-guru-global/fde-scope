# quickstart_manufacturing — 具身机器人工厂端到端

一个虚构的整车厂车身车间：5 个工位（焊装 ×2 / 涂装 / 协作机器人装配 / 人形机器人装配），
每个工位一行生产 KPI 数据。演示 FDE Scope 的**工业 profile**：
制造业 KPI（OEE/MTBF/抓取率/碰撞率）+ 18 阶段 SOP + 工业 gate 叠加层。

## 数据说明（`station_samples.jsonl`，每行一个工位）

| 字段 | 含义 |
|---|---|
| availability/performance/quality | OEE 三分量（0-1） |
| uptime_hours / failures / repair_hours | MTBF / MTTR |
| good_units / started_units / defects / opportunities_per_unit | FPY / DPMO |
| grasp_successes / grasp_attempts | 抓取成功率 |
| tasks_succeeded / tasks_attempted | 任务完成率 |
| interventions / cycles | 碰撞/干预率 |

注意 `ASSY-HUMANOID-01`（人形机器人工位）：availability 0.78、抓取率 73%、干预率 3.2%——
典型的"新部署、还在爬坡"画像，会触发 bad case 与功能安全关注。

## 跑一遍（CLI）

```bash
pip install -e ".[dev]"

# 1. 列出 profiles —— 确认 manufacturing 可选
fde-scope profiles

# 2. 计算 KPI
fde-scope kpi <engagement-id> --samples examples/quickstart_manufacturing/station_samples.jsonl
#    （或先用 web UI，见下）

# 3. 启动一个工业 engagement，走完整 SOP
fde-scope engage init --customer "BMW Spartanburg" --profile manufacturing
fde-scope engage status <id>
fde-scope gate list --profile manufacturing
```

## 跑一遍（Web UI — 推荐）

```bash
fde-scope web              # 打开 http://127.0.0.1:8080
```

在 UI 里：
1. 新建 engagement，profile 选 `manufacturing`。
2. **KPI** tab → profile 选 `manufacturing`，上传 `station_samples.jsonl` → 看 OEE/MTBF/抓取率。
3. **SOP 阶段** tab → 看到 18 阶段（含工业-only 的 site_survey / FAT-SAT / 功能安全 / CE / 工会 / air-gap / 班次交接）。
4. **Gates** tab → 看到 10 个 gate；尝试推进到 deploy 阶段——会被 `fat_sat` gate 拦截（blocker: FAT 未执行）。
5. 在 `fat_sat` gate 补上 FAT/SAT 记录后重新校验 → 推进放行。

## 制造业语料锻造（报警日志 → 语料）

工业 agent 的语料是**报警/故障日志**（不是客服工单）。`alarm_corpus.jsonl`
是 12 条覆盖多数据源的真实形态报警（OPC UA / ROS2 / 安全PLC / MES / MQTT-Sparkplug / 视觉 / 历史库）：

```bash
fde-scope corpus \
  --input examples/quickstart_manufacturing/alarm_corpus.jsonl \
  --out reports/alarm_corpus_report.html
```

输出：12 条真实报警 → 612 条语料（12 真实 + 600 合成补盲 12 个故障类别缺口）。
这份报告就是 FDE 拿给厂长对齐「你的故障数据能用多少、缺什么」的交付物。

## 这套场景证明什么

- **制造业数据栈**：OPC UA / MQTT-Sparkplug / ROS2 / MES / Historian 连接器（stub），
  KPI 用真实公式（OEE=A×P×Q 世界级 85%、DPMO 3.4 = Six Sigma、抓取率 DexNet ~80% 基准）。
- **完整 SOP**：4 zones / 18 阶段，工业 overlay 自动启用。
- **可执行合规 gate**：ISO 13849 PL 等级判定、IEC 61508 SIL、ISO 10218、EU AI Act、
  德国 BetrVG 工会 gate、air-gap、FAT/SAT、班次交接——都能跑能拦。

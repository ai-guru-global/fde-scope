# D6 · 运维化 —— 判「SLO 是不是只剩一个目标值」

`06` Day 6 的这一组断言，全部围着同一件事转：**一条 SLO 由四件东西组成**
（目标值 + 测量窗口 + 错误预算 + 告警路由），而工具只认真第一件。
判分：**11 个机器项 + 1 个人工项**（可信度：工具实测，v0.1.0，2026-10-06）。
档案 `lab-d6`，profile `manufacturing`。9 项契约项 + 2 项写作项（`Runbook`、`值班交接卡`）。

## 跑起来

```bash
./check.sh D6
starter/Runbook.md starter/值班交接卡.md   # 要填满的两件，机器只判「TODO 删干净了 + 关键词在」
python -m fde_scope course check D6 --verbose
```

## 机器判了什么（11 项）

| # | id | 命令 / 面 | 判什么 |
|---|---|---|---|
| 1 | `slo-blocked` | `gate check lab-d6 --gate slo` | 退出码 **1**，打印 `❌ BLOCKED · gate=slo` 与 `🚫 未定义任何 SLO——错误预算/告警路由缺失` |
| 2 | `slo-no-route` | `engage slo add --name 自动解决率 --target 40%` | `✅ … 已定义 · target=40% · window=28d` **且** `⚠️ 未填告警路由`（两句话同一次输出里） |
| 3 | `slo-routed` | `slo add --name 'P95 响应延迟' --target '<=2s' --error-budget '月 30min' --alert-route '平台组 / 电话 / 5min'` | 出现 `已定义` |
| 4 | `slo-availability` | `slo add --name 可用性 --target 99.5% --error-budget '1.68h / 14d' --alert-route '值班 FDE / 企微群 / 15min'` | `已定义` + `window=` |
| 5 | `slo-count` | `engage slo list lab-d6 --json` | `slos` 长度 ≥ **3** |
| 6 | `slo-gate` | `gate check lab-d6 --gate slo --json` | `passed = true`（**注意第 7 行**：此时 warning 还没消） |
| 7 | `oee` | `kpi lab-d6 --samples fixtures/assy.jsonl --json` | `kpis.oee = 0.511056`（±1e-4） |
| 8 | `grasp` | 同上 | `grasp_success_rate = 0.7333333333333333`（教案写 73%） |
| 9 | `collision` | 同上 | `collision_intervention_rate = 0.03214285714285714` |
| 10 | `runbook` | `{{drafts}}/Runbook.md` | 无 `TODO`、≥ **800 字节**、含 `服务不可用/指标暴跌/数据异常/权限配额/上游依赖/回滚` 六个词（**写作项**） |
| 11 | `值班交接卡` | `{{drafts}}/值班交接卡.md` | 无 `TODO`，含 `当前状态 / 待办 / 已知风险 / 联系人` 四栏（**写作项**，判体积） |

第 1 项顺带留了个副作用，实测原话：`💡 已把这次阻塞沉淀为草稿 skill-d2b9fdee`。
**`gate check` 会写档案**——每撞一次 BLOCKED 就建一条草稿技能，所以这一天没有任何
`gate check` / `handoff` / `skill add` 被标成只读，反复手跑会在技能库里堆垃圾。

第 7/8/9 项的三个数来自 `fixtures/assy.jsonl` ——它是**一行聚合记录**（339 字节），
不是逐条样本：`oee = 0.78 × 0.72 × 0.91 = 0.511056`、`grasp = 1100/1500`、
`mtbf = 140/7 = 20.0`、`dpmo = 130/(1410×5)×10⁶ = 18439.716…`。
同一份数据还给出 `first_pass_yield 0.9078014184397163`、`task_completion_rate 0.8666666666666667`、
`mttr 3.0`——第 7~9 项只判其中三个，其余是你在 SLO 卡上要照着解释的上下文。

## 判不了的（1 项）

`盲测`（`ManualCheck`）：`06` / `03` §3 的 G6 ④「凌晨 2 点盲测——同事按文档能处理完」。**不进分母。**
机器能判文档**在不在**，判不了文档**能不能被陌生人执行**——这就是它为什么只能是人工项。

## 工具与门禁的差距

`03` §3 第 73 行对 G6 的原文分级：**①②④ blocker；③ warning**
（① Runbook 含 5 类事件且每类有回滚步骤；② SLO 卡含错误预算；③ 明确告警路由；④ 凌晨 2 点盲测）。

| G6 自查 | 语义 | 工具/lab 拦得住吗 |
|---|---|---|
| ① Runbook 5 类事件 + 每类回滚 | blocker | ⚠️ 半判：第 10 项只查六个词**在不在**。**"每类都有回滚步骤"判不了**——`starter/Runbook.md` 里 `回滚` 已经出现 5 次，六个事件词也都印好了，所以冷跑红**只因 TODO** |
| ② SLO 卡含错误预算 | blocker | ❌ **完全不判**。`SloGate.check` 只在 `ctx.slos` 为空时抛 blocker；`error_budget` 字段它一眼都不看（`fde_scope/engagement/operationalization.py:27-36`）。实测第 6 项：三条 SLO 里有一条预算为空，仍 `passed=true` |
| ③ 告警路由明确 | warning | ✅ 对得上：缺路由只进 `warnings`，实测 `SLO 缺告警路由: ['自动解决率']`，`passed` 不变（`operationalization.py:33-35`）——这正是 `03` 把③定成 warning 的工具印证 |
| ④ 凌晨 2 点盲测 | blocker | ❌ 工具判不了，落成 `ManualCheck`，见上 |

三处必须说清的边界，别把这一天判绿当成 G6 过了：

* **`passed=true` 不等于四件齐全**。第 6 项绿的时候 warning 还在。断言只查 `passed`，
  因为 `03` 的②③本来就是"工具放行、人判质量"；把 warning 也判成红会让门禁语义变味。
* **窗口和预算不自洽，没人管**。`--window` 默认 **28d**（`fde_scope/cli.py:844`），
  而 `build_slo_template()` 的可用性写的是 **14d**（`operationalization.py:92-116`，
  注释里就是那条算式 `14d × 24h × (1−99.5%) = 1.68h`）。第 4 项照着模板把 `1.68h / 14d`
  写进 `error_budget` 文本，实测 `slo list` 表格却是 `window 28d`——工具不校验预算与窗口的关系。
  **SLO 卡交出去之前，这个账你自己核。**
* **`slo add` 不去重**（`cli.py:851` 直接 `append`）。同名再写一次就是第二条，
  第 5 项的 ≥3 会因此虚高——所以名字写准比跑够次数重要。

## 卡住了怎么办

1. **第 2 项红、报 `Got unexpected extra argument(s)`** → 你在**手敲**这条命令。
   `--name 'P95 响应延迟'` 有空格就必须加引号；`course check` 走 argv 元组、不经 shell，
   所以只有你复制粘贴到终端时会炸。
2. **第 1 项红（BLOCKED 没出现）** → 档案里已经有 SLO 了。`engage slo list lab-d6 --json` 看条数；
   想重跑这一天，用**新的 `FDE_SCOPE_HOME`**（别删档案：`gate check` 已经往里写草稿技能了）。
3. **第 6 项绿但你以为过了 G6** → 回看上面那条"passed=true ≠ 四件齐全"。
   ② 错误预算这一版工具**不判**，`03` 却把它列成 blocker。
4. **第 7/8/9 项红** → 档案的 profile 不对。工单档案跑同一份工业样本**不报错**，
   只回一屏 `0.0`（实测 `{"intent_accuracy": 0.0, …}` 退出码 0）——静默错答。
   `kpi` 读的是**档案自己**的 profile 指标表，不是样本的形状。
5. **`KeyError: "Unknown profile: 'bogus'"`（退出码 1，整屏 traceback）** →
   `engage init --profile` **不校验取值**（`profiles/base.py:50` 才抛）。这条不是 lab 的正常路径，
   是你把 profile 名打错了；档案已经建出来，重开一个档案。
6. **第 10 项红、体积够** → 体积早就够（starter 有 2098 字节 > 800），红的是
   `TODO`（starter 里 24 处）或六个词被你删掉了。`grep -c TODO` 自查。
7. **想让机器也判②** → 得改工具（`SloGate.check` 加预算/窗口一致性检查），
   不是改 lab；`03` §3 的分级是 blocker，改代码前先读 AGENTS.md 的门禁契约条目并跑契约测试。

## 来源与可信度

| 内容 | 来源 | 可信度 |
|---|---|---|
| 11 项断言原话、BLOCKED 两行 + `skill-d2b9fdee`、`window=28d`、两条警告原话、`passed=true` 与 `warnings` 内容、`slo list` 表格三行、KPI 全部 8 个取值 | 本仓库一次性沙箱 `gate check` / `engage slo add` / `slo list` / `kpi` 实测 | **工具实测**（v0.1.0 · Python 3.12 · 2026-10-06 · macOS arm64） |
| ①②④ blocker、③ warning 的分级与四条原文 | `course-level-1/03` 第 73 行 | **教案原文** |
| `1.68h / 14d` 算式、模板默认值（availability 99.5% / reply_latency_p95 / bad_case_rate） | `fde_scope/engagement/operationalization.py:92-116` | 代码原文 |
| `SloGate` 只判 `ctx.slos` 是否为空、缺路由只进 warnings、`error_budget` 不判 | `operationalization.py:27-36` | 代码原文 |
| `--window` 默认 `28d`、`slo add` 无去重、告警路由警告文案 | `fde_scope/cli.py:844`、`cli.py:851`、`cli.py:854-855` | 代码原文 |
| ticket 档案跑工业样本返回全 0.0（退出码 0）；`--profile bogus` → `KeyError` 退出码 1 | 沙箱实测（`lab-d6t` / `lab-d6bogus`） | **工具实测** |
| `oee = A×P×Q`、`mtbf = uptime/failures` 等口径 | `fde_scope/profiles/manufacturing.py` 的 `compute_kpis` + 上述取值反算 | 代码原文 + 工具实测 |

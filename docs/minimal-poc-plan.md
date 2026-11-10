# 最小 POC 方案 — 用一个真实连接器替换一个 mock 案例

> **日期**：2026-11-10 · **状态**：可执行方案，尚未启动
> **来源**：`docs/workbench-gap-assessment.md` §3.4 与
> `docs/commercialization-roadmap.md` P3/P5 遗留项「用真实连接器跑通一个 POC，
> 替换 `seed_mock_engagements.py` 的至少一个案例」。
> **原则**：本文只写**能跑的命令**和**能证伪的验收标准**。凡是"看起来好了"
> 的说法都不算完成。

---

## 0. 为什么这是当前最大的风险

代码侧的技术债已经在 2026-11-10 清完（CI 四道检查全绿、覆盖率 91.07%、
1304 条测试、wheel 干净安装可用）。剩下的不是「代码有没有 bug」，而是
**「这套东西在一个真实客户环境里到底对不对」**——而这一点，仓库里没有任何
证据：十个 engagement 全部由 `examples/seed_mock_engagements.py` 脚本生成。

一个具体后果：`fde-scope eval` 的 `MockAgent` 是**按 `--accuracy` 参数用种子
随机数模拟**的（`fde_scope/eval/benchmark.py:136-144`）。也就是说：

```bash
fde-scope eval --agent mock --test-set x.jsonl --accuracy 0.9
# 跑出来的 "intent_accuracy: 0.9" 是你喂进去的，不是被测系统的
```

这不构成造假（参数名与文档都写明了 mock），但**任何在 mock 上得到的准确率
都不能作为 POC 结论**。POC 的第一个任务就是让这句话不再成立。

---

## 1. 目标与反目标

**目标（唯一的）**：

> 用一条真实数据链路，把一个 engagement 从 Zone A 推进到 Zone B 结束，
> 产出一个**可以给客户看、且每条数字都能追溯到原始数据**的语料报告 + KPI 报告。

**反目标（本 POC 明确不做）**：

- 不接生产系统写权限（只读）。
- 不做多租户/RBAC/SSO。
- 不训练/微调模型。
- 不追求全 18 阶段走通——Zone C/D 在 POC 阶段只需要 gate 能正确拦截。
- **不用 mock 或合成数据冒充真实数据**（这正是 2026-11 修掉的那个缺陷）。

---

## 2. 选哪个连接器：三条路径，按客户条件选

选型标准是**「客户手里已经有的东西」**，不是「我们实现得最花哨的连接器」。

### 路径 A · CSV / 工单导出（**推荐首选**）

| 项 | 内容 |
|---|---|
| 前置条件 | 客户能导出一份工单/客诉/日志表（CSV） |
| 连接器 | `csv`（零依赖、零网络、零凭据） |
| 命令 | `fde-scope connect --type csv --source <file.csv>` |
| 为什么推荐 | 最容易拿到，且**行数最重要**：见 §3 的样本量门槛 |
| 风险 | 数据可能已脱敏过度（占位符全是 `***`），导致语料没有信号 |

### 路径 B · MES / Historian（制造业，**次选**）

| 项 | 内容 |
|---|---|
| 前置条件 | 客户 IT 给一个只读 REST 端点 + Bearer token |
| 连接器 | `mes` / `historian`（`FDE_SCOPE_MES_BASE_URL` + `FDE_SCOPE_MES_API_TOKEN`，Historian 同构） |
| 为什么次选 | 工业客户的数据最值钱，但**接入周期最长**（防火墙、变更审批、只读账号申请） |
| 风险 | 被 IT 安全流程卡住，POC 变成一场采购流程演练 |

### 路径 C · OPC UA / MQTT-Sparkplug（现场实时 IO）

| 项 | 内容 |
|---|---|
| 前置条件 | 能进车间网段、拿到 OPC UA endpoint（`opc.tcp://host:4840`）或 broker 地址 |
| 连接器 | `opcua`（`--source opc.tcp://...`）、`mqtt_sparkplug`（`FDE_SCOPE_MQTT_USERNAME/PASSWORD`） |
| 为什么最后 | 真实 IO 已实现且有 mock + 真机测试，但**需要现场网段**，FDE 不在现场就跑不了 |
| 风险 | 「点了通」≠「语义对」：tag 对不对、单位对不对，需要在 `site_survey` 里逐个核 |

> **决策规则**：能在 1 周内拿到 ≥ 300 行真实 CSV → 走 A。拿不到但 IT 能开只读
> API → 走 B。两者都不行而客户坚持实时 → 走 C，并把 POC 周期预期改为 3–4 周。

---

## 3. 样本量门槛（**先算再动手**）

这是本方案最重要的一节，直接来自 2026-11 修掉的语料缺陷。

修复后，`corpus` 的留出集（eval + test）**只放真实样本**，比例是 10% + 10%。
因此：

| 真实行数 | eval | test | 留出合计 | 能得出的结论 |
|---|---|---|---|---|
| 20（quickstart） | 2 | 2 | **4** | **不能**做任何准确率结论 |
| 100 | 10 | 10 | 20 | 只能看趋势，不能进采购材料 |
| **300** | 30 | 30 | **60** | **POC 最低门槛** |
| 1000 | 100 | 100 | 200 | 可以对外报指标 |

**行动项**：在 POC 启动会上先问客户「你能导出多少行历史工单？」。
低于 300 行时，二选一：

1. 扩大时间窗口（从 3 个月拉到 12 个月）；
2. 明确把 POC 交付物降级为「语料覆盖度诊断」，**不承诺准确率指标**。

把这件事写在 POC 启动前，比一个月后向客户解释「4 条 eval 说明不了问题」便宜得多。

复现这条门槛：

```bash
fde-scope corpus --input <real.csv> --out /tmp/poc/corpus.html
# 看这行：✅ Held-out (eval+test): N real samples (eval a, test b)
# N < 60 时 CLI 会给黄色警告
```

---

## 4. 执行步骤（逐条可复现）

```bash
# 0. 环境（客户电脑或 FDE 笔记本；零 key、零 Docker）
pip install fde-scope            # 或 uv pip install fde-scope
fde-scope course doctor          # 应输出 ✅ G0 通过

# 1. 建 engagement，如实记录现场事实
fde-scope engage init --customer "<客户名>" --profile ticket   # 制造业用 manufacturing

# 2. 接真实数据（路径 A 示例）
fde-scope connect --type csv --source ~/poc/tickets.csv

# 3. 锻造语料——注意看留出集真实样本数
fde-scope corpus --input ~/poc/tickets.csv --out ~/poc/corpus.html
#   交付物：corpus.html（给人看）+ corpus_report.json（给机器看，与 HTML 同目录）

# 4. 用真实数据建 KPI 基线
#    坑：kpi 按「engagement 的 profile」选 KPI 口径，不看样本长什么样。
#    ticket 的 engagement 喂制造业样本 → 四项全是 0（已实测）。profile 要对上。
fde-scope kpi <eid> --samples ~/poc/station.jsonl            # manufacturing
#    ticket profile 的 KPI 在 web 控制台的 /api/kpi

# 5. 走 gate：让门禁真的拦一次，并记录被拦原因
fde-scope gate check <eid> --gate success_criteria --json
#   交付物：一次被拦截的真实记录 + 补救动作
#   补救后补齐（如 fde-scope engage criterion ...），再 advance

# 6. 审计链：复盘会重放 audit 流，证明每个阶段停留与门禁结果可查
fde-scope engage retrospective <eid> --json -o ~/poc/retro.md
```

**POC 期间必须真实发生的一件事**：至少一个 gate **拦住**推进，并且团队按
blocker 补齐后通过。只走绿灯的 POC 没有证明门禁引擎在工作。

> **已实测的坑（2026-11-10 用 wheel 干净安装跑通本方案的每一条命令）**：
> `kpi` 按 engagement 的 profile 选口径，**不看样本内容**。用一个 ticket
> engagement 去算制造业样本，会得到 `intent_accuracy / reply_adoption_rate /
> escalation_rate / avg_handle_time` 四项全 0 —— 不报错，只是答非所问。
> profile 选错时这个 0 很容易被当成「模型太差」。POC 前先确认两者一致。

---

## 5. 验收标准（可证伪）

| # | 标准 | 验证方式 | 不通过怎么办 |
|---|---|---|---|
| V1 | 数据来自真实系统，非导出脚本 | `corpus_report.json` 的 `real` ≥ 300 | 回到 §3 扩充数据 |
| V2 | 留出集真实样本 ≥ 60 | CLI 的 `Held-out (eval+test)` 行（<60 会显示黄色警告） | 同上 |
| V3 | 报告**没有**把合成占比藏起来 | `synthetic_ratio` 与 HTML 的「全库合成占比」一致 | 这是 bug，报 issue |
| V4 | 至少一次 gate 拦截被记录 | `retrospective` 的 gate 统计里有 blocked 记录，且 `gate check --json` 可复现同一组 blockers | 说明门禁没用上 |
| V5 | 每个 KPI 能追到原始行 | 抽 3 个 KPI 值，手工从 CSV 复算 | 记偏差，修 profile |
| V6 | 客户方一人独立跑完步骤 0–3 | 观察，不给提示 | 说明书不够，记下来 |

**V6 是本 POC 最值钱的一条**：它检验的不是代码，而是「这东西能不能交给别人用」。

---

## 6. 时间盒（2 周，单人）

| 周 | 内容 | 出口条件 |
|---|---|---|
| W1 上半 | 启动会（§3 的样本量问题）+ 拿数据 + V1/V2 达标 | 数据在手，≥300 行真实 |
| W1 下半 | connect → corpus → kpi，产出第一版报告 | V3/V5 通过 |
| W2 上半 | 走 gate（含一次真实拦截）+ 复盘重放审计流 | V4 通过 |
| W2 下半 | 客户方独立复跑（V6）+ 复盘 + 决定是否继续 | 获得一次真实客户反馈 |

---

## 7. 常见失败模式（提前写死，避免临场找借口）

| 失败模式 | 早期信号 | 应对 |
|---|---|---|
| 数据拿不到 / 脱敏过度 | 第一周结束仍是样本 CSV | 触发 §3 降级为「覆盖度诊断」 |
| IT 流程卡死（路径 B/C） | 第三周还开不了防火墙 | 换路径 A，并把 B/C 作为二期 |
| 客户以为要「训练一个模型」 | 启动会问「准确率能到多少」 | 当场说清：POC 产出是**可审计的诊断报告**，指标取决于数据量 |
| 用 mock 数字汇报 | 有人引用 `eval --accuracy` 的结果 | 引用 §0 的那段代码，说明它不测系统 |
| POC 变成定制开发 | 客户开始提「能不能加个功能」 | 回到本文反目标清单 |

---

## 8. 完成后要更新的东西

1. `docs/commercialization-roadmap.md` 勾掉「用真实连接器跑通一个 POC」。
2. `README.md` 的 mock 数据章节：标注哪个案例已由真实 POC 替换。
3. 若 V5 暴露 KPI 口径问题，补 `fde_scope/profiles/` 的测试。
4. 若 V6 失败，把卡住的地方写成 `docs/user-guide.md` 的 FAQ。

---

## 附：本方案已按原文逐步实跑

2026-11-10 用**干净 venv 安装的 wheel**（不是源码 checkout）把 §4 的六条命令
逐条跑通，结论：

| 步骤 | 结果 |
|---|---|
| 0 `course doctor` | ✅ G0 通过 |
| 1 `engage init` | ✅ `eng-poc-dryrun-ticket`，15 个可见阶段（ticket profile） |
| 2 `connect --type csv` | ✅ 20 行 · 9 类别 · 写出 `samples/preview.json` |
| 3 `corpus` | ✅ 415 条，**留出集 4 条真实**（触发 §3 的 <60 警告，符合预期） |
| 4 `kpi` | ✅ （profile 对上后）OEE 0.7236 · 抓取率 0.7931 · 干预率 0.0108 |
| 5 `gate check --gate success_criteria` | ✅ **被拦**，exit 1，blockers 具体可读 |
| 6 `engage retrospective --json -o` | ✅ 3 条审计事件 · `timeline_consistent: true` |

这轮实跑改了本文两处：`engage start` → **`engage init`**、
`audit export` → **`engage retrospective`**，并补上 `kpi` 需要 engagement id、
且 profile 必须与样本口径一致（否则四项全 0）。方案里其余部分未改。

本文所有命令均来自当前 master（2026-11-10，已推送 `c3b7e40`，CI 全绿）。
除了 §3 依赖 2026-11 的语料修复外，没有一项需要新开发。
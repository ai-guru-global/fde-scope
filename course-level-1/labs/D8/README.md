# D8 · 变现日 —— 判「这些数字今天还能不能当场重跑」

`06` Day 8 不产出新数据，它产出**三套包装**：求职版、汇报版、接单版。
这一天唯一可机器化的要求是 `06` 反复讲的那句反面——**"我做了"后面要跟"数据显示"**，
而"数据显示"必须是**当场敲得出来的命令**。所以 D8 判的是链路可再生，不是文案漂亮。

判分：**8 个机器项 + 2 个人工项**（可信度：工具实测，v0.1.0，2026-10-06）。
档案 `lab-d8`，profile `ticket`。7 项契约项 + 1 项写作项（`作品集索引`）。

## 跑起来

```bash
./check.sh D8
starter/作品集索引.md      # 唯一要写完的那件
python -m fde_scope course check D8 --verbose
```

## 机器判了什么（8 项）

| # | id | 命令 / 面 | 判什么 |
|---|---|---|---|
| 1 | `corpus` | `corpus --input <共享 fixture> --out {{out}}/main/t.html` | `✅ Corpus forged: 20 real + 395 synthetic = 415 total` |
| 2 | `deploy-dry-run` | `deploy --tenant lab-d8 --dry-run` | `Deployment plan assembled` + `Permissions` + `Sandbox: docker` 三张清单同屏 |
| 3 | `deploy-with-corpus` | `deploy … --corpus {{out}}/main/corpus_report.json --agent 'triage:工单分诊:qwen-max'` | `✓ corpus_search 415 forged items (real=20, synthetic=395)` 与 `✓ corpus_coverage category distribution + remaining gaps` |
| 4 | `deploy-bad-spec` | `deploy --tenant x --dry-run --agent bad-spec` | 退出码 **2**，`Invalid agent spec: bad-spec (expected name:role[:model])` |
| 5 | `flywheel-dry` | `flywheel --agent lab-d8 --dry-run` | `DRY-RUN would attach flywheel to agent=lab-d8` |
| 6 | `flywheel-jobs` | `flywheel --agent lab-d8` | `weekly_incremental_retrain` + `monthly_full_eval` + `cron=0 2 * * 1` |
| 7 | `gate-map` | `gate list --profile manufacturing` | 表里同时出现 `success_criteria`、`handoff_signoff`、`works_council`、`air_gap`（实测 **10 行**：🏢 3 + 🏭 7） |
| 8 | `作品集索引` | `{{drafts}}/作品集索引.md` | 无 `TODO`、≥ **800 字节**、含 `证据`（**写作项**） |

第 1→3 项是一条链，不是两条断言：`corpus` 落出 `corpus_report.json`（与 `--out` **同目录**，
`fde_scope/cli.py:222`），`deploy --corpus` 才能把它绑成两个工具。第 3 项打印的
`415 forged items (real=20, synthetic=395)` 与第 1 项的 `20 real + 395 synthetic = 415` **是同一个账**——
作品集里那个"415 条语料"当场能自证，这就是 D4 第 4 项（合成比例如实标注）在交付端的收口。

第 6 项打印的原话带着一条免责声明：
`🔄 retrain jobs (descriptors only — no scheduler runs inside this CLI)`，
两个任务是 `weekly_incremental_retrain: cron=0 2 * * 1 min_new_samples=200 kind=incremental` 和
`monthly_full_eval: cron=0 3 1 * * min_new_samples=0 kind=full_eval`。
**汇报版那一页要把 cron 抄进去**：飞轮是"上线之后怎么持续变好"，写"我们会持续优化"不算。

## 判不了的（2 项）

* `三套包装`（`ManualCheck`）：求职版（简历 3–5 行含数字 + STAR 故事 3 个）｜汇报版一页纸｜接单版服务清单 + 案例页。
  句式见 `10`。检查点：**每个数字都有证据链接，每条"我做了"后面跟一句"数据显示"**。
* `结业门`（`ManualCheck`）：G1–G7 至少 6 关通过｜10 分钟结营答辩｜等级已判定。
  跨日累计不在单条 lab 里判——用 `python -m fde_scope course check all` 逐日核对机器项，
  再由人（或 89 个机器项的合计）定级。**诚实标注为 0 一票否决**（`03`）。

## 工具与门禁的差距

`03` §3 第 75 行原文：G8 四条 **全部是 blocker**（① G1–G7 至少 6 关通过 ② 作品集索引完整（8 件）
③ 完成结营答辩 ④ 作品集等级判定完成）——这是八天里唯一"②③④ 也升 blocker"的一天。

| G8 自查 | 语义 | 工具/lab 拦得住吗 |
|---|---|---|
| ① G1–G7 至少 6 关通过 | blocker | ❌ 本条 lab 判不了。它是**跨日**统计，只有 `course check all` 能给分母；单跑 D8 全绿不等于你过了 6 关 |
| ② 索引完整 8 件 | blocker | ⚠️ 半判：第 8 项查 `TODO` / `证据` / ≥800 字节，**不数行数**。starter 里 8 行是印好的（2923 字节，`证据` 出现 9 次），删掉两行照样绿——**"8 件齐全"要人看** |
| ③ 完成结营答辩 | blocker | ❌ 工具判不了，落成 `ManualCheck` |
| ④ 等级判定完成 | blocker | ❌ 同上，且它依赖 ① |

另外三处实测边界：

* **"零副作用"是真的，可以当场演示**：跑完 `corpus` + 两次 `deploy --dry-run` + 两次 `flywheel`，
  数据根目录里只多出 3 个文件（`engagements/lab-d8.json`、`main/corpus_report.json`、`main/t.html`）——
  **`deploy --dry-run` 和 `flywheel` 一个字节都不写**，manifest 只打印在屏上。
  接单版可以让客户当场敲，不必担心污染环境。
* **`deploy` 不连引擎也算"装配成功"**。无 key 时它先打印
  `LLM disabled (FDE_SCOPE_MIMO_API_KEY / FDE_SCOPE_LLM_* not set) — falling back to rule-based mode.`
  再照常输出计划。这是诚实降级（凭证只走环境变量，`AGENTS.md` 不变式 3），
  但**别把它当"部署成功"**：`started: false` 就写在 manifest 里。
* **第 7 项用 slug 而不是中文名**，因为招聘方会照你写的命令去跑；`03` 第 28 行就是这张对照表
  （课程 9 关 G0+G1–G8 ↔ 工具 10 门禁）。作品集里写"过了 SLO 关"要能落到 `gate check <eid> --gate slo`。

## 卡住了怎么办

1. **第 3 项红、第 1 项绿** → `--corpus` 指错了。`corpus_report.json` 永远落在 `--out` **同目录**
   （`cli.py:222`），不是当前目录，也不是你指定的 html 名。
2. **第 4 项红** → 你改了 `--agent` 的值。这条断言的是**拒绝**（退出码 2），
   格式必须三段或两段：`name:role[:model]`。
3. **第 2/3 项里数字漂了** → 共享 fixture 被换过。第 1、3 项都锁 `415 / real=20 / synthetic=395`，
   这四个数在 `labs/_shared/fixtures/sample_tickets.csv`（20 行）+ 合成器上；
   先 `python -m fde_scope --version` 对版本（v0.1.0），跨版本合成比例会漂。
4. **第 6 项红** → `flywheel` 不带 `--dry-run` 才打印两个 cron；带 `--dry-run` 只有那一句 DRY-RUN。
   两条都有断言（第 5、6 项），别混。
5. **第 8 项红、体积早就够** → 2923 > 800，红的是 **26 处 `TODO`**。`grep -c TODO` 自查。
6. **想让机器也数"8 件齐全"** → 得给课程加一条按行计数的断言，
   或把索引改成结构化输入（`--json` 那类）。**不要**为了变绿去改 `03` 的 blocker 分级。

## 来源与可信度

| 内容 | 来源 | 可信度 |
|---|---|---|
| 8 项断言原话：`Corpus forged: 20 real + 395 synthetic = 415 total`、`Sandbox: docker` / `Permissions:` / `Deployment plan assembled (dry-run / core-only)`、`✓ corpus_search … 415 forged items (real=20, synthetic=395)`、`✓ corpus_coverage category distribution + remaining gaps`、`Invalid agent spec: bad-spec (expected name:role[:model])`+退出码 2、`DRY-RUN would attach flywheel to agent=lab-d8`、两个 cron 全行、`gate list` 10 行与 🏢/🏭 标记 | 一次性沙箱 `FDE_SCOPE_HOME=/tmp/probe-d8b-home` 全流程实测 | **工具实测**（v0.1.0 · Python 3.12 · 2026-10-06 · macOS arm64） |
| dry-run / flywheel 零落盘（沙箱只剩 3 个文件）、`LLM disabled … rule-based mode` 降级行、manifest 里 `started: false` | 沙箱 `find` + 输出实测 | **工具实测** |
| 作品集索引 starter 2923 字节、TODO 26 处、`证据` 9 次、8 行印好 | `wc -c` / `grep -c` 对 `labs/D8/starter/` | 工具实测 |
| Day 8 六条任务项与"产出 8｜作品集三套包装 + 结营答辩"、常见坑（全是"我做了"没有"数据显示"、答辩超时） | `course-level-1/06` 第 202 行起 | **教案原文** |
| G8 四条 + ① blocker、②③④ blocker | `03-评估体系与通关门禁.md` 第 75 行 | **教案原文** |
| 课程 9 关 ↔ 工具 10 门禁对照 | `03` 第 28 行 | **教案原文** |
| 凭证只走环境变量、不落盘 | `AGENTS.md` 不变式 3、`fde_scope/llm.py` | 项目约束原文 |
| `corpus_report.json` 与 `--out` 同目录 | `fde_scope/cli.py:222` | 代码原文 |

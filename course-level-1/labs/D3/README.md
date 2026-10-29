# D3 · 接数据 —— 判「现场事实和体检数字对不对得上」

`06` Day 3 的产出是数据体检报告。这一天 lab 干两件 D1 干不了的事：
**把工业门禁 `site_survey` 的阻塞/警告边界跑出来**，以及**用两份不同数据
证明「覆盖率缺口」是可数的**。

判分：**13 个机器项 + 1 个人工项**（可信度：工具实测，v0.1.0，2026-10-06）。
档案 `lab-d3`，profile `manufacturing`。12 项契约项 + 1 项写作项（`体检报告`）。

## 跑起来

```bash
./check.sh D3
starter/数据体检报告.md     # §0 是「先猜后看」，先写完猜测再跑命令
python -m fde_scope course check D3 --verbose
```

必须用 `manufacturing` profile。ticket 档案上跑同一道门也返回 `✅ PASS`，
但 `--json` 里是 `notes: ["gate 'site_survey' not applicable to profile"]`——
**空过**，不是通过工业门（实测，见下）。

## 机器判了什么（13 项）

| # | id | 命令 | 判什么 |
|---|---|---|---|
| 1 | `site-blocked` | `gate check lab-d3 --gate site_survey` | **退出码 1**，`现场勘察缺失` + `资产清单为空` |
| 2 | `site-minimal` | `engage site set lab-d3 --location 总装车间 A 线` | `现场事实已记录` + `资产 0 项` |
| 3 | `site-pass-warning` | 再次 `gate check` | **退出码 0**：`PASS` 与 `资产清单为空` **同时出现** |
| 4 | `site-full` | `engage site set … --network PROFINET --network OPC UA 汇聚 --shift-count 3 --ot-it-separated --assets-file fixtures/assets.csv` | `资产 5 项` + `班次 3` |
| 5 | `site-warnings-clear` | `gate check … --json` | `warnings` 长度 = **0**（补齐之后警告归零） |
| 6 | `site-show` | `engage site show lab-d3` | 回读成五行原话：`OT/IT 隔离: True`、`网闸/气隙: False`、`班次: 3`、`网络: PROFINET, OPC UA 汇聚`、`资产: 5 项` |
| 7 | `ticket-corpus` | `corpus --input <lab 自带工单 CSV>` | `PII entities masked: 2` |
| 8 | `pii-count` | — | `corpus_report.json` 的 `pii_entities_masked == 2`，与第 7 项打印一致 |
| 9 | `dropped` | — | `dropped == 0`：这 20 条没有重复、没被质量门槛丢掉 |
| 10 | `alarm-corpus` | `corpus --input fixtures/alarm_corpus.jsonl` | `12 real + 560 synthetic = 572 total` + `Coverage gaps` |
| 11 | `alarm-gaps` | — | `coverage.gaps` 长度 = **12**（12 个类别，每类都薄） |
| 12 | `alarm-target` | — | `coverage.category_counts.急停事件 == 1` |
| 13 | `体检报告` | — | `{{drafts}}/数据体检报告.md` 无 `TODO` 且 ≥ 600 字节（**写作项**） |

第 1 项和第 3 项是这一天的重点：屏幕上两句都在，但**只有一句是 blocker**。
`SiteSurveyGate`（`fde_scope/engagement/pre_engagement.py:15-32`）只有一条
blocker——`if not site.location`；`资产清单为空` 和 `多班次现场但未记录网络拓扑`
是 warnings。所以「填个地点就能过现场门」不是 bug，是工具的下限。

第 5 项证明反向也成立：警告是真的会归零，不是永远挂着糊你眼睛。
第 6 项把「现场事实」变成可交接的口径——交接时别人问「有气隙吗」，
你答的是 `网闸/气隙: False`，不是记忆。

第 11/12 项对应 `06` G3 的第 ④ 条（≥3 条质量风险，warning 级）：
12 个缺口是**数出来的**，不是形容词。第 12 项特意指着急停事件——
唯一一条真实样本，安全相关的类别最薄。

## 判不了的（1 项）

`体检结论`（`ManualCheck`）：`06` G3 四条自查——「字段表含类型与缺失率｜
PII 清单带处置方式｜有明确结论（写『待定』= 未达）｜≥3 条质量风险」。**不进分母。**

## 工具与门禁的差距

| G3 自查（`03` §3） | 语义 | lab 判了吗 |
|---|---|---|
| ① 字段清单含类型/缺失率 | blocker | ❌ 判不了。第 7～9 项只证明 PII 与 dropped 两个数对得上，字段表在写作项里 |
| ② PII 清单与处置建议 | blocker | ⚠️ 半判：第 7/8 项判「工具脱敏了几个实体」，**没判你写了什么处置** |
| ③ 明确结论「能做/不能做/有条件能做」 | blocker | ❌ 判不了（语言产出）。第 13 项只保证那一节没留 `TODO` |
| ④ ≥3 条质量风险 | warning | ✅ 第 11 项给了可数的 12 |

另有两件事必须写清楚，否则这一天容易被误读成「门过了」：

* **`PII?` 列 ≠ `PII entities masked`**。前者是 `connect` 打印的**列级猜测**
  （D1 第 4 项），后者是 `corpus` **实际脱敏掉的实体条数**。两个数不同来源，
  别在体检报告里把它们当同一个。（`starter/数据体检报告.md` 里也钉了这一条。）
* **profile 决定这道门存不存在**。`site_survey` 带 `industrial_only = True`，
  ticket 档案上是 `notes` 里的 `not applicable`。`03` §1.1 那句
  「9 个课程门 ≠ 10 个工具门」在这里是具体的：**不适用 ≠ 通过**。

## 卡住了怎么办

1. **第 3 项红、报了 BLOCKED** → 你手跑过 `site set` 改了档案？判分用沙箱里的
   `lab-d3`，但如果你自己在真实 HOME 下建过同名档案，删掉它再判。
2. **第 6 项 `资产: 5 项` 变成 `资产: 0 项`** → `--assets-file` 是相对当前目录解析的。
   手跑时写全路径；lab 内部传的是 `fixtures/` 绝对路径，所以判分不该因此红。
3. **`--network` 只留了一个** → 这个选项是**可重复**的，`PROFINET` 和
   `OPC UA 汇聚` 要分两次给；`OPC UA 汇聚` 含空格，shell 里加引号。
4. **第 1 项的两个 needle 只出现一个** → `export COLUMNS=200`。窄终端会把
   「资产清单为空」这类中文行折行，字符串匹配就断了（lab 内部已设）。
5. **`alarm_corpus.jsonl` 报解析错误** → `corpus --input` 的分流规则写在
   `fde_scope/cli.py:259-262`：**`.csv`（或一个目录）**走 CSV 连接器，
   其余按 JSON 数组 / 逐行 JSONL 解析。把 `.jsonl` 改名成 `.csv` 会走错分支。
   顺带：D1 那条 `CSV source not found` 的退出码 2 也出自这里，不是别处。

## 来源与可信度

| 内容 | 来源 | 可信度 |
|---|---|---|
| 13 项断言原话、`PASS` 同时带警告、`warnings=[]`、五行 site show | 本仓库 `course check D3` 实测 | **工具实测**（v0.1.0 · Python 3.12 · 2026-10-06 · macOS arm64） |
| ticket 档案上 `site_survey` 的 `not applicable to profile` | 一次性沙箱实测（`--json` 原文） | **工具实测** |
| 只有 location 是 blocker，资产/拓扑是 warning | `pre_engagement.py:15-32` 原文 | 代码原文 |
| `industrial_only = True` | `pre_engagement.py:20` | 代码原文 |
| 体检报告六项勾选、先猜后看、结论写「待定」= 未达 | `06` §4 Day 3 | **教案原文** |
| G3 四条自查与 blocker/warning 分级 | `03` §3 | **教案原文** |
| 「9 个课程门 ≠ 10 个工具门」 | `03` §1.1 | **教案原文** |
| 12 个类别、每类目标 100 条（目标值在 D4 断言） | `corpus_report.json` 实测 | **工具实测** |

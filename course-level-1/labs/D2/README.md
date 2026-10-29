# D2 · 定边界 —— 判「委托单是不是真能验收」

`06` Day 2 的产出是一页客户委托单。这一天 lab 判的不是你写得好不好，
而是**工具在哪些地方会放你过去**——因为 G2 的四条自查里，工具只拦得住两条。

判分：**14 个机器项 + 1 个人工项**（可信度：工具实测，v0.1.0，2026-10-06）。
档案 `lab-d2`，profile `ticket`。其中 13 项是契约项（冷跑就该绿），
第 14 项 `委托单` 是写作项（冷跑必红，见下）。

## 跑起来

```bash
./check.sh D2
starter/委托单.md          # 这份要你先写完，写完再判才全绿
python -m fde_scope course check D2 --verbose
```

## 机器判了什么（14 项）

| # | id | 命令 | 判什么 |
|---|---|---|---|
| 1 | `blocked-empty` | `gate check lab-d2 --gate success_criteria` | **退出码 1**，打印 `BLOCKED` + `成功标准未定义` |
| 2 | `sponsor-collapse` | 同上 | 同一次输出里还有 `sponsor` + `要求 ≥2` —— 空档案上两个 blocker 一起响 |
| 3 | `empty-criterion` | `engage criterion add lab-d2 --text`（空值） | **退出码 2**，`成功标准不能为空` |
| 4 | `vague-criterion` | `engage criterion add lab-d2 --text 提升体验` | 退出码 **0**（接受了！），但打印 `没有数字` 与 `门禁 G2 会打回` |
| 5 | `measurable-1` | `… --text 自动解决率 ≥ 40%` | `成功标准 2 条已记录` |
| 6 | `measurable-2` | `… --text 人工升级率 ≤ 10%` | `成功标准 3 条已记录` |
| 7 | `measurable-3` | `… --text 首次响应 ≤ 5min` | `成功标准 4 条已记录` |
| 8 | `duplicate` | 再写一遍 `自动解决率 ≥ 40%` | **退出码 2**，`重复的成功标准` |
| 9 | `sponsor-1` | `engage stakeholder add … --sponsor`（客服总监） | `sponsor` + `当前发起人 1 位（要求 ≥2` |
| 10 | `sponsor-2` | 同上（数字化负责人） | `当前发起人 2 位` |
| 11 | `criteria-count` | `engage criterion list lab-d2 --json` | `success_criteria` 长度 = **4**（3 条带数字 + 第 4 项那条形容词） |
| 12 | `gate-passes-anyway` | `gate check … --gate success_criteria --json` | `passed == true` |
| 13 | `warning-kept` | 同上 | `warnings` 长度 ≥ 1 —— 放行不等于没意见 |
| 14 | `委托单` | — | `{{drafts}}/委托单.md` 里没有 `TODO` 且 ≥ 600 字节（**写作项**） |

第 5～7 项那三个数字是这一天的核心：**它们依次是 2、3、4，不是 1、2、3**。
计数把第 4 项那条形容词也算了进去。所以「成功标准 3 条已记录」这句话
在屏幕上出现时，你手上其实只有 2 条能被验收的标准。断言把这个坑钉死。

## 判不了的（1 项）

`委托单质量`（`ManualCheck`）：`06` G2 的四条自查——「≥3 条全可度量（禁『提升体验』类）
｜≥2 发起人｜写了放弃标准｜≤1 页」。**它不进分母。**

## 工具与门禁的差距

| G2 自查（`03` §3） | 语义 | 工具拦得住吗 |
|---|---|---|
| ① 成功标准 ≥3 条且**全部可度量** | blocker | ❌ **只拦「一条都没有」**。实测：1 条形容词 + 2 位发起人 → `✅ PASS`（见下） |
| ② 干系人含 ≥2 位发起人 | blocker | ✅ 拦得住（第 2、9 项：`仅有 N 个 sponsor——要求 ≥2`） |
| ③ 有「放弃标准」 | warning | ❌ 工具里没有这个字段，无法判 |
| ④ 委托单 ≤1 页（超 2 页 blocker） | warning | ❌ 判不了页码 |

代码依据：`SuccessCriteriaGate.check`（`fde_scope/engagement/pre_engagement.py:41-52`）
只有两条 blocker——`if not ctx.success_criteria` 与 `if len(sponsors) < 2`；
**没有数量阈值、没有可度量判断**。「没有数字」那句是 `criterion add` 打的**警告**，
不进 gate 结论（`fde_scope/cli.py:769` 一带）。

我另外实测了三个边界来确认这不是我读错代码（工具实测，同一版本同一台机器）：

| 档案内容 | gate 结论 |
|---|---|
| 3 条**全形容词** + 2 sponsor | `passed=true`，1 条 warning |
| 2 条带数字 + 2 sponsor | `passed=true`，0 warning |
| 1 条形容词 + 2 sponsor | **`passed=true`** |

所以第 12 项 `gate-passes-anyway` 判绿的时候，G2 ① 其实**没过**。
这一天门禁自查要靠你自己数，工具的 ✅ 帮不了你——这正是 `03` §1.1
说那两套门禁不是一套的原因。

顺带一个真实副作用：`gate check` **不是只读命令**。实测每次 BLOCKED 都新增一条
草稿（`已把这次阻塞沉淀为草稿 skill-xxxxxxxx`）；同一档案连跑 3 次 → `skill list`
里 3 条 `success_criteria,gate-blocked` 草稿，**不去重**。这是设计（阻塞即素材），
但你调门禁时它只涨不消，`skill review` 得自己清。lab 的判分不受影响：
沙箱每次新建（`verifier.py::LabWorkspace.create`），也正是因此，
判分器绝不给 `gate check` 标 `read_only`（标了会命中缓存、漏判这条副作用）。

## 卡住了怎么办

1. **第 12/13 项红、前面全绿** → 大概率是你手跑过 `criterion add` 把沙箱外的档案改了。
   lab 用的是沙箱里的 `lab-d2`，与你自己档案同名也会隔离；但若你用了
   `--id lab-d2` 在真实 HOME 下跑，请删掉那份档案再判。
2. **`成功标准 2 条已记录` 变成了 `3 条`** → 你在这个档案上多写了一条。
   这三项断言的是**累计计数**，对条数敏感，不是我对齐错了。重新 `course check D2`。
3. **`--text` 带空格的标准没生效** → `自动解决率 ≥ 40%` 里有空格，shell 里要加引号：
   `--text "自动解决率 ≥ 40%"`。lab 内部直接传 argv，不走 shell，所以判分不会因此红。
4. **委托单那项一直红** → 它判的是**数据根目录**下的 `course-labs/D2/委托单.md`
   还有没有 `TODO`，不是 `starter/` 里那份原件。`course doctor` 打印这次命中的是哪条规则。
5. **想清警告但不想动档案** → `gate check <id> --gate success_criteria --json`，
   `warnings` 就是那条 `sponsor 未填写可度量的 success_metric`；
   补掉它用 `engage stakeholder add … --success-metric "…"`（选项见 `--help`）。

## 来源与可信度

| 内容 | 来源 | 可信度 |
|---|---|---|
| 14 项断言原话、退出码 1/2、`成功标准 2/3/4 条已记录`、`passed=true` | 本仓库 `course check D2` 实测 | **工具实测**（v0.1.0 · Python 3.12 · 2026-10-06 · macOS arm64） |
| 「1 条形容词 + 2 sponsor 也 PASS」等三个边界 | 一次性沙箱实测（本 README 上一节表格） | **工具实测** |
| G2 四条自查与 blocker/warning 分级 | `03-评估体系与通关门禁.md` §3 | **教案原文** |
| 委托单六项勾选、≤1 页、双发起人、放弃标准 | `06` §4 Day 2 | **教案原文** |
| 工具门只有两条 blocker | `fde_scope/engagement/pre_engagement.py:41-52` | 代码原文 |
| `gate check` 会沉淀草稿 skill | 实测输出原文 | **工具实测** |
| Sponsor Collapse 这个词的出处与 18 阶段里的位置 | `fde_scope/engagement/phases.py:76` | 代码原文 |

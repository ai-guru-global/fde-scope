# D5 · 验证与评估 —— 判「这个分数是怎么来的，你能不能说清」

`06` Day 5 的产出是"原型证据 + 评估结果 + Top3 bad case + 一页验证记录"。
这一天 lab 只做一件机器做得到、又最容易被糊过去的事：
**拿两份只差一个字段（`expected_category`）的测试集，把同一个 mock 跑两遍**，
看你能不能解释"1.000 变 0.000"。分数本身不是证据，分数的**来路**才是。

判分：**9 个机器项 + 1 个人工项**（可信度：工具实测，v0.1.0，2026-10-06）。
档案 `lab-d5`，profile `ticket`。8 项契约项 + 1 项写作项（`验证记录`）。
两份测试集都在 `fixtures/` 里，不需要 LLM、不需要 key。

## 跑起来

```bash
./check.sh D5
starter/验证记录.md        # 唯一要写的那件
python -m fde_scope course check D5 --verbose

# 手跑（lab 用的就是这两条）
python -m fde_scope eval --agent mock --test-set fixtures/test_set.jsonl --json
python -m fde_scope eval --agent mock --test-set fixtures/test_set_labeled.jsonl --json
```

## 机器判了什么（9 项）

| # | id | 命令 / 面 | 判什么 |
|---|---|---|---|
| 1 | `unknown-agent` | `eval --agent bogus …` | **退出码 2** 且打印 `Unknown agent`（实测原话：`Unknown agent: 'bogus' — use 'mock' (rule-based) or 'mimo' (MiMo LLM).`）——写错名字不会被静默改成 mock |
| 2 | `unlabeled-accuracy` | 无标签集 + `--json` | `metrics.intent_accuracy == 1.0`（**5 条里没有一条带 `expected_category`**） |
| 3 | `labeled-accuracy` | 有标签集 + `--json` | `metrics.intent_accuracy == 0.0`（4 条全带标签） |
| 4 | `escalation` | 无标签集 + `--json` | `metrics.escalation_rate == 0.2` —— 5 条里 `c-003` 一条 `escalated: true` |
| 5 | `bad-case-id` | 同上 | `bad_cases.cases.0.case_id == "c-003"`，原文 `这家店的服务太差了！我要投诉` |
| 6 | `bad-case-category` | 同上 | `bad_cases.by_category["门店投诉"] == 1`（失败**按类别聚合**，不是平铺一条） |
| 7 | `recommendation` | 有标签集（人读输出） | 打印 `Top bad case category: 退款售后` + `建议补充「退款售后」类语料 ~50 条，重点覆盖失败模式。` |
| 8 | `reproducible` | 无标签集跑两遍 | `DeterminismCheck`：两次的 `metrics` 必须一致（实测两份 `--json` **逐字节相同**） |
| 9 | `验证记录` | `{{drafts}}/验证记录.md` | 无 `TODO`、≥ 400 字节（**写作项**，冷跑必红） |

### 第 2、3 项是这一天的核心，不是两个巧合的数字

判分函数只有几行（`fde_scope/eval/metrics.py:90-99`）：

```python
if not case.expected_category:
    return 1.0                       # 没信号 → 判为对
return 1.0 if case.expected_category in case.agent_reply else 0.0
```

所以 **1.000 是 vacuous pass**（无标签＝无信号＝全对），**0.000 也不是模型变差**：
mock 的回复是 `已为您处理：<原文>…（mock 回复）`，里面**不含类别名**，子串判分
恒为 0。同一个 agent、同一批数据，只因为多写了一个字段，分数从满分掉到零分。
`06` Day 5 让你"先删掉 `expected_category` 跑通"，就是让你亲眼看到这对数字，
然后**在答辩里说清它意味着什么**——说"准确率 100%"是事故，说"这个指标在 mock 上
没有分辨力"才是产出。

判的是**两条断言同时成立**，所以"我把标签删了刷分"这条路走不通：删标签 ⇒ 第 3 项红；
留标签 ⇒ 第 2 项红。要全绿，只有理解它、并在验证记录里写出它。

### 第 5、6、7 项：坏例子必须落到"哪一条 / 哪一类 / 下一步做什么"

`bad_cases` 不是把低分样本倒出来，它有三级（实测，无标签集）：
`cases[0]` 指到 `c-003`；`by_category` 给出 `{"门店投诉": 1}`；
`recommendation` 给动作。推荐条数不是拍的：
`n = min(max(count × 30, 50), 300)`（`fde_scope/eval/bad_case_miner.py:87-89`），
1 条失败 ⇒ 下限 50。有标签集 4 条失败、四类各 1 条并列，`top_category` 仍是
`退款售后`——并列时取**先出现的那一类**（`Counter.most_common` 的插入序，
`bad_case_miner.py:63-64`），不是字典序、也不是随机。

失败原因有优先级（`bad_case_miner.py:77-85`）：
`intent_mismatch` > `not_adopted` > `escalated` > `not_resolved_first_contact`。
所以有标签集里 `c-003` 的原因写的是 `intent_mismatch`，尽管它同时 `escalated: true`。

## 判不了的（1 项）

`top3`（`ManualCheck`）：`06` G5 的"Top3 bad case 每条四段——现象 → 根因假设 →
下一步动作 → 预计改善；只描述现象 = 未达"。**不进分母。**
工具能给你 `cases`／`by_category`／`recommendation`，但"根因假设"和"预计改善"
是你的判断，退不出退出码。

## 工具与门禁的差距

| G5 自查（`03` §3） | 语义 | 工具/lab 拦得住吗 |
|---|---|---|
| ① 同命令同结果可复现 | blocker | ⚠️ 半判：第 8 项只在**同一沙箱、同一版本**里跑两遍比 `metrics`。换机器、换版本、换数据不在此列；`06` 说的"别人照着敲也能出同一个数"仍要你写清版本与命令 |
| ② bad case Top3 含"下一步动作" | blocker | ❌ 判不了（`top3` 是人工项）。第 5/6/7 项只证明**工具给的**那一条动作存在，不证明你写的三段假设是你的 |
| ③ 一页验证记录（含被拒绝需求） | warning | ⚠️ 只判"无 TODO + ≥400 字节"（第 9 项），**没有任何内容关键词**——写满 400 字的天气也绿。"被拒绝的需求"机器不知道 |

另外两件 `06` Day 5 明写、这一天**一项都没判**的事：

* **可演示原型**（命令截图 / `fde-scope web` 录像 ≤2 min）：判它要浏览器与图像比对，
  超出"只打在 CLI 三个面上"的取舍（`fde_scope/course/verifier.py` 顶部）。
* **测试集 ≥200 条**：lab 用自带 5 条／4 条夹具判"分数的来路"，
  因为判"你有多少条"要读你自己的文件，而 `06` 的模板落盘路径各人不同。
  这是**已知 GAP**，不是遗漏：数量要求留给讲师，来路判断必须机器判。

## 卡住了怎么办

1. **`Unknown agent`** → 只有 `mock`（规则版）与 `mimo`（需要 key）两个名字。
2. **第 2 项红、看到 0.000** → 你跑的是**有标签**那份。两条命令只差 `--test-set`
   的文件名，先 `wc -l fixtures/*.jsonl`（实测 5 与 4）对一下手里是哪份。
3. **`intent_accuracy` 怎么都是 1.000** → 你的 `test_set.jsonl` 里没有
   `expected_category` 字段——这是设计（`06` 让你先删），不是 bug。要真实判分就把
   标签加回去，然后**别把 0.000 读成"模型很差"**：见 §核心。
4. **`escalation_rate` 是 0.250 而不是 0.200** → 有标签集只有 4 条（1/4）。
   两份夹具条数不同，别跨文件比这个数。
5. **第 5 项红、`cases.0` 不是 `c-003`** → bad case 顺序跟测试集**行序**一致。
   你自己重排过 `test_set.jsonl` 就会漂；lab 判的是自带夹具。
6. **第 8 项红** → 说明 eval 有随机性（不该有）。先确认没设 `FDE_SCOPE_MIMO_API_KEY`
   ——带 key 时 `--agent mimo` 才可能不稳；`mock` 路径实测逐字节可复现。
7. **只有第 9 项红** → 改的是数据根目录下 `course-labs/D5/验证记录.md`，
   不是 `starter/` 原件（`--verbose` 会打印这次用的绝对路径）。

## 来源与可信度

| 内容 | 来源 | 可信度 |
|---|---|---|
| 9 项断言原话；1.000／0.000／0.2／0.25；`c-003`；`{"门店投诉": 1}`；`Top bad case category: 退款售后` 与推荐句；两次 `--json` 逐字节一致 | 本仓库一次性沙箱实测（`FDE_SCOPE_HOME=/tmp/…`）+ `course check D5` | **工具实测**（v0.1.0 · Python 3.12 · 2026-10-06 · macOS arm64） |
| 子串判分与"无信号＝判为对"；失败原因优先级；`most_common` 并列取先出现者；`~50 条` 的算式 | `fde_scope/eval/metrics.py:90-99`、`eval/bad_case_miner.py:63-64,77-89` | 代码原文 |
| 测试集 5 行／4 行、`c-005` 是 `c-001` 的口语改写、`c-003` 带 `escalated` | `labs/D5/fixtures/*.jsonl` 原文 | 配置原文 |
| "先删 `expected_category` 跑通""主指标 + ≥1 个业务口径指标""Top3 四段""一页验证记录含被拒绝需求""测试集 ≥200 条""原型截图／录像 ≤2 min" | `06` §4 Day 5 | **教案原文** |
| G5 三条自查与 ①② blocker／③ warning 分级 | `03` §3 | **教案原文** |
| 原型演示与条数要求未进 lab；复现只在同沙箱成立 | 本文 §工具与门禁的差距 | **GAP**（有意取舍，写在 `verifier.py` 顶部） |

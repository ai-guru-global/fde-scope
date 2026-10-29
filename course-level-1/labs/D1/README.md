# D1 · 入门日 —— 判「链路真的通了」

`06` Day 1 的产出是一张「迷你链路证据包」。这一天 lab 只判一件事：
**你贴进档案的那些数字，是不是命令真跑出来的。**

判分：**10 个机器项 + 1 个人工项**（可信度：工具实测，v0.1.0，2026-10-06）。
档案 `lab-d1`，profile `ticket`。

## 跑起来

```bash
./check.sh D1                    # 或 python -m fde_scope course check D1
python -m fde_scope course check D1 --verbose   # 每项打印命中的原话
```

D1 **没有 `starter/`**：这一天要写的东西（三行白话解释）机器判不了，
其余全部靠命令和落盘文件。这是唯一一天这样安排的天，不是漏了。

## 机器判了什么（10 项）

断言只打在三个面上：退出码、打印的原话、`--json`／落盘文件。
下面「判什么」那一栏是 catalog 里的原话，不是我的转述。

| # | id | 命令 | 判什么 |
|---|---|---|---|
| 1 | `status` | `engage status lab-d1 --json` | 输出里有 `customer` / `current_phase` / `visible_phase_count` 三个键，且 `西岸家电` 真的在里面 —— 档案是建出来了，不是 JSON 里写了个名字 |
| 2 | `phase` | 同上 | `current_phase == "qualification"` |
| 3 | `visible-phases` | 同上 | `visible_phase_count == 15`（制造业档案是 18，两者不是同一张 SOP） |
| 4 | `connect` | `connect --type csv --source <lab 自带 CSV> --sample-size 20` | 打印含 `Sample extracted` / `nullable` / `PII?` / `sample_size=20` 四句原话 |
| 5 | `preview-rows` | — | `<沙箱数据根>/samples/preview.json` 里正好 20 条 |
| 6 | `corpus` | `corpus --input <CSV> --out <沙箱>/main/t.html` | 打印 `Corpus forged` + `20 real + 395 synthetic = 415 total` + `Report →` |
| 7 | `total` | — | `corpus_report.json` 的 `total == 415`，与第 6 项打印的是同一个数 |
| 8 | `real-share` | — | `real == 20`（其余 395 条是合成的） |
| 9 | `html` | — | 那份 HTML ≥ 4000 字节 —— 存在且不是空壳 |
| 10 | `bad-input` | `corpus --input <不存在的文件>` | **退出码 2** 且打印 `CSV source not found` —— 报错而不是静默产出空报告 |

第 7/8 项是 G1 第三条自查（「报告数字与实际一致」）唯一能被机器看到的形式：
**命令行打印的数**和**报告 JSON 里的数**必须同时等于 415／20。
只判其中一个，就放过了「打印写了 415、JSON 其实是 414」这种漂。

## 判不了的（1 项）

`explain`（`ManualCheck`）：三句话对同伴解释这份报告，415／20／395 各是什么，
对方能复述。这是 `06` G1 的 ② 号 blocker。

**它不进分母。** 报告文件存在 ≠ 你能解释，而这门课的 G1 明确把「能解释」写成
blocker。机器项全绿不等于过了 G1 —— 见 `03` §1.1 那两套门禁的区别。

## 工具与门禁的差距

| G1 自查（`03` §3） | lab 判了吗 | 差在哪 |
|---|---|---|
| ① 命令跑通、报告文件真实存在 | ✅ 判了（第 4、6、9 项） | — |
| ② 能用白话解释（blocker） | ❌ 判不了 → `ManualCheck` | 语言产出无法用退出码判 |
| ③ 报告数字与实际一致（warning） | ✅ 判了（第 7、8 项对第 6 项） | 只核对「打印 vs JSON」这一对；「与实际跑的这批数据一致」仍靠你 |

`06` Day 1 卡片还有两件事，这一天**没进 lab**，原因各不相同：

* **`python examples/seed_mock_engagements.py`**：`examples/` **不进 wheel**
  （`pyproject.toml:100` 只 `force-include` 了 `course-level-1`）。pip 装的用户
  根本没有这个路径。可信度：`pyproject.toml` 原文 —— 这是 GAP，不是我没写。
  在仓库里跑的人仍然该跑它，因为空控制台**没有红色 blocker**，跳过这一步
  等于没见过真实形态。
* **控制台截图**：判它需要浏览器与图像比对，超出「只打在 CLI 三个面上」的取舍
  （取舍写在 `fde_scope/course/verifier.py` 顶部）。

## 卡住了怎么办

按这个顺序查，前两条解决绝大多数 D1 失败：

1. **`fde-scope: command not found`** → 用 `python -m fde_scope`，它不依赖 PATH
   里的入口点。两种写法都能用（`11` §2）。
2. **中文表格断列、`contains` 判不过** → `export COLUMNS=200`。宽度不够时 rich
   会把 `sample_size=20` 这种串拆行，字符串匹配就断了。lab 内部已经设了
   `COLUMNS=200`，你自己手跑命令时没有。
3. **`corpus_report.json` 找不到** → 它一定落在 `--out` **同一个目录**
   （`fde_scope/cli.py:222`）。而 `--out` 是**相对当前目录**解析的，不是相对数据
   根目录：`--out reports/t.html` 会写到你此刻站的目录下面。不给 `--out` 时
   默认才落到 `<数据根>/reports/corpus_report.html`（`cli.py:187`）。
4. **报告打不开** → `11` §3.2。macOS 上双击那份 HTML 就会用浏览器打开。
5. **前面全绿、第 5 项红** → `preview.json` 写在**数据根目录**下
   （`cli.py:154`）。`course doctor` 会打印这次命中的是四条规则里的哪一条；
   换一个目录跑，它可能换了一个家。

## 来源与可信度

| 内容 | 来源 | 可信度 |
|---|---|---|
| 10 个机器项、415/20/395、退出码 2 与两句报错原话 | 本仓库 `course check D1` 实测 | **工具实测**（v0.1.0 · Python 3.12 · 2026-10-06 · macOS arm64） |
| 「产出 1 = 迷你链路证据包」、三行白话解释、G1 三条自查 | `06` §4 Day 1、`03` §3 | **教案原文** |
| 判分只打在退出码／打印／`--json`+落盘文件三个面上 | `fde_scope/course/verifier.py`、`fde_scope/course/checks.py:99` | 代码原文 |
| `examples/` 不进 wheel | `pyproject.toml:100` | 配置原文 |
| ticket 档案 15 个可见阶段 vs 制造业 18 | `engage status` 实测 | **工具实测** |
| 12 类告警、每类目标 100 条等数据侧结论 | 见 D3 | 各天各自标注 |

换版本后请重跑 `course check all`，不要沿用本文数字（同一份 CSV、不同版本的
合成器种子可能给出不同的 395）。

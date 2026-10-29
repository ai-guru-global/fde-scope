# labs · 八天，每天一条命令判分

`06-学员手册与作业包.md` 给了 8 张任务卡和 8 道门禁自查，但任务卡不是 lab：
自学的读者贴完命令，没人告诉他"这条命令真的干了课上说的那件事"。这里的
`D1…D8/` 就是补这一层——每天一个 starter 目录 + 一组机器判分项。

判分**不发明新语言**。全部断言打在 CLI 已有的三个面上：

| 面 | 怎么用 | 谁规定它 |
|---|---|---|
| 退出码 | `gate check` 遇阻塞项退 1，参数非法退 2 | `fde_scope/cli.py` |
| 打印文本 | 「未填告警路由」「重复的成功标准」这些原话 | 同上 |
| `--json` / 落盘文件 | `corpus_report.json`、`samples/preview.json`、`reports/runbook_<id>.md` | 工具自己写的 |

所以一门 lab 不可能"绿着"而工具说别的话——这是 `fde_scope/course/verifier.py`
顶部写死的取舍。

## 跑起来

```bash
python -m fde_scope course doctor          # 先自检环境（G0）
python -m fde_scope course check D3        # 只判第 3 天
python -m fde_scope course check all       # 八天全判
./check.sh D3                              # 等价，少打几个字
```

每天跑在**一次性沙箱**里：新建临时工作目录 + 临时 `FDE_SCOPE_HOME`，跑完删掉。
你自己的档案不会被碰到，昨天的状态也不会让今天的题变绿。
可信度：工具实测（v0.1.0，2026-10-06），机制见 `fde_scope/course/verifier.py::LabWorkspace.create`。

## 分数怎么读

一台机器 **91 个判分项 + 9 个人工项**（按天：D1 10+1｜D2 14+1｜D3 13+1｜D4 9+1｜
D5 9+1｜D6 11+1｜D7 17+1｜D8 8+2），分两类：

* **契约项（contract）** — 用 lab 自带的数据跑，冷跑就该全绿。它证明的是
  *"命令和课上印的一样"*。冷跑若有红的，是你环境不对或教案漂了，不是你写错了。
* **写作项（writing）** — 判 `starter/` 里那份文档**有没有被写完**：`TODO` 还在
  就是没写完。所以**冷跑必然在这里红**，这是设计，不是 bug。

拆开算：**81 个契约项 + 10 个写作项**（按天 契约/写作：D1 10/0｜D2 13/1｜
D3 12/1｜D4 8/1｜D5 8/1｜D6 9/2｜D7 14/3｜D8 7/1）。可信度：工具实测
（`course check D1…D8` 逐日冷跑，v0.1.0 · 2026-10-08 · macOS arm64）——
在一台没写过任何东西的机器上跑 `check all`，正确结论是 **81 绿 / 10 红**，
红的那 10 项全部是 `TODO` 占位没写完。要是红的数量不是 10，或红的是契约项，
那就是本文件的数字漂了，请按 `# 可信度标签` 一节重测并改这一页。

`ManualCheck`（`06` 里"≤1 页""话术零术语""凌晨 2 点盲测"这类）**不进分母**，
单独报 `manual`。工具判不了的东西假装判得了，是这个课程最容易犯的诚信问题
（`03-评估体系与通关门禁.md` 的诚实标注是一条 0 分一票否决）。

写作项判的是 `{{drafts}}` 目录 = `<数据根目录>/course-labs/<Day>/`。数据根目录由
`fde_scope/paths.py::data_root` 按四条规则决定，**第 2、4 条会跟着当前目录走**：
固定在一个目录里跑，或者显式设 `FDE_SCOPE_HOME`，否则你会在两个地方看到两份
半成品。`course doctor` 会打印它这次命中的是哪一条。

## 每篇 README 的结构

`跑起来` → `机器判了什么`（逐项列出断言的原话）→ `判不了的` → `工具与门禁的差距`
→ `卡住了怎么办` → `来源与可信度`。

## 可信度标签（沿用 `/certification` 页的编码方式）

`fde_scope/web/certification.py:12-30` 要求每个数字标明来源等级，不许"看起来像"。
lab 里加了一档实测，共四档：

* **工具实测** — 本仓库这条命令的真实输出，版本与日期写在下面。写 README 前先跑。
* **教案原文** — 抄自 `course-level-1/16…23-Dx逐节教案.md` 或 `06`，编号给出。
* **OFFICIAL** — 供应商/论文自己的页面。
* **NOTED** — 第三方笔记，正文里就在数字旁边标出来。
* **GAP** — 没有公开来源。明说缺，不填空。

实测口径：**fde-scope v0.1.0 · Python 3.12 · 2026-10-06 · macOS arm64**。
换版本后请重新 `course check all`，不要沿用本文的数字。

## 目录

```
labs/
  README.md             这一页
  check.sh              ./check.sh D3 —— 只做解释器选择和参数转发，无判分逻辑
  _shared/fixtures/     sample_tickets.csv（八天共用）、station_samples.jsonl
  D1/ … D8/
    README.md           这一天判什么、判不了什么
    starter/            要你接着写完的文档（带 TODO）；**D1 没有**——见下面
    fixtures/           这一天独有的示例数据（与 examples/ 里的原始文件比对，见测试）
```

两处不对称，写在这里而不是藏在各天 README 里：

* **D1 不判写作**。它判的是"链路真的通了"，全部靠命令与落盘文件，所以没有
  `starter/`，只有一个人工项（三句话解释）。
* **`station_samples.jsonl` 目前不进任何判分项**。它是 `12` §2.4 手写测试集时
  要抄的那份产线样本的副本，留着是为了装成 wheel 之后还能对着读；
  `_shared/fixtures/` 里只有 `sample_tickets.csv` 真的被命令消费。

`./check.sh` 在 `python3` 与 `python` 之间自动挑一个；挑错了就
`FDE_SCOPE_PYTHON=/path/to/.venv/bin/python ./check.sh D3`。它不做判分，
所以不可能与 `course check` 给出不同的结论。可信度：脚本本身
（`labs/check.sh`——选解释器、两条前置报错、`exec` 转发）。

`_shared/fixtures/sample_tickets.csv` 与仓库根 `examples/quickstart_csv/sample_tickets.csv`
是同一份字节（`tests/test_course_verifier.py` 钉住）——lab 用副本是为了装成 wheel
之后还能跑（`examples/` **不**进 wheel，`course-level-1/` 由 `pyproject.toml` 的
`force-include` 打进 `fde_scope/_data/`）。可信度：`pyproject.toml` 原文。

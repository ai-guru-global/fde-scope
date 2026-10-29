# D7 · 交接与沉淀 —— 判「四件套是不是真的齐了」

`06` Day 7 的一天，工具做两件事：把交付物**装进一个包**，然后数包里有没有四件；
再加两件**只警告、不阻塞**的叙述字段（③适用边界 / ④终止条件）。
这一天的 README 重点是那台秤**称不到的东西**——路径不校验、快照不实时、
③④ 只查"有没有"不查"管不管用"。三条全是实测，不是我推测。

判分：**17 个机器项 + 1 个人工项**（可信度：工具实测，v0.1.0，2026-10-08）。
档案 `lab-d7`，profile `manufacturing`。14 项契约项 + 3 项写作项（`技能卡`、`验收清单`、`培训材料`）。
冷跑正确结论：**14/17 绿**，红的恰好是那三个写作项。

## 跑起来

```bash
./check.sh D7
starter/技能卡.md starter/交接验收清单.md starter/培训材料.md   # 三件要写完的
python -m fde_scope course check D7 --verbose
```

## 机器判了什么（17 项）

| # | id | 命令 / 面 | 判什么 |
|---|---|---|---|
| 1 | `handoff` | `handoff lab-d7 --eval-report <fixtures> --training-material <drafts> --accept` | `✅ Handoff package assembled for lab-d7` + 摘要里 `customer accepted: ✅`；此时 ③④ 打印 `- boundary (G7③): —` |
| 2 | `signoff-blocked` | `gate check lab-d7 --gate handoff_signoff` | 退出码 **1**，`🚫 移交包缺失: ['slo_definition']`，**同时**两条 `⚠️ 移交包未记录…`（blocker 与 warning 同屏） |
| 3 | `slo-added` | `engage slo add … --name 自动解决率 --target '>=40%'` | `已定义`（把缺的那件补进**档案**） |
| 4 | `handoff-again` | 再跑一次 #1 | `Handoff package assembled`（**这一步不能省**，见下） |
| 5 | `signoff-pass` | `gate check … --gate handoff_signoff --json` | `passed = true`，实测 `blockers: []` 而 **`warnings` 有 2 条**——门绿着，③④ 还空着 |
| 6 | `advisory-recorded` | `handoff … --boundary '只覆盖 6 个月内…' --termination '连续两个 14d 窗口 <40%…' --accept` | 摘要里 `boundary (G7③)` + `termination (G7④)` 两行都有内容 |
| 7 | `advisory-cleared` | `gate check … --gate handoff_signoff --json` | `warnings#len = 0`，`passed` 仍是 true——**warning 不改退出码**，所以这条才需要单独钉 |
| 8 | `runbook-file` | `{{home}}/reports/runbook_lab-d7.md` | ≥800 字节，含 `移交状态` / `客户接受: ✅` / `自动解决率` |
| 9 | `bad-category` | `skill add --category 现场处置` | 退出码 **2**，`非法 category/source（见 --help）` |
| 10 | `skill-add` | `skill add --category methodology --body-file {{drafts}}/技能卡.md` | `✅ 草稿创建 skill-<8hex>`——id 由服务端生成，断言用 capture 把它抓回来喂后面三条 |
| 11 | `skill-publish` | `skill publish {{skill_id}}` | `✅ 已发布 skill-…` |
| 12 | `publish-twice` | 同一条再跑 | 退出码 **2**，`only drafts can be published: published` |
| 13 | `skill-show` | `skill show {{skill_id}}` | 首行 `… · methodology · published · v2` |
| 14 | `skill-export` | `skill export {{skill_id}} --format agentscope --out {{out}}/export` | `✅ 导出 1 个文件 → … (agentscope)` |
| 15 | `技能卡` | `{{drafts}}/技能卡.md` | 无 `TODO`、≥400 字节、含 `适用边界`（**写作项**） |
| 16 | `验收清单` | `{{drafts}}/交接验收清单.md` | 无 `TODO`、含 `签字`（**写作项**） |
| 17 | `培训材料` | `{{drafts}}/培训材料.md` | 无 `TODO`、≥300 字节（**写作项**） |

第 4、5 项的关系是这一天原来的核心机制：`slo_definition` 是**装配那一刻的快照**
（`fde_scope/engagement/handoff.py:89`：`[s.model_dump() for s in ctx.slos] or None`），
不是实时视图。所以"档案里补了 SLO、门禁还红"不是 bug——**必须再装配一次**。
实测代价：第一次装配的 Runbook 1905 字节、里面没有 SLO 表；第二次 1990 字节，
多出 `| 自动解决率 | >=40% | 月 2pp | 值班 FDE / 企微群 / 15min | 28d |`。

第 5~7 项是这次加进来的第二条机制，而且它和第 4 项**方向相反**：

* 证据路径（`--eval-report` / `--training-material`）**不 carry-over**——某次装配不带，包里就是 `—`；
* 叙述字段（③④）**carry-over**——`handoff.py:91-92` 写的是
  `boundary if boundary is not None else prior.get("boundary")`，不带就从上一版留着。

一句话：**证据宁缺勿旧，叙述宁留勿删。** 实测（沙箱 `lab-d7p`，只带 `--accept` 再装配一次）：
`- eval report: —` / `- training material: —`，而 `- boundary (G7③): 只覆盖 6 个月内有线下 POS 流水的门店` 原样还在。
反向也实测：`--boundary ''` 会把 boundary **清空**并让 ⚠️ 重新出现——所以"传空串"是删除手段，不是保留手段。

第 10~14 项是一条完整的写库纪律：草稿 → 发布 → 重复发布被拒 → 版本号 `v1→v2` → 能被别的 runtime 消费。
`v2` 是发布时升的那一次，不是笔误。技能 id 每次跑都不同（实测两次分别 `skill-66e819ea`、`skill-3629bc22`），
所以断言用 capture 抓，不硬编码。

## 判不了的（1 项）

`退场计划`（`ManualCheck`）：G7 ④「退场计划有终止条件」+ ③「技能卡五段齐全（场景→问题→做法→证据→适用边界）」。**不进分母。**
原因写在 rubric 里，分两半：终止条件**已经在包里**了，但工具只查"有没有"——写「待定」也算有，
能不能真据此停手只能人判；而 **30/60 天支持安排工具里根本没有字段**——移交包的交付物键是
`runbook / eval_report / slo_definition / training_material / boundary / termination / safety_posture /
model_card / customer_accepted`，外加 `customer / engagement_id / profile` 三个身份键
（`handoff.py:84-99`），没有"支持期"。

## 工具与门禁的差距

`03` §3 第 74 行原文：**①② blocker；③④ warning**
（① 交接包四件套齐全（Runbook/评估报告/SLO/培训材料）② 验收清单含签字人 ③ 技能卡含"适用边界" ④ 退场计划有终止条件）。

| G7 自查 | 语义 | 工具/lab 拦得住吗 |
|---|---|---|
| ① 四件套齐全 | blocker | ⚠️ 判了"键在不在"，**没判"东西真不真"**。实测：`--eval-report /tmp/nope_does_not_exist.md` 照样 `✅ Handoff package assembled`、退出码 0——`handoff` 只记路径，门禁判的是 `not pkg.get(k)`，**非空字符串就算有**。一个指向空气的路径能让 G7 ① 变绿 |
| ② 验收清单含签字人 | blocker | ⚠️ 半判：第 16 项只查 `签字` 两个字在不在，**有没有名字判不了**（`张三`/`待补` 都算含"签字"） |
| ③ 技能卡含"适用边界" | warning | ✅ 对得上：第 15 项逐字查 `适用边界`；`starter/技能卡.md` 已印好该词（出现 2 次），所以冷跑红**只因 6 处 TODO** |
| ③′ 移交包记录适用边界 | warning（本次新增） | ✅ 有字段、有 ⚠️、lab 第 6/7 项判了；但 `--boundary 一句话` 与 `--boundary 待定` 工具分不出来，且**Runbook 文档里没有这两行**——实测第三次装配（补了 ③④）Runbook 仍 1990 字节、`grep 适用边界` 零命中。包里查得到，交给运维的那份 md 看不到 |
| ④ 退场计划有终止条件 | warning | ⚠️ 半判：`termination` 字段 + ⚠️ 有了（第 6/7 项），**但 30/60 天支持安排不在包里**，所以整体仍留 `ManualCheck` |

其余必须说清的边界：

* **第 5 项绿 ≠ 客户凌晨打电话时活得**。它绿的时候 `warnings` 里明确躺着两条
  `移交包未记录适用边界（G7③）…` / `…终止条件（G7④）…`——**这正是 warning 与 blocker 的分界**：
  第 7 项把它们清零，但退出码从头到尾都是 0。和 D6 的 `slo` 门禁同类（那里 `passed=true` 也带 warning）。
* **第 8 项判的是工具生成的 Runbook**，不是你 D6 手写的那份。两份都要交：一份证明工具落盘了，
  一份证明你会写话术。
* **`gate check` / `handoff` / `skill add` 都写档案**（第 2 项那次 BLOCKED 顺带建了一条草稿技能）。
  所以这一天没有任何一条被标成只读，反复重跑会在技能库里堆垃圾，也会让 ③④ carry-over 到下一轮。

## 卡住了怎么办

1. **第 2 项没红（BLOCKED 没出现）** → 档案里已经有 SLO 了，或你复用了 D6 的档案。用全新
   `FDE_SCOPE_HOME` 重开；`lab-d7` 的 setup 只跑 `engage init`，不会替你清 SLO，也不会替你清 ③④。
2. **第 5 项红、还报 `移交包缺失: ['slo_definition']`** → 你补了 SLO 但**忘了第二次 handoff**。
   这不是环境坏了，是这一天最该学会的动作：改了数据，交付物要重新装配。
3. **第 6 项红了但 #1~#5 都绿** → 先单独跑那条 `handoff`，看摘要有没有 `- boundary (G7③):` 开头的行。
   没有就是命令被截断了（`--boundary` 的值里有空格，必须整体加引号）。
4. **第 7 项红、`warnings#len = 2`** → 你只跑了 `--boundary` 没跑 `--termination`（或反之）。
   两条是独立字段，一条填了一另一条仍会警告。
5. **第 8 项红、报找不到文件** → Runbook 落在**数据根目录**的 `reports/runbook_lab-d7.md`
   （实测 `/tmp/probe-d7c-home/reports/…`），不在你当前工作目录。`{{home}}` 由 verifier 解析。
6. **第 10~14 项连锁红** → 第 10 项的 capture 没抓到 id（`草稿创建 (skill-[0-9a-f]{8})`）。
   先单独跑 `skill add`，看那行有没有 `✅ 草稿创建`；正文用的是 `--body-file`，
   路径不对就没有那行。
7. **第 12 项绿了你却慌了** → 正常的。它断言的是**拒绝**：`only drafts can be published: published`
   配退出码 2。状态机不可逆是特性，不是缺陷。
8. **第 15/16/17 项红** → 三个 starter 的 TODO 分别是 **6 / 12 / 16** 处。关键词早就印好了，
   拦你的是"写没写完"。`grep -c TODO` 自查。
9. **想判"路径指向的文件真的存在"** → 得改 `fde_scope/cli.py` 的 `handoff`（或
   `HandoffSignoffGate.check`）加一次 `Path.exists()`。那是**工具改动**：先读 AGENTS.md
   的门禁契约条，再跑契约测试，别在 lab 里用文本断言假装判了。

## 来源与可信度

| 内容 | 来源 | 可信度 |
|---|---|---|
| 17 项断言原话：`移交包缺失: ['slo_definition']`、`⚠️ 移交包未记录适用边界（G7③）：用 --boundary 写明，否则接手方无人知道边界与停手条件`（及 ④ 那条）、Runbook 1905→1990 字节与 SLO 表行、`passed=true` + 空 `blockers` + **2 条 warnings**、填完后 `warnings: []`、`非法 category/source（见 --help）`+退出码 2、`only drafts can be published: published`+退出码 2、`… · methodology · published · v2`、`✅ 导出 1 个文件 … (agentscope)` | 一次性沙箱 `FDE_SCOPE_HOME=/tmp/probe-d7c-home`（档案 `lab-d7p`）全流程实测 + `course check D7 --verbose` | **工具实测**（v0.1.0 · Python 3.12 · 2026-10-08 · macOS arm64） |
| 冷跑 `14/17 绿、红的恰是 3 个写作项`；全 lab 冷跑 `81 契约绿 / 10 写作红` | `course check D7` / `check all` 实测，`tests/test_course_verifier.py` 两个 oracle 钉住 | **工具实测** |
| carry-over 不对称：只带 `--accept` 再装配 → `eval report: —`、`training material: —`，`boundary` 原样保留；`--boundary ''` → 清空且 ⚠️ 回来 | 沙箱实测 `lab-d7p` 第 4、5 次装配 | **工具实测** |
| ③④ 不进 Runbook 文档（第三次装配仍 1990 字节，`grep 适用边界` 零命中） | 沙箱实测 `wc -c` + `grep` | **工具实测** |
| 不存在的 `--eval-report` / `--training-material` 路径仍被接受（退出码 0，路径原样记入） | 沙箱实测 `/tmp/nope_does_not_exist.md` | **工具实测** |
| starter 三件的 TODO 计数（6 / 12 / 16）、字节数（1055 / 1626 / 1369）、`适用边界`×2、`签字`×3 | `grep -c` 对 `labs/D7/starter/` | 工具实测 |
| G7 四条与 ①② blocker、③④ warning 分级 | `course-level-1/03-评估体系与通关门禁.md` 第 74 行 | **教案原文** |
| 包内键名与顺序、`slo_definition` 快照语义、carry-forward 表达式、`移交包未生成` / `客户尚未书面接受移交——不得退场` 两条 blocker、`ADVISORY` 两条 warning | `fde_scope/engagement/handoff.py:15-128` | 代码原文 |
| 技能 id 由服务端生成、不可外部指定 | `AGENTS.md` 不变式 2 | 项目约束原文 |
| 课程 9 关（G0+G1–G8）对工具 10 门禁 | `03` 第 28 行 | **教案原文** |

# grill-me

> 状态：📦 可安装（未装；registry 真名 `mattpocock/skills@grill-me`，与建档名一致）· 类型：流程/方法论（需求盘问 / elicitation）· FDE 位点：Zone A · qualification / success-criteria
> 安装：`npx skills add mattpocock/skills@grill-me --directory ~/.qoder/skills -y` · 装机量：1.0M（skills.sh，2026-08-31）· 详情：https://skills.sh/mattpocock/skills/grill-me
> 说明：Matt Pocock 自述的 "my most popular skills"（repo README 原话："Use them _every_ time you want to make a change"）。同 repo 的 `tdd`（802K 装机）与 superpowers TDD 重叠，本库不重复建档。与 brainstorming 分工：发散探索 → [brainstorming](brainstorming.md)；收敛盘问 → 本页。

## 能做什么
在动手前对计划/设计做**系统性追问**（skills.sh 原话："Relentless interviewing skill that stress-tests plans and designs through systematic questioning"）：自动读代码库补上下文，沿决策树逐层盘问，直到达成 shared understanding。产出是"盘清楚的共识"，不是代码。核心盘问逻辑在同 repo 的 `grilling` 原语里（`grill-me` 的 SKILL.md 只是一层转发），`grill-with-docs`、`to-spec`、`to-questionnaire`、`wayfinder` 等兄弟 skill 都复用它。

## 何时使用
- Zone A 与客户开工会前后：把"我们想做个 X"这类口头需求盘成可进 success-criteria 的清单
- 计划评审：[writing-plans](../cross-cutting/writing-plans.md) 产出的实施计划，执行前先过一遍 grill-me 找漏洞
- 设计评审/架构方案定稿前的最后一轮"找茬"

**不用于**：需求发散探索（→ [brainstorming](brainstorming.md)，先发散后收敛）；规格已完全明确的执行型任务；纯排障。

## 新人上手

- **触发**：对 agent 说"用 grill-me 把这份需求盘一遍"/"grill me on this plan"（repo 亦有 `/grill-me` 斜杠命令；模型侧实际执行的是 `grilling` 原语）
- **第一步**：安装 `npx skills add mattpocock/skills@grill-me --directory ~/.qoder/skills -y`（skills.sh 页给的等价形式：`npx skills add https://github.com/mattpocock/skills --skill grill-me`）；装完把一段客户的模糊原话直接丢给 agent，要求逐条追问并产出"已澄清 / 未决"两栏清单
- **常见坑**：盘问密度极高（relentless），客户在场时会把开工会开成审讯——先在 FDE 内部盘一轮，只把真正需要客户拍板的问题带进客户会
- **常见坑**：repo 要求先跑 `/setup-matt-pocock-skills` 做 repo 级配置（trackers/labels），`grill-with-docs` 还依赖 `CONTEXT.md`——只单装 grill-me 时走纯对话盘问即可，别指望文档联动

## 最佳实践
- Do：盘问结论落盘成文字（未决问题清单/决策记录），再交给 [writing-plans](../cross-cutting/writing-plans.md) 出实施计划——skill 的终点是共识，不是实现
- Do：与 brainstorming 组成流水线：brainstorming 发散出方向 → grill-me 收敛掉歧义
- Don't：不在需求冻结后的执行阶段反复开 grill——它是 pre-plan 工具，执行期变更走正式变更流程
- Don't：不把 agent 的追问原样转抛客户——先内部过滤、合并、排序

## 项目应用位点
- Zone A `qualification`：客户口头需求收敛；`success-criteria`：把"上线算成功"盘成可验证标准（gate 证据的前置输入）
- Engagement 新 phase / 新 gate 方案文档定稿前：先 grill 再进评审
- fde-scope 开工会（kickoff）问题清单骨架：让 agent 按 grill-me 风格生成

## 相关
[brainstorming](brainstorming.md) · [architecture-communicator](architecture-communicator.md) · [writing-plans](../cross-cutting/writing-plans.md)

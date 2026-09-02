# executing-plans

> 状态：✅ 已安装（superpowers 插件 v5.1.0）· 类型：流程纪律 · FDE 位点：横切

## 能做什么
按已评审的计划执行：**分阶段推进 + 评审检查点**（每完成一段就停下来核对，而不是闷头跑完），配合 todo 跟踪与验证门（完成前必须有证据）。

## 何时使用
- 有 [writing-plans](writing-plans.md) 产出的计划文件要落地
- 任务跨越多个会话/多天（防止上下文丢失后重复或漏做）
- 需要在客户/团队面前展示进度与可验证性

**不用于**：没有计划的小改动；探索性试验（会破坏"按计划执行"的前提）；纯调研（→ [research-*](../zone-a-pre-engagement/firecrawl-search.md) 系列）。

## 新人上手

- **触发**：有一份已写好的计划要落地，对 agent 说「用 executing-plans 执行 <plan 文件>」——SKILL.md 触发描述是"有书面实施计划、带评审检查点地在独立会话执行"
- **第一步**：它先批判性通读计划、有疑问先向人提出，然后逐任务勾选执行（每步照计划跑、按计划跑验证）；宿主有子 agent 能力时会建议改走 `subagent-driven-development`
- **常见坑**：遇阻塞（缺依赖、测试失败、指令不明）立即停下问人，禁止靠猜推进；验证反复失败同样是停止条件——"强行穿过 blocker"是 skill 明令禁止的行为
- **常见坑**：未经用户明确同意不得在 main/master 上直接实施（"Never start implementation on main/master branch without explicit user consent"）；开工前先用 using-git-worktrees 确认隔离工作区，收尾走 `finishing-a-development-branch`

## 最佳实践
- 执行前先把计划读进来再动手，别凭上一轮的记忆
- 每个检查点做三件事：跑验证命令 → 对照计划验收标准 → 更新状态（不要"看起来做完了"）
- 偏离计划要显式记录偏离原因和后续动作，不能悄悄改路线
- 遇到阻塞：先诊断再决定（换方案 / 问用户 / 停下），不要靠猜继续推进
- 与 [verification-before-completion](using-superpowers-family.md) 绑定：没有验证证据不宣称完成——这条纪律在交付场景能救命
- 现场适用性：客户环境里的写操作阶段，检查点必须包含"客户确认"这一步

## 项目应用位点
- 横切：多阶段交付任务（如连接器扩展 + 评估改造 + 文档同步）的执行框架
- Zone C/D：分批推进交接清单时的进度控制器

## 相关
[writing-plans](writing-plans.md) · [using-superpowers-family](using-superpowers-family.md) · [dispatching-parallel-agents](dispatching-parallel-agents.md)

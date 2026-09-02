# using-git-worktrees

> 状态：✅ 已安装（`~/.qoder/skills/using-git-worktrees`，亦随 superpowers 插件 v5.1.0 分发）· 类型：工作区隔离 · FDE 位点：横切（Zone B 实施 / 横切调度）

## 能做什么
在动手改代码前，确保工作发生在一个**隔离工作区**：优先用平台原生 worktree 工具，没有才回退到 `git worktree add`。流程固定为「检测已有隔离 → 征求同意 → 建区 → 装依赖 → 跑基线测试」，核心原则是 **先检测、再原生、最后 git 兜底，绝不跟 harness 抢管理**。

## 何时使用
- 开始一项 feature 改造，而当前分支上有未收口的东西（客户现场分支尤其危险）
- 执行实现计划前（→ [executing-plans](executing-plans.md)），需要一条干净的对照基线
- 并行派发多个 agent 改同一仓库（→ [dispatching-parallel-agents](dispatching-parallel-agents.md)），必须有物理隔离
- 想在客户 repo 上做实验性修复，但不能污染交付分支

**不用于**：只读分析、答疑、生成文档（不写代码就别开销）；已经在 linked worktree 里（先检测，别套娃再建一层）；submodule 内部——`GIT_DIR != GIT_COMMON` 在 submodule 里同样成立，要用 `git rev-parse --show-superproject-working-tree` 排除误判。

## 新人上手

- **触发**：开工前对 agent 说「建一个隔离工作区」或「先起个 worktree」——SKILL.md 触发描述是"starting feature work that needs isolation… or before executing implementation plans"
- **第一步**：它先检测再动手：比对 `git rev-parse --git-dir` 与 `--git-common-dir`，两者不等说明已在 worktree 里（直接复用，不套娃）；确认要新建时优先用平台原生工具（`EnterWorktree` / `/worktree` / `--worktree`），没有才回退 `git worktree add`
- **常见坑**：submodule 里 `GIT_DIR != GIT_COMMON` 同样成立，会误判成"已在 worktree"——必须用 `git rev-parse --show-superproject-working-tree` 排除
- **常见坑**：project-local 的 `.worktrees/` 建前必须 `git check-ignore -q .worktrees` 验证已被 gitignore——没忽略就先加 ignore 再提交，否则 worktree 内容会被误提交进仓库；建区后装依赖 + 跑基线测试两步不能省，基线红了先报告

## 最佳实践
- **同意优先**：用户没表达过 worktree 偏好时，先问一句"要不要建隔离工作区"；已经声明过偏好就直接执行，不重复问
- 有原生工具（如 `EnterWorktree` / `/worktree` 命令 / `--worktree` 标志）就必须用它——手动 `git worktree add` 会造出 harness 看不见的"幽灵状态"，清理时踩坑
- project-local 目录默认 `.worktrees/`；**建之前强制验证被 gitignore**（`git check-ignore -q .worktrees`），没忽略就先加 ignore 再提交——否则 worktree 内容会被误提交进仓库
- 建区后两件事不能省：装依赖（按 `package.json`/`pyproject.toml` 自动识别）+ 跑基线测试。**基线红了就先报告，别带着失败继续改**，否则无法区分"我改坏的"和"本来就坏的"
- 沙箱拒绝 `git worktree add` 时如实说明并就地工作，不要静默降级
- 收尾走 superpowers 的 `finishing-a-development-branch`（合并/PR/丢弃三选一，见 [using-superpowers-family](using-superpowers-family.md)），别留一堆游离 worktree

## 项目应用位点
- fde-scope 分支纪律：`connectors/` 大改与 `pawapp/` 适配属于互不影响的两条线，适合各占一个 worktree，避免 `git status` 混污
- 客户现场：在客户 repo 上验证"猜测型修复"时先建 worktree，保证随时能整块丢弃——比 `git stash` 可靠，也不会因为 IDE 自动恢复而串味
- 本 catalog 的批量建档（按 Zone 分批写文件、互不冲突）就是典型的"可并行 + 宜隔离"任务

## 相关
[executing-plans](executing-plans.md) · [dispatching-parallel-agents](dispatching-parallel-agents.md) · [writing-plans](writing-plans.md) · [using-superpowers-family](using-superpowers-family.md) · [gstack-suite](gstack-suite.md)（`freeze`/`guard` 是另一类"防误改"机制）

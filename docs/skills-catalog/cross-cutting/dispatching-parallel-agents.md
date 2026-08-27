# dispatching-parallel-agents

> 状态：✅ 已安装（superpowers 插件 v5.1.0）· 类型：并行调度 · FDE 位点：横切

## 能做什么
面对 2 个以上**互相独立**的任务，派发多个并行 agent 各管一个（各自完整上下文、互不污染），再汇总结果；也可用于探索/验证并行的场景。

## 何时使用
- 多个模块互不相关的改造（例：给 3 个 connector 分别补测试）
- 同时需要"调研 A + 验证 B + 起草 C"且三者无依赖
- 大范围代码库分析：分区并行比单线扫更快

**不用于**：有共享状态/会改同一文件的任务（会冲突）；顺序依赖强的流程（→ [executing-plans](executing-plans.md)）；需要保持推理链连续的单任务（拆分会丢上下文）；任何生产写操作（并行执行事故面更大）。

## 最佳实践
- 派发前三问：有重叠改动吗？有顺序依赖吗？结果能独立验收吗？任一为"否"就别并行
- 每个子任务给**明确边界**：只碰哪些文件、成功判据是什么、不要越界改别的
- 用 [using-git-worktrees](using-git-worktrees.md) 做物理隔离，避免多 agent 抢同一工作树
- 汇总阶段人工过一遍：并行的产出风格/假设可能不一致，合并就是统一的机会
- 并行数控制在能审得过来的量（一般 2~3），并行不是越多越好
- 成本注意：每个并行 agent 都吃一份上下文，重复的检索会放大 token 消耗

## 项目应用位点
- 横切：多场景（ticket / manufacturing）并行推进时的调度方式
- 本 catalog 建设即属可并行类型（按 Zone 分批、彼此无文件冲突）

## 相关
[using-git-worktrees](using-git-worktrees.md) · [executing-plans](executing-plans.md) · [using-superpowers-family](using-superpowers-family.md)

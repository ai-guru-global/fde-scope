# writing-plans

> 状态：✅ 已安装（superpowers 插件 v5.1.0）· 类型：流程纪律 · FDE 位点：横切（多步任务开始前）

## 能做什么
在动手写代码之前产出**可执行计划**：任务分解、步骤粒度（2~5 分钟一步）、文件路径、验证点、回滚位点，并保存为文档供后续评审与执行（默认存 `docs/superpowers/plans/`）。

## 何时使用
- 任何 3 步以上的任务：新连接器、迁移、批量文档重构、现场部署脚本
- 需要客户/同事评审"你打算怎么做"的时候（交付场景里这是信任来源）
- 上下文即将切换或多轮会话推进同一任务（计划就是持久化的意图）

**不用于**：单步小改动（直接做）；探索性原型（先 [brainstorming](../zone-a-pre-engagement/brainstorming.md) 再回来）；已有计划要执行（→ [executing-plans](executing-plans.md)）。

## 最佳实践
- 步骤要含**验证方式**（跑什么命令、期望什么输出），否则计划无法判定完成
- 计划里显式标注"需要人工确认"的节点（生产变更、客户环境写操作、删数据）
- 粒度宁细勿粗：粗计划在执行时会被迫即兴决策，即兴决策就是风险
- 与本项目工作流对齐：复杂任务用 Plan 模式产出 plan 文件，Agent 模式执行；跨会话续做时先读 plan
- 计划不是合同：发现假设错了要改计划并留痕，不要悄悄偏离
- 大计划要拆分：一次会话只推进一个可验证的子计划

## 项目应用位点
- 横切：本 catalog 自身的建设就是按"计划 → 分批执行 → 校验"跑完的
- Zone B：连接器/评估改造的实施计划载体

## 相关
[executing-plans](executing-plans.md) · [brainstorming](../zone-a-pre-engagement/brainstorming.md) · [using-superpowers-family](using-superpowers-family.md)

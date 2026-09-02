# 内置工具使用纪律

> 状态：✅ 随客户端自带 · 类型：使用规约 · FDE 位点：横切（新人第一周必读）
> 配套：[内置工具总览](overview.md)（清单）· fde-scope 硬约束见仓库 `AGENTS.md`

## 能做什么

把内置工具**用对**的规约清单：每条都对应一个真实的踩坑模式。新人把本页过一遍，能避开 80% 的低级失误。

## 何时使用

- 每次会话里动手干活前——这些不是可选建议，是行为默认值
- code review 自查时：对照逐条检查 agent 产出的操作序列

**不用于**：项目级不变量（如 fde-scope 的原子写、门禁再评估）——那些在仓库 `AGENTS.md`，优先级更高。

## 新人上手

- **触发**：新人第一周必读；动手前本页就是行为默认值，code review 自查时逐条对照
- **第一步**：先记牢三条最高频——`Read` 之后再 `Edit`、声称完成前必须跑验证、破坏性操作先问用户；其余四节每周回看一遍
- **常见坑**：把本页当"可选建议"——每条规约背后都是真实踩坑模式（外部改动后读状态失效、sleep 轮询、误读后台任务全量日志）；被拒绝的调用原样重试只会再被拒，先想为什么

## 最佳实践

**文件操作**
- `Edit`/`Write` 前必须先 `Read` 目标文件的当前状态；文件在会话外被改动后，读状态失效，重读再改
- 精确字符串替换用 `Edit`；整文件新建或彻底重写才用 `Write`；别用 Bash 的 `echo >` / `sed -i` 干编辑的活
- 改完自查 diff，别声称改了没改的东西

**执行与验证**
- 读用 `Read`、搜用 `Grep`/`Glob`、编辑用 `Edit`——`Bash` 留给真正需要 shell 的场景（跑测试、装依赖、git）
- 长命令（构建、测试套件）用 `run_in_background`，完成自动通知；禁止 `sleep` 轮询等待
- **声称完成之前必须跑验证**：改了代码跑测试、改了文档跑 `make check-catalog`——证据先于结论（见 [verification-before-completion](../cross-cutting/using-superpowers-family.md) 的超能力族）

**并行与委派**
- 互不依赖的调用并行发（读多个文件、跑多个独立检查）；有依赖的串行等结果
- 派 `Agent` 前想清楚任务边界：搜索/调研可委派，**理解与决策不委派**；子 agent 的结论要抽查核对
- 后台任务的产物不要直接 `Read` 它的完整日志文件（可能是全量 transcript），等完成通知里的摘要

**权限与风险**
- 被拒绝的调用不要原样重试：先想为什么被拒，换思路
- 破坏性/不可逆操作（`rm -rf`、`git push --force`、删分支、动共享资源）默认先问用户；用户批准过一次不代表处处批准
- 遇到陌生的文件/分支/锁，先调查是什么再决定动不动——那可能是别人的进行中工作

**沟通**
- 动手前一句话说明要做什么；长任务在关键节点给简短进展
- 结论里区分"实测到的"与"推测的"；跳过的检查要点名说明原因

## 项目应用位点

- fde-scope 的门禁文化与本页同构：`make test` / `make check-catalog` / `make check-local` 是每批改动的固定收尾，不改"绿"不收工
- 客户现场高危环境：本页"权限与风险"一节 + [gstack-suite](../cross-cutting/gstack-suite.md) 的 `guard`/`freeze` 是双重保险
- 新人第一周路径：本页 → [内置工具总览](overview.md) → [MCP 服务器总览](../mcp/overview.md) → 手册库按 Zone 补场景

## 相关

[内置工具总览](overview.md) · [MCP 服务器总览](../mcp/overview.md) · [using-superpowers-family](../cross-cutting/using-superpowers-family.md) · [writing-plans](../cross-cutting/writing-plans.md)

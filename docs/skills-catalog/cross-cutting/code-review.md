# code-review

> 状态：✅ 已安装（coderabbit 插件 v1.1.1，含 `code-review` + `autofix`；另有 superpowers 的 `requesting-code-review` / `receiving-code-review`）· 类型：质量门禁 · FDE 位点：横切（每次合并前）

## 能做什么
用 CodeRabbit 做 AI 代码评审（显式请求或 agent 自主触发均可），覆盖正确性、安全、质量与规范；`autofix` 可把评审意见落成修改。本项目另有 `docs/code_review_checklist.md` 作为人工清单。

## 何时使用
- 每次 PR / 合并前，尤其涉及连接器、gate 逻辑、凭据处理、部署配置
- 交付前最后一道质量门（客户会看代码的项目尤其重要）
- agent 自主认为需要评审时（该 skill 是默认评审入口）

**不用于**：架构层面的取舍判断（→ [risk-quality-reviewer](architecture-visualization-suite.md)）；文档一致性（→ [architecture-health](architecture-visualization-suite.md)）；纯格式化（用 ruff/black，别浪费评审额度）。

## 新人上手

- **触发**：对 agent 说「review my code」「看看这次改动有什么问题」或直接点名 coderabbit——它是默认评审入口，显式请求与 agent 自主触发都走它
- **第一步**：先确认 CLI 就绪：`coderabbit --version`、`coderabbit auth status`（未装从 https://www.coderabbit.ai/cli 安装，未登录跑 `coderabbit auth login`），然后 `coderabbit review --agent` 拿 agent 可读的评审与修复指引
- **常见坑**：`--agent` 需要 CodeRabbit CLI v0.4.0+，旧版本直接不支持；`--dir <path>` 指定的目录必须已初始化 Git 仓库
- **常见坑**：CLI 会把代码 diff 发送到 CodeRabbit API 分析——跑评审前先确认暂存区无凭据/密钥；客户气隙环境这条要走线下评审路径，别默认直连

## 最佳实践
- 三层不重复：lint/typecheck 机械层 → AI 评审模型推理层 → 人工业务与安全判断（`docs/code_review_checklist.md` 就是人工层）
- 小 diff 才有好评审：大改动先拆 PR，评审质量与 diff 大小反比
- 提供上下文：让评审知道业务约束（工业场景的安全边界、气隙限制），否则会收到大量不适用建议
- `autofix` 只用于低风险项（命名、类型、简单修复）；涉及 gate 语义、凭据、连接器的建议必须人工确认
- 反馈要具体可操作，禁止"建议优化"式空话；不认可的规则要在配置里关掉而不是每次忽略
- 与 superpowers 的 `receiving-code-review` 配合：收到意见先验证再改，避免"评审说啥改啥"

## 项目应用位点
- 横切：AGENTS 级流程（本仓库为 `docs/code_review_checklist.md`）
- 每次交付前：Zone B → Zone C 的门禁之一

## 相关
[security-scan](security-scan.md) · [gstack-suite](gstack-suite.md) · [using-superpowers-family](using-superpowers-family.md)

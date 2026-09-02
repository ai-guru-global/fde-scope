# trailofbits-security-suite（trailofbits/skills）

> 状态：📦 可安装（**未装**）· 类型：套件档案（深度安全审计插件族）· FDE 位点：横切（Zone B validate + 交付前加固）
> 来源：`trailofbits/skills`（Trail of Bits——业界知名安全研究公司；repo **6,924★**，描述 "Trail of Bits Claude Code skills for security research"，2026-08-31 GitHub API 核对）· 上游：https://github.com/trailofbits/skills
> 规模事实（2026-08-31 核对）：`.claude-plugin/marketplace.json` 共 **43 个插件**（README 正文口径为 32，两者不一致，以 marketplace.json 为准）；九大类：Smart Contract Security / Code Auditing / Malware Analysis / Verification / Reverse Engineering / Mobile Security / Development / Team Management / Tooling；许可 CC BY-SA 4.0，兼容 Claude Code 与 Codex
> 安装：**不走 skills.sh 单条**，而是 Claude Code 式插件市场：`/plugin marketplace add trailofbits/skills`——与 `npx skills add` 是**不同通道**，Qoder 侧先跑 [skill-criticagent](skill-criticagent.md) 评估再逐个启用
> 建档名说明：registry 无 `trailofbits-security-suite` 条目，本页是对 `trailofbits/skills` 整仓库的套件档案

## 能做什么
Trail of Bits 出品的 AI 辅助安全插件族（43 个）。对本库最相关的成员（README 描述原文已核对）：`static-analysis`（"Static analysis toolkit with CodeQL, Semgrep, and SARIF parsing"）、`differential-review`（"Security-focused differential review of code changes with git history analysis"）、`supply-chain-risk-auditor`（审计 npm / PyPI / Go 依赖的版本匹配 advisory）、`modern-python`（"Modern Python tooling and best practices with uv, ruff, and pytest"）、`spec-to-code-compliance`（"checks code against the documentation that specifies it"）。其余可选：`insecure-defaults`、`mutation-testing`、`property-based-testing`、`semgrep-rule-creator`、`yara-authoring`、`vulnerability-triage-brocards` 等。

## 何时使用
- 交付前深度安全审计：工业/制造业客户、代码要进 air-gap 内网，出网前要一轮超出日常扫描的深度审计
- 供应链风险闸口：新依赖引入或版本升级时用 `supply-chain-risk-auditor` 出审计证据
- Python 3.12 项目工具链巡检：`modern-python`（uv / ruff / pytest）与本仓库技术栈**完全同构**
- 规格符合性：`spec-to-code-compliance` 检查实现是否与规格文档一致（对应交付引擎的 gate 证据思路）

**不用于**：日常 PR 评审（→ [code-review](code-review.md)，CodeRabbit 评审流）；Qoder 云端 L2/L3 扫描（→ [security-scan](security-scan.md)）。三层分工：[security-scan](security-scan.md) 管**云上快速扫描**，[code-review](code-review.md) 管**评审流**，Trail of Bits 管**深度安全审计**——逐级加深，不互相替代。

## 新人上手

- **触发**："对这次交付的代码做一轮深度安全审计"/"审计一下新引入依赖的供应链风险"
- **第一步**：`/plugin marketplace add trailofbits/skills`（Claude Code 插件市场通道；Qoder 环境下先按 [skill-criticagent](skill-criticagent.md) 结论决定启用哪些），装完先跑 `static-analysis` 建基线，再按需加 `differential-review` 做增量
- **常见坑**：安装通道与 `npx skills add` 不同——skills.sh 上没有单条目可装，别按标准安装行硬套；43 个插件一次全开会污染触发空间，按需挑 3-5 个
- **常见坑**：`static-analysis` 依赖 CodeQL/Semgrep 本地工具与规则库——air-gap 环境要预先把工具链和规则包备进内网，别假设能在线拉取

## 最佳实践
- Do：`modern-python` 与本仓库（Python 3.12 + uv + ruff + pytest）同构，可作编码规范对照基线，季度巡检一次
- Do：三层安全纵深——CI 日常 [security-scan](security-scan.md) → PR [code-review](code-review.md) → 交付前 Trail of Bits 深度审计，证据分别归档进对应 gate
- Don't：不把审计报告（含客户代码细节）外传或写进共享文档——按敏感交付物管理
- Don't：不给非区块链项目上 smart-contract 类插件——43 个里按语言/场景选对类别（c-review / rust-review / modern-cpp / modern-python 各管一摊）

## 项目应用位点
- Zone B `validate`：`static-analysis` 出基线报告、`spec-to-code-compliance` 核对实现与规格文档一致
- 依赖变更 gate：`supply-chain-risk-auditor` 审计 npm/PyPI/Go 依赖（本项目 Python 侧对应 PyPI）
- 交付评审：`differential-review` 对本轮变更做安全向 diff 评审，结论作 gate 证据

## 相关
[security-scan](security-scan.md) · [code-review](code-review.md) · [skill-criticagent](skill-criticagent.md)

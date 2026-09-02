# skill-criticagent

> 状态：✅ 已安装（research-copilot 插件 v1.0.0）· 类型：元能力/门禁 · FDE 位点：横切（所有 📦 安装前置）

## 能做什么
评估一个 Agent Skill（SKILL.md 目录）到底"好不好、能不能装"：**规范合规 + 安全扫描**、带/不带该 skill 的行为对比、description 触发测试，最后给出 **安装 / 先修 / 拒绝** 的明确结论。

## 何时使用
- 本 catalog 的强制门禁：任何 📦 项安装前跑一次，结论回填该页"最佳实践"段
- 收到别人推荐的 skill（GitHub 链接、marketplace URL）想快速判断值不值得装
- 自查自写 skill 的触发质量（和 [writing-skills](writing-skills.md) 互补：writing 管写作，critic 管判定）
- 判断 skill 是否真的带来增益（with/without 对比是唯一可信证据）

**不用于**：评估 MCP server（→ [mcp-criticagent](mcp-criticagent.md)）；代码评审（→ [code-review](code-review.md)）；架构评估（→ [risk-quality-reviewer](architecture-visualization-suite.md)）。

## 新人上手

- **触发**：把 skill 目录丢给 agent 问「这个 skill 能不能装 / is this skill any good」——SKILL.md 写明哪怕只问这一句也触发
- **第一步**：在仓库根目录零提问默认评估，先跑合规 + 安全扫描：`uv run python -m src.main eval-skill <skill_dir> --strict --json`（依赖 `uv sync`，无需 API key）——报错即不可安装，直接给「先修复」结论并跳过后续
- **常见坑**：`evals/evals.json` 里的自由句式断言会退化成字面子串匹配、with/without 两轮都无意义失败——要先在工作副本上把每句改写成可验证断言（具体字符串 / 正则）
- **常见坑**：without-skill 基线必须用没读过 skill 的全新子 agent 跑，否则对比被污染；最终结论只有三种——建议安装 / 先修复 / 不建议安装，每种都要带证据

## 最佳实践
- 评估三件套留档：verdict + 触发测试结果 + with/without 差异，写在对应 catalog 页面里，不要只留在对话
- 安全扫描不通过直接拒（不要"先用着看"）；注意 skills.sh 页面的三项审计（Agent Trust Hub / Socket / Snyk）与本 skill 的结论互相印证
- 触发测试要覆盖**误触发**：用一个语义相近但不应触发的任务验证边界
- with/without 对比要用真实交付任务（本仓库场景：连接器接入、评估报告），玩具任务测不出价值
- 同一功能的多个候选（如 runbook 类）要横向比一次，选一个装，避免重叠路由
- 社区个人源 + 低热度 + 审计缺失 = 默认拒绝，除非有明确不可替代收益

## 项目应用位点
- 横切：catalog 维护规约第 3 条的执行工具
- 当前待评估清单：所有 📦 项（`mqtt-development`、`kubernetes-specialist`、`docker-build-deploy`、`vllm-ascend`、`sre-runbooks`、`rag-agent-builder` 等）

## 相关
[mcp-criticagent](mcp-criticagent.md) · [find-skills](skill-discovery.md) · [writing-skills](writing-skills.md)

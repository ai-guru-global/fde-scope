# phoenix-evals 📦

> 状态：📦 可安装（未装）· 类型：评估指标开发 · FDE 位点：Zone B validate + Zone C 观测
> 来源：`arize-ai/phoenix@phoenix-evals`（官方 org，repo 11.2K★）· 热度：1.3K installs · https://skills.sh/arize-ai/phoenix/phoenix-evals
> 安全审计：Agent Trust Hub **Pass** · Socket **Pass** · Snyk **Pass**（三项全绿，2026-08-27 复核）
> 安装：`npx skills add arize-ai/phoenix@phoenix-evals --directory ~/.qoder/skills -y`
> 说明：早期建档时记为 `phoenix-evals-new-metric`，registry 中不存在该名，已更正为官方真实条目 `phoenix-evals`
> 同系列：`phoenix-tracing`（1.4K，观测接入）、`phoenix-cli`（1.4K）

## 能做什么
为 AI/LLM 应用**构建评估器**（evaluator）：code-first 规则打分 + LLM-as-judge 处理语义细节，并用人工标注做校验闭环。含 Phoenix 的 evals API 用法、指标编写范式、experiments 对比。

## 何时使用
- `fde_scope/eval/metrics.py` 只有规则型指标，需要新增**语义类**指标（回答是否解决了工单诉求、是否符合客户话术规范）
- bad case 规模化挖掘：`BadCaseMiner` 之外想要可复用的 judge 指标库
- 交付时要给客户一个可持续跑的评估框架，而不是一次性脚本

**不用于**：公开 benchmark 跑分（→ [huggingface-community-evals](huggingface-community-evals.md) / [evaluating-llms-harness](evaluating-llms-harness.md)）；纯 APM/链路追踪（→ [sentry-mcp](../zone-c-operationalization/sentry-mcp.md)）。

## 新人上手

- **触发**："给回答是否解决工单写一个语义评估指标"、"bad case 想用 LLM-as-judge 规模化挖掘"
- **第一步**：先安装 `npx skills add arize-ai/phoenix@phoenix-evals --directory ~/.qoder/skills -y`（官方 org、三项审计全绿可直接装；按规约补一次 [skill-criticagent](../cross-cutting/skill-criticagent.md) 结论回填本页），再让 agent 按 code-first 规则 + LLM-as-judge 范式实现指标，落地为 `fde_scope/eval/` 里的函数并注册进 `METRICS`
- **常见坑**：judge 分数直接对客户讲话——skill 的核心主张是 "validate against humans"，先在同一批样本上做 human-judge 一致性抽检，一致率不足别用；judge 走外部 LLM 时客户原文会出境——气隙/合规客户必须换本地 judge（→ [vllm-deploy-docker](vllm-deploy-docker.md)），且每条样本至少一次 LLM 调用，1k 数据集成本要预估

## 最佳实践
- 该 skill 三项安全审计全绿且来自官方 org，是本 catalog 里**风险最低的 📦 项之一**，可直接安装；仍按规约走一次 [skill-criticagent](../cross-cutting/skill-criticagent.md) 并把结论回填本页
- Judge 也是模型：先在同一批样本上做 **human-judge 一致性抽检**（skill 的核心主张："validate against humans"），一致率不足就别拿分数对客户讲话
- 成本：LLM-as-judge 每条样本一次以上调用，1k 数据集评估成本要预估；规则指标能覆盖的不要上 judge
- 数据边界：judge 用的是外部 LLM 时，客户原文会出境——气隙/合规客户必须换本地 judge（→ [vllm-deploy-docker](vllm-deploy-docker.md)）
- 与本项目整合姿势：把新指标实现为 `fde_scope/eval/` 里的函数并注册进 `METRICS`，不要另起一套评估栈

## 项目应用位点
- Zone B `validate`：语义指标补齐（intent/话术合规/引用正确性）
- Zone C：上线后持续评估与漂移监测的指标来源
- `fde_scope/eval/manufacturing_metrics.py` 的工业场景语义扩展

## 相关
[huggingface-community-evals](huggingface-community-evals.md) · [evaluating-llms-harness](evaluating-llms-harness.md) · [rag-agent-builder](rag-agent-builder.md)

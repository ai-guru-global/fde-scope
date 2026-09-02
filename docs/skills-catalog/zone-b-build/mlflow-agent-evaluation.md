# mlflow-agent-evaluation

> 状态：📦 可安装（registry 真名 `mlflow/skills@agent-evaluation`；建档名加 mlflow- 前缀防泛化，安装/详情均用真名 `agent-evaluation`）· 类型：工具/数据 · FDE 位点：Zone B validate · 客户 MLOps 栈（MLflow）评估对接
> 安装：`npx skills add mlflow/skills@agent-evaluation --directory ~/.qoder/skills -y` · 装机量：662（skills.sh，2026-08-31）· 详情：https://skills.sh/mlflow/skills/agent-evaluation

## 能做什么
MLflow 官方（mlflow org）的 agent 系统化评估手册：用 `mlflow.genai` API 面走"数据集 → scorer → 评估 → trace"闭环——`mlflow.genai.datasets.create_dataset()` / `get_dataset(name=...)` 管评估数据集，`mlflow.genai.scorers` + `scorer.register()` 管打分器，`mlflow.genai.judges.make_judge()` 写 LLM judge，`mlflow.genai.evaluate()` 跑批量评估；正文强制先查官方文档（Documentation Access Protocol），附 setup-guide、dataset-preparation、scorers、scorers-constraints、throughput-guide 五个参考文件。同 repo 兄弟：build-a-scorer、instrumenting-with-mlflow-tracing、querying-mlflow-metrics、mlflow-onboarding、analyze-mlflow-trace、fix-agent-issue 等。

## 何时使用
- 客户 MLOps 栈已在用 MLflow，要求评估结果/trace 落到客户自己的 MLflow 实例做看板与回归对比
- 要给已有 agent 做"数据集化"评估：固定评估集 + 可复跑 scorer，而不是一次性脚本
- 需要 trace 级根因分析时，配合兄弟 skill（analyze-mlflow-trace / fix-agent-issue 一族）

**不用于**：自建评估首选仍是 `fde_scope.eval` + [phoenix-evals](phoenix-evals.md)（指标开发与 judge 校验在那边做）；公开 benchmark 标准分走 [evaluating-llms-harness](evaluating-llms-harness.md) / [huggingface-community-evals](huggingface-community-evals.md)。与 phoenix-evals 的分工：Phoenix 偏评估器开发与 human-judge 校验，MLflow 偏客户 MLOps 平台集成与落库。

## 新人上手
- **触发**：对 agent 说"客户要求评估结果进 MLflow"或"用 MLflow genai 给 agent 打分"
- **第一步**：`npx skills add mlflow/skills@agent-evaluation --directory ~/.qoder/skills -y` 装完后，先 `uv run mlflow --version` 对齐客户环境版本，再按 skill 的 Evaluation Workflow 走：建/取数据集 → 注册 scorer → `mlflow.genai.evaluate()` 出结果
- **常见坑**：scorer 返回字符串 `"pass"` / `"fail"` 会被**静默**转成 None 并从 `results.metrics` 里消失（skill 原文明确警告），打分器必须返回数值或布尔；skill 明令 "DO NOT create custom evaluation frameworks"，别在 `mlflow.genai` 之外自造评估框架

## 最佳实践
- 官方 org 但装机量仅 662（2026-02 上架，社区验证薄），按 catalog 规约装前先过 [skill-criticagent](../cross-cutting/skill-criticagent.md) 并把结论回填本页
- 对接姿势：客户 MLflow 实例只做**落库与看板**，指标实现仍注册在 `fde_scope/eval` 的 `METRICS`，加一层适配器导出即可，不要双评估栈并存
- 气隙客户：MLflow server 可内网自托管，评估集与 trace 不出境；但 `make_judge` 若配外部 LLM 同样有客户原文出境问题，须换客户内网模型（同 [phoenix-evals](phoenix-evals.md) 的 judge 出境坑）
- 数据集与 scorer 命名跟随客户 MLflow 的 experiment 习惯，避免交付后客户接不住

## 项目应用位点
- Zone B validate：客户 MLflow 栈时的评估落库、回归对比与看板交付
- Zone C 观测：上线后 trace 评估回流（配合 instrumenting-with-mlflow-tracing / querying-mlflow-metrics 等兄弟 skill）
- `fde_scope/eval` ↔ 客户 MLflow 的适配层设计（指标内核不动，导出走适配器）

## 相关
[phoenix-evals](phoenix-evals.md) · [evaluating-llms-harness](evaluating-llms-harness.md) · [huggingface-community-evals](huggingface-community-evals.md)

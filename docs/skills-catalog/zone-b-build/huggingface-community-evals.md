# huggingface-community-evals

> 状态：✅ 已安装（hugging-face 插件 v1.0.0）· 类型：评估执行 · FDE 位点：Zone B validate

## 能做什么
在**本地硬件**上对 HF Hub 模型跑评估：`inspect-ai` 与 `lighteval` 两条路线、backend 选型（vLLM / Transformers / accelerate）、GPU 显存适配、任务选择、smoke test 与 backend 回退策略。

## 何时使用
- 需要拿**公开 benchmark**（MMLU/GSM8K/HumanEval/…）给客户证明"这个模型比那个强"
- 现场机器只有消费级 GPU，要选能跑动的 backend 与并发
- 与 `fde_scope.eval` 的自研业务指标做交叉验证：公开分 + 业务分双证

**不用于**：HF Jobs 云端编排（→ [huggingface-llm-trainer](../zone-c-operationalization/huggingface-llm-trainer.md)）、model-card PR / `.eval_results` 发布自动化（skill 自身声明的边界）、客户私有数据评估（→ 用 `fde_scope.eval`，数据不出机）。

## 最佳实践
- 顺序固定：先 smoke test（小样本 5~10 题）打通 backend，再全量——直接全量最容易在显存/依赖上浪费半天
- backend 优先级：本地 GPU 大模型用 vLLM，小模型/需要 logits 的用 Transformers，多卡分片用 accelerate
- 公平比较：不同模型的 chat template / max_gen_toks / few-shot 数必须一致，否则结论无效（现场最常见的坑）
- 与本项目契约：把外部 benchmark 结果当"参考量"，`EvalReport` 的 `metrics` 仍以 `fde_scope/eval/metrics.py` 的业务指标（intent_accuracy / first_contact / adoption / escalation / handle_time_ratio）为准
- 许可证：商用评估要记录 benchmark 与模型的 license 限制（部分 benchmark 禁止用于商业宣称）

## 项目应用位点
- Zone B `validate`：模型选型证据链的公开分部分
- `fde_scope/eval/benchmark.py` 的外部对照；docs/evaluation.md 补强

## 相关
[evaluating-llms-harness](evaluating-llms-harness.md) · [phoenix-evals](phoenix-evals.md) · [vllm-deploy-docker](vllm-deploy-docker.md)

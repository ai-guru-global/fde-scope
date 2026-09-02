# trl-training

> 状态：✅ 已安装（hugging-face 插件 v1.0.0）· 类型：本地训练执行 · FDE 位点：Zone C flywheel + Zone B validate

## 能做什么
用 `trl` CLI 在**本地/自有 GPU** 上跑 SFT、DPO、GRPO、KTO、RLOO 与 reward model 训练（`trl sft`、`trl dpo` 等），含数据集/参数与训练配置约束。

## 何时使用
- 客户现场有 GPU 机器（或自有训练机），数据不得出厂 → 这是唯一合规路线
- 做小规模对齐实验（偏好对 DPO）验证"话术规范"能否被训出来
- 需要完全掌控超参与日志复现时

**不用于**：无本地算力（→ [huggingface-llm-trainer](huggingface-llm-trainer.md) 走 HF Jobs）；百炼生态客户（→ [bailian-train-deploy](../zone-b-build/bailian-train-deploy.md)）；嵌入模型训练（→ [train-sentence-transformers](../zone-b-build/train-sentence-transformers.md)）；只想调用不训练。

## 新人上手

- **触发**：对 agent 说「在现场 GPU 上跑个 SFT/DPO」「用 trl CLI 微调」——对应 `trl sft` / `trl dpo` / `trl grpo` / `trl kto` / `trl rloo` / `trl reward` 六个 CLI 命令
- **第一步**：先小步验证再放全量：`trl sft --model_name_or_path <模型> --dataset_name <数据集> --max_steps 1 --output_dir smoke-test` 确认显存与数据管道通了，再改回完整超参（参考 SKILL.md 模板：`--learning_rate 2.0e-5 --packing --per_device_train_batch_size 2 --gradient_accumulation_steps 8`）
- **常见坑**：数据格式必须与训练方法对应——SFT 要 `messages`/text/prompt-completion，DPO 要 `chosen`/`rejected` 偏好对；且 DPO 命令要带 `--no_remove_unused_columns`，否则偏好列会被默认丢弃
- **常见坑**：TRL 默认从 HF Hub 拉模型权重与数据集——气隙/内网环境开跑就卡在下载，要先离线准备好模型与数据集再指向本地路径

## 最佳实践
- 环境锁死：`torch`/`transformers`/`trl` 三件套版本记录进交付文档（现场最常见的复现失败原因）
- 先 1 步 smoke run（小数据 + `--max_steps 1`）确认显存与数据管道，再跑全量
- 显存策略优先级：LoRA/QLoRA → 降 seq len → 梯度累积 → 才是加卡
- 训练数据必须来自 `fde_scope.corpus` 的导出格式，别手搓 jsonl（会绕过质量门禁与去重）
- 评估不能省：训练后用 [phoenix-evals](../zone-b-build/phoenix-evals.md) / `fde_scope.eval` 对比新旧模型，没有对比结论就不上线
- 现场注意：TRL 会拉 HF 权重，气隙环境要先离线准备模型与数据集

## 项目应用位点
- Zone B `validate`：私有化微调实验主路径
- Zone C `flywheel`：把 `retrain_scheduler` stub 落到本地训练（数据不出厂场景的首选后端）

## 相关
[huggingface-llm-trainer](huggingface-llm-trainer.md) · [train-sentence-transformers](../zone-b-build/train-sentence-transformers.md) · [bailian-train-deploy](../zone-b-build/bailian-train-deploy.md)

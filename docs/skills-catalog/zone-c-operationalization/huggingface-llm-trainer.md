# huggingface-llm-trainer

> 状态：✅ 已安装（hugging-face 插件 v1.0.0）· 类型：训练执行 · FDE 位点：Zone C flywheel（重训后端候选）

## 能做什么
在 **Hugging Face Jobs 云 GPU** 上做 SFT / DPO / GRPO / reward modeling，并支持 GGUF 转换用于本地部署。覆盖 TRL Jobs 包、PEP 723 头的 UV 脚本、数据集准备与校验、硬件选型、**成本预估**、Trackio 监控、Hub 认证与模型持久化。

## 何时使用
- `fde_scope/flywheel/retrain_scheduler.py` 目前是 **stub**（"actual fine-tune submission is a roadmap item"）——本 skill 是把这个 stub 落成真实动作的候选后端之一
- 现场没有本地 GPU，但要跑微调实验
- 交付产物需要一个可直接调用的 Hub 模型，或需要 GGUF 让客户在内网笔记本上跑

**不用于**：本地 GPU 训练（→ [trl-training](trl-training.md)）；百炼平台客户（→ [bailian-train-deploy](../zone-b-build/bailian-train-deploy.md)，数据不出阿里云）；视觉模型（→ [huggingface-vision-trainer](huggingface-vision-trainer.md)）；**含客户数据**的训练（HF Jobs 会把数据传到 Hub——合规红线）。

## 最佳实践
- ⚠️ **数据出境判断**：HF Jobs 需要把数据集上传 Hub（即便 private repo）。工业客户/政企默认视为不可接受，须书面确认后才用；否则一律走本地/私有云训练
- 先成本预估再提交：明确 GPU 型号与时长，demo 用最小规格，跑通即停
- 数据集准备阶段就用 skill 的 validate 流程，训练失败往往源于格式与字段缺失
- 训练与评估闭环：Trackio 曲线留档 → 用 [huggingface-community-evals](../zone-b-build/huggingface-community-evals.md) + `fde_scope.eval` 双证，再谈上线
- 版本可追溯：记录 base model revision + dataset hash + 训练配置，写进 engagement 记录（交接必需）
- GGUF 转换只在"客户要离线本地跑"时用，别为省事牺牲精度

## 项目应用位点
- Zone C `flywheel`：周度增量重训的执行后端候选（配合 [schedule](../cross-cutting/schedule.md)）
- Zone B `validate`：LoRA/SFT 实验的云端算力来源

## 相关
[trl-training](trl-training.md) · [huggingface-vision-trainer](huggingface-vision-trainer.md) · [bailian-train-deploy](../zone-b-build/bailian-train-deploy.md)

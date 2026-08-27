# bailian-train-deploy

> 状态：✅ 已安装 · 类型：工作流/平台 · FDE 位点：Zone B validate/deploy + Zone C flywheel
> 依赖：`bl` CLI + 百炼平台账号（需 API key；写操作先 `--dry-run`）

## 能做什么
用百炼 CLI 走完「数据→微调训练→导出→部署→调用」完整闭环，或跳过训练直接部署基座模型。覆盖文本（SFT/DPO/CPT）、TTS（CosyVoice）、图像（Wan2.7）、视频（Wan i2v/kf2v）微调。

## 何时使用
- 涉及百炼/DashScope 的"训练/微调/精调/部署模型/上线/LoRA/SFT/DPO"任何环节——即使用户没点名 `bl`
- 数据飞轮回流后的周期性重训（`fde_scope.flywheel.retrain_scheduler` 的落地执行器）

**不用于**：火山方舟 ark 精调；本地 GPU 训练（→ trl-training / huggingface-llm-trainer）；纯选型（→ bailian-model-recommend）。

## 最佳实践
- Do：链路固定为 validate 数据 → upload 拿 file-id → finetune create → watch → export → deploy，**不要跳步**
- Do：所有写操作先 `--dry-run` 预览再执行
- Do：数据集格式在 validate 阶段就对齐模板，省得训练失败再查
- Don't：不要凭记忆拼 `bl` 参数；不要未 watch 完成就 export
- 成本：训练/部署按时长计费，demo 用最小规格，验证通就下线

## 项目应用位点
- Zone B `validate→deploy`：微调产物的真实落地路径
- Zone C flywheel：bad case 回流 → 周度重训 → 新模型再部署
- docs/llm_integration.md 中 MiMo 之外的平台侧选项

## 相关
[bailian-cli](../cross-cutting/bailian-cli.md) · [trl-training](../zone-c-operationalization/trl-training.md) · [huggingface-llm-trainer](../zone-c-operationalization/huggingface-llm-trainer.md)

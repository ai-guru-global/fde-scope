# huggingface-vision-trainer

> 状态：✅ 已安装（hugging-face 插件 v1.0.0）· 类型：视觉训练 · FDE 位点：Zone B/C 具身与制造业场景

## 能做什么
在 Transformers + HF Jobs 云 GPU 上训练/微调视觉模型：目标检测（D-FINE、RT-DETR v2、DETR、YOLOS）、图像分类（timm：MobileNetV3、MobileViT、ResNet、ViT/DINOv3 等）、SAM/SAM2 分割（bbox/point prompt、DiceCE loss）。含 COCO 格式数据准备、Albumentations 增强、mAP/mAR 与准确率评估、硬件选型、成本预估、Trackio 监控、Hub 持久化。

## 何时使用
- 制造业/具身机器人场景的视觉质检、部件定位、抓取前分割（fde-scope 的 manufacturing profile 延伸能力）
- 客户只有几百张标注图，需要小样本微调而不是从零训练
- 需要在边缘设备上跑分类 → 先用 MobileNetV3/MobileViT 这类小模型验证可行性

**不用于**：LLM/文本微调（→ [trl-training](trl-training.md) / [huggingface-llm-trainer](huggingface-llm-trainer.md)）；ROS2 bag 的解析与数据集导出（→ `fde_scope/connectors/ros2_bag.py`）；数据不出厂客户（HF Jobs 需上传数据，先做合规判断）。

## 最佳实践
- 数据格式先对齐 COCO（bbox 归一化/类别映射最容易出错），再谈模型选择
- 模型选择从任务反推：实时性优先 RT-DETR/MobileViT；精度优先 D-FINE/DINOv3；标注少考虑 SAM 交互式分割补标
- 指标口径要提前和客户书面确认（mAP@0.5 还是 @0.5:0.95），验收扯皮多源于此
- 增强策略保守：工业图像不要乱用颜色抖动（会破坏缺陷判据）
- 算力成本：先 1 个 epoch 小样本验证收敛趋势，再放全量；Trackio 曲线存档进交付记录
- 与 fde-scope 衔接：训练产物的评估报告应接入 `EvalReport` 形式，保持交付材料同一口径

## 项目应用位点
- Zone B `manufacturing`：视觉质检模型的小样本微调
- Zone C：缺陷类型漂移后的再训练（flywheel 视觉分支）

## 相关
[trl-training](trl-training.md) · [huggingface-llm-trainer](huggingface-llm-trainer.md) · [huggingface-datasets](../zone-b-build/huggingface-datasets.md)

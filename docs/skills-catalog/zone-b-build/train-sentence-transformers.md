# train-sentence-transformers

> 状态：✅ 已安装 · 类型：训练/领域 · FDE 位点：Zone B corpus + Zone C flywheel

## 能做什么
训练/精调 sentence-transformers 全家族：`SentenceTransformer`（双塔嵌入：检索、相似、聚类、分类、 paraphrase 挖掘、去重、多模态）、`CrossEncoder`（重排器/ pair 分类）、`SparseEncoder`（SPLADE 稀疏检索）。覆盖损失选择、难负例挖掘、评估器、LoRA、Matryoshka、Hub 发布。

## 何时使用
- 语料工程需要**领域定制嵌入模型**：工单相似检索、故障案例去重、告警聚类
- `fde_scope.corpus` 的语义去重/覆盖度分析用通用模型效果不够时

**不用于**：生成式 LLM 微调（→ bailian-train-deploy / trl-training）；只是调 API 检索（平台侧知识库解决）。

## 新人上手

- **触发**：要训/精调嵌入或重排模型时说「训练 sentence-transformers」「微调个 embedding 模型」「训个 reranker」（skill description：any sentence-transformers training task；先按双塔/重排/稀疏三类定位模型类型）
- **第一步**：别让 agent 从零写训练脚本——SKILL.md 开头明说"this is a router, not a manual"：确定类型后复制对应生产模板 `scripts/train_<type>_example.py` 起步，并完整读 `references/losses_*.md` 的损失-数据形状映射
- **常见坑**：CrossEncoder 非 BCE 损失必须 `activation_fn=Identity()`，漏了会"silent eval-rank collapse"（SKILL.md 原话）；MNRL 损失族要求 `BatchSamplers.NO_DUPLICATES` 采样器，随机负例直接训错
- **常见坑**：精度别写 `torch_dtype=bfloat16`——规则是 fp32 加载 + autocast（bf16/fp16）；`save_steps` 必须是 `eval_steps` 的倍数，否则 `load_best_model_at_end` 不生效。训前先跑现成模型 baseline（recall@k），不够再训

## 最佳实践
- Do：先拿现成模型跑 baseline 并量化（recall@k / 聚类纯度），不够再训——训练是最后手段
- Do：难负例挖掘（hard-negative mining）是效果大头，别只喂随机负例
- Do：Matryoshka 维度裁剪（如 1024→256）省现场存储与延迟
- Don't：不要在无标注数据时盲目对比学习"试试"；先把 bad case 判读做成标注集
- 组合：bad_case_miner 产出 → 本技能训练 → 部署进 KnowledgeBase collection

## 项目应用位点
- Zone B corpus：语义去重、覆盖度聚类的嵌入内核
- Zone C flywheel：周期性重训的检索侧分支（区别于生成侧）

## 相关
[trl-training](../zone-c-operationalization/trl-training.md) · [huggingface-datasets](huggingface-datasets.md) · [bailian-train-deploy](bailian-train-deploy.md)

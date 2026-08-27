# train-sentence-transformers

> 状态：✅ 已安装 · 类型：训练/领域 · FDE 位点：Zone B corpus + Zone C flywheel

## 能做什么
训练/精调 sentence-transformers 全家族：`SentenceTransformer`（双塔嵌入：检索、相似、聚类、分类、 paraphrase 挖掘、去重、多模态）、`CrossEncoder`（重排器/ pair 分类）、`SparseEncoder`（SPLADE 稀疏检索）。覆盖损失选择、难负例挖掘、评估器、LoRA、Matryoshka、Hub 发布。

## 何时使用
- 语料工程需要**领域定制嵌入模型**：工单相似检索、故障案例去重、告警聚类
- `fde_scope.corpus` 的语义去重/覆盖度分析用通用模型效果不够时

**不用于**：生成式 LLM 微调（→ bailian-train-deploy / trl-training）；只是调 API 检索（平台侧知识库解决）。

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

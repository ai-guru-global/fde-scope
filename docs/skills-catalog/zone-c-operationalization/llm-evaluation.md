# llm-evaluation

> 状态：📦 可安装（registry 真名 `wshobson/agents@llm-evaluation`）· 类型：方法论 · FDE 位点：Zone C · 飞轮重训/评估验收（反哺 Zone B validate）
> 安装：`npx skills add wshobson/agents@llm-evaluation --directory ~/.qoder/skills -y` · 装机量：10.7K（skills.sh，2026-08-31）· 详情：https://skills.sh/wshobson/agents/llm-evaluation

## 能做什么
LLM 评估**方案设计**的方法论套件（wshobson/agents 大库中 `llm-application-dev` 插件下的单 skill）：怎么选指标、怎么设计数据集与 judge、怎么定验收线。覆盖三层：自动化指标（生成：BLEU / ROUGE / METEOR / BERTScore / Perplexity；分类：accuracy / precision / recall / F1 / AUC-ROC；RAG 检索：MRR / NDCG / Precision@K / Recall@K）、人工评估六维（accuracy / coherence / relevance / fluency / safety / helpfulness）、LLM-as-judge 四式（pointwise / pairwise / reference-based / reference-free）。进阶内容在套件内 `references/details.md`：标注者间一致性（Cohen's kappa 分档：<0.2 Slight → ≥0.8 Almost Perfect）、A/B 显著性检验（scipy.stats，alpha=0.05）、回归检测、benchmarking，并附 `EvaluationSuite` / `Metric` dataclass 代码骨架。

## 何时使用
- 交付前要给客户**定义"质量验收标准"**：哪些指标、多少分算过、judge 怎么设计——评估方案本身的验收设计
- 飞轮重训前后要证明"真的变好了"：A/B 显著性检验 + 回归检测，而不是贴单点分数
- 挑模型/prompt 方案对比，需要建立 baseline 并长期追踪
- 客户问"你们怎么证明这个 agent 比上一版好"时的方案设计依据

**不用于**：具体评估器的代码实现（→ [phoenix-evals](../zone-b-build/phoenix-evals.md)，管 code-first + LLM-as-judge 指标开发）；公开 benchmark 跑分的封装与执行（→ [evaluating-llms-harness](../zone-b-build/evaluating-llms-harness.md) 管 lm-eval 封装、[huggingface-community-evals](../zone-b-build/huggingface-community-evals.md) 管 benchmark 运行）。分工一句话：那三页管"做评估"，这页管"评估方案怎么验收"。

## 新人上手
- **触发**：对 agent 说"设计一套验收标准证明重训有效"、"这个 LLM 应用该怎么评估"、"对比两个 prompt 的方案怎么定胜负"
- **第一步**：装好后让 agent 按套件框架先出**评估方案文档**：指标选型（生成/分类/RAG 各对应哪组指标）→ 数据集构成（含 bad case 占比）→ judge 设计（pointwise/pairwise 选型 + 一致性验收线）→ 再动手写评估代码
- **常见坑**：LLM-as-judge 分数直接对客户讲话——套件明确要求先做 inter-rater agreement（Cohen's kappa），kappa 低于 0.6（Moderate 以下）时 judge 结论不可信，先修标注指南再上量
- **常见坑**：A/B 只报均值不看显著性——套件的统计框架用 alpha=0.05；样本量不足时"提升 3%"可能只是噪声，别拿去当验收证据

## 最佳实践
- 指标跟着任务形态走：生成类别硬套 accuracy 没意义，RAG 检索优先 Recall@K/NDCG，别一把 BLEU 撒到底
- 分层评估：自动化指标做回归门禁（快、可重复），judge + 人工抽查做质量验收（慢、可信），两层都要有
- 回归检测是底线：prompt 或模型一换，先跑同一批回归集确认没把老 case 改坏
- 方案先行：数据集 → judge → 验收线写进交付文档并让客户签字，评估结果才有"证据"效力
- 与 fde-scope 整合：验收线落地为 `fde_scope/eval/` 里 `METRICS` 注册的具体指标，方案文档只管"为什么是这些指标、线画在哪"

## 项目应用位点
- Zone B `validate`：18-phase 交付里 LLM 环节的验收标准设计（本页出方案，phoenix-evals 出实现）
- Zone C SLO gate：LLM 服务的质量 SLO 定义（如回答解决率 ≥ X%，judge + kappa 支撑）
- 飞轮重训：`BadCaseMiner` 挖出的 bad case 进数据集，重训后 A/B + 回归检测证明提升
- 客户验收材料：评估方案文档作为交付物之一

## 相关
[phoenix-evals](../zone-b-build/phoenix-evals.md) · [evaluating-llms-harness](../zone-b-build/evaluating-llms-harness.md) · [huggingface-community-evals](../zone-b-build/huggingface-community-evals.md)

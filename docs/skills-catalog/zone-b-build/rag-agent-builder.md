# rag-agent-builder 📦

> 状态：📦 可安装（未装）· 类型：工作流 · FDE 位点：Zone B prototype/deploy
> 来源：`qodex-ai/ai-agent-skills@rag-agent-builder` · 热度：239 installs · 详情：https://skills.sh/qodex-ai/ai-agent-skills/rag-agent-builder
> 安装：`npx skills add qodex-ai/ai-agent-skills@rag-agent-builder --directory ~/.qoder/skills -y`

## 能做什么
RAG 智能体搭建流程参考：检索管道组织、知识库接线、生成端拼装。

## 何时使用
- 给客户做"文档问答/工单辅助"类 RAG demo，想要一套现成套路
- 补 Corpus 产物 → 可服务知识库这一环的**方法论**参考

**不用于**：百炼平台知识库（`bl knowledge` 已安装，平台路径优先）；AgentScope 的 Knowledge 体系（以 `fde_scope/deploy` 真实 API 为准，别被通用模板带偏用虚构 API）。

## 最佳实践
- 装前门禁：239 installs 属低热度社区件，**必须**先过 [skill-criticagent](../cross-cutting/skill-criticagent.md)，重点审它推荐的 API 是否真实存在（本项目 docs/agentscope_api_mapping.md 就是为虚构 API 坑而写的）
- 若模板与 `docs/agentscope_api_mapping.md` 的"真实 2.0.5 API"冲突，一律以本项目映射表为准
- 评估结论回写本页

## 项目应用位点
- Zone B prototype-on-real-data：语料 → 可演示问答原型
- Zone C：客户自助知识库的搭建参考

## 相关
[huggingface-datasets](huggingface-datasets.md) · [train-sentence-transformers](train-sentence-transformers.md) · [bailian-cli](../cross-cutting/bailian-cli.md)

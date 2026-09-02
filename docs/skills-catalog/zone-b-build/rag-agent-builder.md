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

## 新人上手

- **触发**：给客户做"文档问答/工单辅助"类 RAG demo、想要现成搭建套路时说「帮我搭一个 RAG 智能体」（页面"何时使用"；该 skill 尚未安装，先装再问）
- **第一步**：装前先让 agent 过 [skill-criticagent](../cross-cutting/skill-criticagent.md) 门禁（重点审它推荐的 API 是否真实存在），通过后执行 `npx skills add qodex-ai/ai-agent-skills@rag-agent-builder --directory ~/.qoder/skills -y`，再按"检索管道→知识库接线→生成端拼装"的流程走
- **常见坑**：低热度社区模板最容易教 agent 编造 API：与 docs/agentscope_api_mapping.md 的"真实 2.0.5 API"冲突时一律以映射表为准，照抄模板虚构调用会直接跑不通
- **常见坑**：百炼知识库走已装的 `bl knowledge` 平台路径，AgentScope Knowledge 体系以 `fde_scope/deploy` 真实 API 为准——该模板只做方法论参考，不落地成代码

## 最佳实践
- 装前门禁：239 installs 属低热度社区件，**必须**先过 [skill-criticagent](../cross-cutting/skill-criticagent.md)，重点审它推荐的 API 是否真实存在（本项目 docs/agentscope_api_mapping.md 就是为虚构 API 坑而写的）
- 若模板与 `docs/agentscope_api_mapping.md` 的"真实 2.0.5 API"冲突，一律以本项目映射表为准
- 评估结论回写本页

## 项目应用位点
- Zone B prototype-on-real-data：语料 → 可演示问答原型
- Zone C：客户自助知识库的搭建参考

## 相关
[huggingface-datasets](huggingface-datasets.md) · [train-sentence-transformers](train-sentence-transformers.md) · [bailian-cli](../cross-cutting/bailian-cli.md)

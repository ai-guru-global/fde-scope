# prompt-engineering-patterns

> 状态：📦 可安装 · registry 真名 `wshobson/agents@prompt-engineering-patterns`（与建档名一致）· 类型：领域知识 · FDE 位点：Zone B · 语料/原型（LLM 功能 prompt 质量）
> 安装：`npx skills add wshobson/agents@prompt-engineering-patterns --directory ~/.qoder/skills -y` · 装机量：20.7K（skills.sh，2026-08-31）· 详情：https://skills.sh/wshobson/agents/prompt-engineering-patterns

## 能做什么
面向生产环境的 prompt 工程模式库（wshobson/agents 套件成员）：few-shot 动态示例选择、CoT 推理 + self-consistency、JSON/Pydantic 结构化输出约束、角色化 system prompt 设计、语义示例选择 + self-verification、错误恢复（fallback 与 RAG 集成）、路由（routing）与护栏（guardrails）、迭代式 prompt 优化与可复用模板体系。它不改代码，改的是"喂给模型的指令质量"。

## 何时使用
- 客户 LLM 功能上线前 prompt 质量评审：按模式清单逐条过，找出缺结构化约束、缺错误恢复的裸 prompt
- 输出不稳定（JSON 解析失败、格式漂移）时套结构化输出 + self-verification 模式
- bad case 修复没有抓手时，用模式库做系统化归因，替代凭感觉改词

**不用于**：评估指标与打分（→ [phoenix-evals](phoenix-evals.md)）；RAG 检索链路本身（→ [rag-agent-builder](rag-agent-builder.md)）——本页只管 prompt 侧。

## 新人上手
- **触发**：对 agent 说"用 prompt-engineering-patterns 把这段 prompt 过一遍，输出不稳定按结构化输出模式重构"
- **第一步**：装完后选一段真实业务 prompt（如工单摘要），让 agent 对照模式库标注缺失项，先补结构化输出（JSON schema 约束）——对稳定性收益最直接
- **常见坑**：skill 自身提醒避免 over-engineering、context overflow、ambiguous instructions——别把所有模式堆进一个 prompt，每加一个模式要能说清解决什么问题
- **常见坑**：few-shot 示例是模式库的通用例，中文客户语料上必须换成客户领域样本，照搬会带偏输出风格

## 最佳实践
- 先量化基线再改：改前改后跑同一批样本（配合 [phoenix-evals](phoenix-evals.md) 的规则指标/judge），没有数据支撑的"感觉变好"不算数
- 一次只引入一个模式，验证有效再叠加
- 结构化输出用 schema 约束而不是"请输出 JSON"的口头要求；错误恢复（fallback/重试）写进调用侧逻辑，别指望 prompt 求模型
- prompt 变更进版本管理与评审，与代码同等待遇

## 项目应用位点
- Zone B 语料/原型阶段：客户 LLM 功能的 prompt 质量工作台
- `fde_scope/llm.py` 调用侧 system prompt 的设计评审参考
- Zone C 观测发现输出漂移后，回调 prompt 的模式化修法

## 相关
[rag-agent-builder](rag-agent-builder.md) · [bailian-train-deploy](bailian-train-deploy.md) · [../zone-d-handoff/anthropic-documentation](../zone-d-handoff/anthropic-documentation.md)

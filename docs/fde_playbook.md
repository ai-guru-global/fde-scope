# FDE 现场操作手册（Playbook）

> 这是 FDE（前线部署工程师）到客户现场的 72 小时操作流程。
> 每一步对应 `fde-scope` 的一个子命令。

## Day 1 上午 — 接入数据

客户能给你什么？CSV 导出 / Zammad API / Salesforce / 数据库直连 / 邮件。

```bash
# 先看一眼数据长什么样（look before you load）
fde-scope connect --type csv --source ./client_export.csv
# ✅ Discovered N tickets, M categories, K channels.
# ✅ Sample extracted → ./samples/preview.json
```

**关注点**：
- 字段是否齐全（content / category / id）？
- PII 候选字段（schema 标 ⚠）—— 决定脱敏规则强度。
- 类别分布是否极度不均衡 —— 预告后面要合成补盲。

## Day 1 下午 — 锻造语料

```bash
fde-scope corpus \
  --input ./client_export.csv \
  --config fde_scope/templates/corpus_config.yaml \
  --out reports/corpus_report.html
# 可选：用 MiMo 合成更真实的补盲样本（需 FDE_SCOPE_MIMO_API_KEY，
# 失败自动回退规则路径；逐类合成+逐条评分，小数据集约几分钟）
fde-scope corpus --input ./client_export.csv --out reports/corpus_report.html --llm
```

**拿 CorpusReport 跟客户对齐预期**：
- 「你的原始数据 N 条，清洗后 M 条可用（去重 X、质量门淘汰 Y）」
- 「PII 脱敏了 Z 个实体」
- 「发现 K 个覆盖盲区，已针对性合成补齐」（LLM 样本 trace 为 `synthesize:llm`，
  同样过质量门与缺口上限，可审计）
- 「最终 train/eval/test = a/b/c」

> **核心差异化**：合成是「补盲区」，不是「凑数量」。每一条合成样本都有对应的缺口理由。

## Day 2 — 部署 Agent

```bash
fde-scope deploy --tenant client_a --corpus reports/corpus_report.json --model qwen-max
```

**三层隔离交付**：
1. Docker 沙箱（执行隔离）
2. `corpus_client_a` collection（数据隔离）
3. PermissionEngine 规则（权限隔离：禁跨租户、禁删、禁 shell）

> 真实启动需要 `[agentscope]` extra + docker。本期 dry-run 出 manifest。

## Day 2 下午 — 评估

```bash
# 规则版 mock Agent（零配置）或 MiMo 真实 LLM Agent（需 FDE_SCOPE_MIMO_API_KEY）
fde-scope eval --agent mock --test-set ./corpus/test/
fde-scope eval --agent mimo --test-set ./corpus/test/
# 📊 Intent Accuracy:     91.3%
# 📊 Reply Adoption:      78.5%
# ⚠ Top bad case: 跨品类退换货 (accuracy: 62%)
# 💡 建议：补充跨品类退换货语料 ~150 条
```

**用数据说话**：FDE 不是「跑个 demo 就走」，而是用评估框架证明价值。
**bad_cases 是持续调优的抓手**。

## 持续运行 — 飞轮

```bash
fde-scope flywheel start --agent client_a
# [human_override] +1 golden sample
# [low_confidence] +3 queued for labeling
# [weekly_retrain] scheduled: next Mon 02:00
```

线上反馈自动回流：人工覆盖 = 最高质量标注（quality 5.0）→ 周度增量微调 → 持续进化。

## 面试追问防御

| 追问 | 回答要点 |
|---|---|
| FDE 和传统实施工程师区别？ | FDE 是 AI 原生——不是装软件，是让 Agent 在客户业务里跑起来并持续进化。懂模型、懂语料、懂评估 |
| 为什么 AgentScope 不用 LangGraph？ | 2.0 把多租户沙箱、权限引擎、HITL、事件系统做成了框架级能力。LangGraph 这些全要自己造 |
| 语料合成怎么保证质量？ | 三道关：策略约束 → 质量门控打分 → 覆盖度验证确实填了盲区 |
| 客户现场没有外网/不想用外部 LLM？ | 全链路规则路径可跑，LLM 纯可选（`llm.py` 可选注入，无 key 自动降级，失败自动回退）；air-gap 部署也不受影响 |
| LLM 合成的样本能信吗？ | 与规则样本同一质量门与缺口上限，逐条打分后入库，trace 可区分来源；对客户如实报告合成比例 |
| 多租户数据泄露怎么防？ | 三层隔离：Docker 沙箱 + collection + PermissionEngine（BYPASS 都绕不过） |
| 客户数据质量极差？ | Connector 先 schema 探测 + 样本预览；CorpusReport 明确告诉客户「能用多少、缺什么」 |
| 和 Dify/Coze 区别？ | 它们是给业务人员的低代码平台；FDE Scope 是给 FDE 工程师的专业工具，强调语料工程深度、评估、多租户运维 |

# gdpr-data-handling

> 状态：📦 可安装（registry 真名 `wshobson/agents@gdpr-data-handling`）· 类型：合规方法论 · FDE 位点：Zone C · 合规交付/数据处理设计
> 安装：`npx skills add wshobson/agents@gdpr-data-handling --directory ~/.qoder/skills -y` · 装机量：13.1K（skills.sh，2026-08-31）· 详情：https://skills.sh/wshobson/agents/gdpr-data-handling

## 能做什么
GDPR 合规数据处理的**实操模式库**（wshobson/agents 大库中 `hr-legal-compliance` 插件下的单 skill）：个人数据分级（基础数据 / Art. 9 敏感数据→明示同意 / Art. 10 犯罪数据 / 儿童 <16→监护人同意）、Article 6 六项合法处理依据（同意 / 合同履行 / 法律义务 / 生命攸关 / 公共利益 / 正当利益平衡）、数据主体权利八项（Art. 15 访问、16 更正、17 删除、18 限制、20 可携、21 反对——需在**一个月内**响应）。进阶内容在套件内 `references/details.md`：五个实现模式（同意管理 Consent Management、DSAR 数据主体访问请求、数据留存 Data Retention、Privacy by Design、泄露通知 Breach Notification）加两份合规 checklist。

## 何时使用
- 企业交付涉及**欧盟个人数据**：方案设计阶段就要把同意、留存、DSAR 支持画进架构
- 客户要做 GDPR 合规审查/差距评估：拿套件的 checklist 逐条过
- 评估系统边界时判断"这个数据能不能进 LLM"：敏感数据分级 + 合法依据匹配
- 跨境传输方案评审：是否有 SCC（标准合同条款）或充分性认定支撑

**不用于**：非欧盟辖区的通用安全加固（→ [security-scan](../cross-cutting/security-scan.md) 管代码/依赖漏洞扫描）；安全事件发生后的处置流程（→ [incident-response](incident-response.md)；GDPR 泄露通知只是其中合规侧输入）。同主题低装机备选：`ruvnet/ruflo@pii-detect`（751 装，偏 PII 检测脱敏落地）、`alirezarezvani/claude-skills@soc2-compliance`（643 装，SOC 2 审计支持）——SOC 2 场景用后者更对口。

## 新人上手
- **触发**：对 agent 说"这个系统要处理欧盟用户数据，帮我过一遍 GDPR 要求"、"设计同意管理和数据删除流程"
- **第一步**：装好后让 agent 按套件做**数据映射**：盘出系统里全部个人数据字段 → 逐字段定级（是否 Art. 9 敏感）→ 逐字段挂 Article 6 合法依据 → 输出处理活动记录，这是后续一切合规动作的底账
- **常见坑**：同意框预勾选直接不合规（必须 opt-in），且不同目的**不得捆绑同意**——"勾了同意框顺便用于营销"是典型翻车点；DSAR 响应时限是一个月（约 30 天），没留处理通道的客户环境要提前补，别等请求来了现搭
- **常见坑**：跨境传输无保障机制即违规——给客户 LLM 环节选型时，judge/推理用外部模型意味着客户原文出境，欧盟数据场景必须换本地模型或确认 SCC 已签（呼应 [phoenix-evals](../zone-b-build/phoenix-evals.md) 的本地 judge 主张）

## 最佳实践
- 数据最小化是第一原则：能不收集就不收集，收集的字段必须有对应合法依据和用途留痕
- 留存策略要**可执行**：定义了留存期就要有自动清理机制，"定义了但没人删"等于没定义
- PII 静态 + 传输全链路加密，访问控制按 need-to-know 收紧
- 合规证据进交付文档：处理活动记录、同意日志、DSAR 处理 SLA 写进客户交接材料
- Do/Don't 对照（套件原文主张）：Do——最小化收集、全程留痕、加密 PII、最小权限、定期审计；Don't——预勾选同意框、捆绑同意、无限留存、忽视 DSAR、无 SCC 就跨境传输

## 项目应用位点
- Zone C 变更/交付 phase：涉欧盟数据客户的合规设计评审，checklist 进 gate 材料
- 部署 checklist 扩展：DSAR 支持通道、留存清理任务作为上线前检查项（→ [deploy-checklist](deploy-checklist.md)）
- 飞轮重训的数据边界：训练/评估数据集中的个人数据需满足留存与合法依据约束
- 制造业客户出海欧盟的产线数据（含工人个人信息）合规方案

## 相关
[deploy-checklist](deploy-checklist.md) · [incident-response](incident-response.md) · [security-scan](../cross-cutting/security-scan.md)

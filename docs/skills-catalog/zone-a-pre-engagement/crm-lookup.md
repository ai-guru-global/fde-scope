# crm-lookup

> 状态：📦 可安装（未装；registry 真名 `hubspot/agent-cli-skills@crm-lookup`，与建档名一致）· 类型：数据查询（CRM 只读检索）· FDE 位点：Zone A · qualification（客户背景调研）
> 安装：`npx skills add hubspot/agent-cli-skills@crm-lookup --directory ~/.qoder/skills -y` · 装机量：1.2K（skills.sh，2026-08-31）· 详情：https://skills.sh/hubspot/agent-cli-skills/crm-lookup
> 说明：HubSpot 官方 agent CLI skill 仓库。同仓库兄弟条目：`deal-management`（成交全生命周期）、`workflow-automation`（workflow 增删改查）、`crm-data-quality`——注意 README 里写作 **`crm-data-quality`** 而非 `data-quality`，检索时别拼错。

## 能做什么
HubSpot 官方出品的**只读** CRM 检索 skill：按 ID / 邮箱 / 域名 / 名称找记录（contacts、companies、deals、tickets 四类对象），并遍历 associations 关联关系。本质是教 agent 正确使用 HubSpot CLI 的查询与关联命令，避免凭记忆拼 API。只查不写——写入类操作在同仓库 `deal-management` / `workflow-automation`（本库未建档）。

## 何时使用
- Pre-engagement 摸底：客户在 HubSpot 上，先查其 pipeline 各阶段 deal 分布、关键联系人、ticket 历史痛点
- 现场对接前确认数据面：查客户 CRM 已有的对象/字段命名，为集成方案对齐 schema

**不用于**：CRM 写操作（创建/更新 deal、改 workflow——同仓库兄弟条目负责）；非 HubSpot CRM（Salesforce/自建 ERP 不覆盖，方法论可参照）。

## 新人上手

- **触发**："在客户 HubSpot 里查一下 Acme 的 open deals 和关键联系人"
- **第一步**：安装后先校准 schema 再查询：`hubspot properties list` 确认对象属性名，然后精确查询 `--filter "email=jane@acme.com"`，子串匹配用 `dealname~acme`（skills.sh 页原文示例）
- **常见坑**：子串匹配（`~`）的原始结果要接 `jq` 处理；查关联记录的正规姿势是 `associations list` 管道给 `jq` 之后**分批** `objects get`——skill 原文点名 **never use xargs**（进程数爆炸）
- **常见坑**：schema 会漂移（skill 原话 "schemas drift"），别按记忆猜 property 名；认证/token 的初始化步骤在抓取的 README 页未见写明，装前详见官方 README

## 最佳实践
- Do：只读定位——本 skill 天然 read-only，适合在客户环境做无副作用的 pre-engagement 调研
- Do：每次会话先 `hubspot properties list` 校准字段，再写查询
- Don't：不用 xargs 批量拉关联对象；不把查询逻辑固化成脚本——schema 漂移会让脚本静默失真
- Don't：客户 CRM 数据（联系人、pipeline 金额）是敏感商业数据，不进交付文档/日志/engagement JSON

## 项目应用位点
- Zone A `qualification`：客户背景调研的 CRM 通道，与公开网页通道 [firecrawl-search](firecrawl-search.md) 互补
- 制造业客户多用自建 CRM/ERP：非 HubSpot 时本页作方法论参照（CLI + 只读过滤 + 关联遍历的通用姿势）
- 查得的 pipeline/ticket 摘要可作 kickoff 材料与 success-criteria 的证据输入

## 相关
[brainstorming](brainstorming.md) · [architecture-communicator](architecture-communicator.md) · [firecrawl-search](firecrawl-search.md)

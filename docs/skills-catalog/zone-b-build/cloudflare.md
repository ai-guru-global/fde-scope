# cloudflare

> 状态：✅ 已安装（cloudflare 插件 v1.0.0，同插件含 workers-best-practices / durable-objects / web-perf / wrangler / agents-sdk 等）· 类型：平台/决策树 · FDE 位点：Zone B deploy（边缘/无服务器）

## 能做什么
Cloudflare 全平台决策树 + 实现指导：Workers / Pages / KV / D1 / R2 / Queues / Vectorize / Durable Objects / Workflows / Containers / Tunnel / Spectrum / WAF / Flagship 特性开关 / Terraform & Pulumi。**内置强约束：极限值、定价、API 签名必须从 Cloudflare docs 检索，不许凭记忆**。

## 何时使用
- 客户要"零运维 + 全球低延迟"的轻量交付面（看板、上报页、Agent 端点）
- 需要选型：这段逻辑该放 Worker、Pages Function 还是 Durable Object
- 需要边缘侧存储/向量检索（R2 + Vectorize）而不是自建集群

**不用于**：客户内网离线部署（Cloudflare 依赖公网 → [docker-build-deploy](docker-build-deploy.md) / [kubernetes-specialist](kubernetes-specialist.md)）；GPU 推理（→ [vllm-deploy-docker](vllm-deploy-docker.md)，Workers AI 只适合小模型）。

## 最佳实践
- 严格遵守 skill 的 retrieval 规则：引用数字/价格/限额前先拉最新 docs，reference 文件与 docs 冲突时**以 docs 为准**
- 用 `wrangler` 做本地 dev + 类型校验，别在生产 Worker 上试错
- 数据边界：客户数据入边缘存储前必须确认可出境/合规条款，工业客户通常禁止 → 默认只放配置与匿名指标
- 成本：Workers 免费额度适合 demo，规模化前先算 request/GB-s

## 项目应用位点
- Zone B deploy：面向多客户分支的轻量看板 / 遥测接收端点
- Zone C：`web-perf`（同插件）用于交付 Web 面板的 Core Web Vitals 分析

## 相关
[docker-build-deploy](docker-build-deploy.md) · [kubernetes-specialist](kubernetes-specialist.md) · [web-perf](../zone-c-operationalization/web-perf.md)

# cloudflare-docs（MCP server）

> 状态：✅ 已连接（插件 cloudflare v1.0.0，文档检索子 server）· 类型：MCP 服务器 · **2 个工具** · FDE 位点：Zone B 部署
> 平台技能族：[cloudflare](../zone-b-build/cloudflare.md)（Workers/Pages/KV 等全部 skill）

## 能做什么

Cloudflare **官方文档**的检索工具面，只有 2 个工具但定位关键：

- `search_cloudflare_documentation`：按自然语言检索 CF 官方文档，返回相关页面与要点——文档是持续更新的，检索结果比任何模型记忆都新
- `migrate_pages_to_workers_guide`：给出 Pages 项目迁移到 Workers 的结构化指引（CF 官方正在主推的路线）

## 何时使用

- 写 wrangler 命令/配置 `wrangler.jsonc` 前核对**当前版本**的语法与限制（[wrangler](../zone-b-build/cloudflare.md) skill 会要求先查文档）
- 客户问"CF 现在支不支持 X / 限额是多少"——直接检索官方文档回答，不凭记忆
- Pages → Workers 迁移评估：用 `migrate_pages_to_workers_guide` 起步

**不用于**：非 Cloudflare 的问题；平台通用概念学习（先读 skill 页，有上下文再查文档）。

## 新人上手

- **触发**：对 agent 说"CF 现在支不支持 X / Durable Objects 限额是多少 / Pages 怎么迁 Workers"
- **第一步**：让 agent 用 `search_cloudflare_documentation` 检索**英文功能名**（如 `durable objects alarms`）——中文命中率低
- **常见坑**：检索结果给的是文档页面，限额/定价/破坏性变更要点进原文确认版本与日期；"我记得是……"不算答案，retrieval-first 就是本 server 存在的理由

## 最佳实践

- **retrieval-first**：CF 平台迭代快（限额、beta 产品、定价都常变），任何"我记得是……"的答案都先用本 server 验证
- 检索词用英文功能名（如 `durable objects alarms`）比中文命中率高
- 检索结果给的是文档页面：关键结论（限额/定价/破坏性变更）点进原文确认版本与日期
- 与 cloudflare 插件的 skill 族配合：skill 给方法论，本 server 给事实源

## 项目应用位点

- Zone B 部署：fde-scope 交付物上 Cloudflare（Workers/Pages/KV）时的配置与限额核对
- 客户方案书：CF 相关章节的引用来源（官方文档 > 博客 > 记忆）

## 相关

[总览](overview.md) · [cloudflare skill 页](../zone-b-build/cloudflare.md) · [vercel-deploy](../zone-b-build/vercel-deploy.md)（同为部署平台的对照）

# firecrawl（MCP server）

> 状态：✅ 已连接（插件 firecrawl v0.1.0）· 类型：MCP 服务器 · **27 个工具** · FDE 位点：Zone A 调研 / Zone C 监测
> 日常入口是 skill 页族：[firecrawl-search](../zone-a-pre-engagement/firecrawl-search.md) / [scrape](../zone-a-pre-engagement/firecrawl-scrape.md) / [crawl](../zone-a-pre-engagement/firecrawl-crawl.md) / [parse](../zone-a-pre-engagement/firecrawl-parse.md) / [monitor](../zone-c-operationalization/firecrawl-monitor.md)——本页是工具面底账与组合场景参考

## 能做什么

网页数据获取的完整 API 面，27 个工具分五族：

| 工具族 | 工具 | 用途 |
|---|---|---|
| 搜索与抽取 | `firecrawl_search` / `firecrawl_scrape` / `firecrawl_map` / `firecrawl_crawl` / `firecrawl_extract` / `firecrawl_parse` / `firecrawl_developer_search` | 联网搜索、单页/整站转 Markdown、URL 空间摸底、结构化抽取、本地文件（PDF/DOCX/HTML）解析、开发者文档检索 |
| 浏览器交互 | `firecrawl_interact` / `firecrawl_interact_stop` | 在抓取到的页面上继续点击/填表/翻页（自然语言驱动） |
| 自主 agent | `firecrawl_agent` / `firecrawl_agent_status` | 复杂站点自主导航抓取，异步提交后轮询状态 |
| 变更监测 | `firecrawl_monitor_create` / `_get` / `_list` / `_run` / `_check` / `_checks` / `_update` / `_delete` | 页面变化 → webhook/邮件告警（竞品价格、招聘、文档更新） |
| 学术研究 | `firecrawl_research_search_papers` / `search_github` / `read_paper` / `inspect_paper` / `related_papers` | 论文/GitHub 检索、原文阅读、相关论文扩展 |

另有 `firecrawl_feedback` / `firecrawl_search_feedback` 结果质量反馈通道。

## 何时使用

- **直接调工具**：skill 页没覆盖的组合场景——research 族论文链、monitor 批量管理、agent 异步抓取、`map` + `crawl` 的定点组合
- **日常单步任务走 skill**：搜索、抓单页、解析本地文件都有现成 skill 入口（见头部链接），skill 里已带参数与预算建议
- **批量语料**：`map` 摸清站点 → `crawl` 限范围 → `parse` 收尾本地文件

**不用于**：需要登录/内网的站点（用 [chrome-devtools](chrome-devtools-mcp.md) 本地会话取证）；已有结构化 API 的系统（直接 HTTP 更省额度）；对实时性要求极高且目标稳定的数据（写专用 connector 更可靠）。

## 新人上手

- **触发**：对 agent 说"搜一下 X / 抓这个网页 / 把这份 PDF 转 Markdown / 盯着这个页面有变化就告诉我"
- **第一步**：日常不用记工具名——搜、抓、解析都有 skill 入口（见页头链接），agent 自动走；想看工具面就 `mcp_list({keyword: "firecrawl"})`
- **常见坑**：`firecrawl_crawl` 按页计费，大站不先 `firecrawl_map` 摸 URL 空间就 crawl，范围失控等于账单失控；`firecrawl_extract` 不给 schema 输出就不是稳定 JSON

## 最佳实践

- `firecrawl_scrape` 直接产 Markdown，不要抓 HTML 回来自己洗；JS 渲染页确认拿到的是渲染后内容，必要时用 `firecrawl_interact` 补交互
- 大站点先 `firecrawl_map` 摸 URL 空间，再对 `firecrawl_crawl` 设定精确范围——crawl 按页计费，范围失控就是账单失控
- `firecrawl_extract` 必须给清晰 schema，输出才是稳定 JSON；没 schema 就用 scrape + 自行解析
- monitor 是唯一的**常驻产物**：建了要 `firecrawl_monitor_list` 定期巡检，不用的 `firecrawl_monitor_delete`，避免告警噪音
- research 族查论文/GitHub 快，但**引用必须回原文核验**后才允许进交付物（与 [firecrawl-search](../zone-a-pre-engagement/firecrawl-search.md) 的真实性门一致）
- 先 `mcp_get` 读 schema 再调：各工具的分页/过滤参数名不统一，凭记忆传参会静默返回空结果

## 项目应用位点

- Zone A 客户调研：search → scrape → parse → 入 QMind（[qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md)），是调研摸底的标准管线
- Zone C firecrawl-monitor 已单独立页：竞品/客户系统网页监控告警
- 客户交付：把"目标站点 → 结构化数据"封装成 monitor + extract 的组合，就是轻量级数据订阅服务

## 相关

[总览](overview.md) · [chrome-devtools](chrome-devtools-mcp.md) · [firecrawl-search](../zone-a-pre-engagement/firecrawl-search.md) · [firecrawl-monitor](../zone-c-operationalization/firecrawl-monitor.md) · [qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md)

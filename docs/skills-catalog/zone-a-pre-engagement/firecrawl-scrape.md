# firecrawl-scrape

> 状态：✅ 已安装（firecrawl 插件）· 类型：工具 · FDE 位点：Zone A/B · 调研与数据接入

## 能做什么
对给定 URL（含 JS 渲染的 SPA）抽取干净、LLM 友好的 Markdown；支持多 URL 并发、整页截图、结构化抽取。是"给我一个链接，我要它的内容"的默认解。

## 何时使用
- 用户直接给 URL 要看内容/总结
- WebFetch 拿不到的重 JS 页面
- 客户公开文档页、产品页、API 文档页的单页抓取

**不用于**：整站批量（用 [firecrawl-crawl](firecrawl-crawl.md)）、本地文件（用 [firecrawl-parse](firecrawl-parse.md)）。

## 最佳实践
- Do：优先 scrape 而不是自己写 requests+BeautifulSoup
- Do：需要页面上特定字段时用 extract/结构化模式，别拿全文再人肉找
- Don't：不抓需要登录且未配置 profile 的页面（→ interact + profile）
- 合规：只抓客户授权范围与公开页面，现场交付注意 robots/内网保密约定

## 项目应用位点
- Zone B `connect` 阶段的补充数据源（无 API 的公开网页）
- 客户产品手册在线版的快速本地化

## 相关
[firecrawl-search](firecrawl-search.md) · [firecrawl-map](#)（列 URL） · [firecrawl-interact](#)（需登录/点击）

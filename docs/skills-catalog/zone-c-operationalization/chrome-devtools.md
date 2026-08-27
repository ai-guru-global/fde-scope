# chrome-devtools

> 状态：✅ 已安装（chrome-devtools-mcp 插件 v1.2.0；同插件含 `chrome-devtools-cli`、`a11y-debugging`）· 类型：调试/自动化 · FDE 位点：Zone B demo + Zone C operate

## 能做什么
通过 MCP 高效使用 Chrome DevTools：调试网页、自动化交互（点击/输入/滚动/截图）、审查 DOM 与样式、分析网络请求瀑布、跑性能 profile、检查可访问性。

## 何时使用
- 交付的 Web 控制台/PawApp 前端出现"只在客户机器上才有"的问题（真实浏览器证据）
- 需要验证前端改动确实生效（截图 + 网络请求，而不是"代码看起来对")
- 演示前自查：控制台无 error、请求无 4xx、首屏可达

**不用于**：后端逻辑与数据问题（→ [investigate](investigate.md)）；连接失败本身（→ [troubleshooting](troubleshooting.md)）；只需要抓公开网页数据（→ [firecrawl-scrape](../zone-a-pre-engagement/firecrawl-scrape.md)）。

## 最佳实践
- 验证 UI 改动时的最小闭环：navigate → 关键交互 → 截图 → 看 console/network 四步，缺一步结论就不算验证过
- 用无头/隔离 profile 跑自动化，避免污染自己的登录态；需要客户登录态时走人工授权而不是拷 cookie
- 性能类问题不要在这里手搓，走 [web-perf](web-perf.md) / [debug-optimize-lcp](debug-optimize-lcp.md)（同族 skill 已有流程）
- 可访问性检查用同插件 `a11y-debugging`，交付给国企/海外客户时经常是硬要求
- 截图留档到 `docs/` 或 engagement 记录，作为验收证据

## 项目应用位点
- Zone B：`fde_scope/web/` 三视图与 PawApp 前端验证
- Zone D：交付演示前的自查清单（控制台干净 + 首屏达标）

## 相关
[web-perf](web-perf.md) · [debug-optimize-lcp](debug-optimize-lcp.md) · [troubleshooting](troubleshooting.md)

# web-perf

> 状态：✅ 已安装（cloudflare 插件 v1.0.0；chrome-devtools-mcp 插件亦有同名能力）· 类型：性能分析 · FDE 位点：Zone C operate（交付面板性能）

## 能做什么
用 Chrome DevTools MCP 分析 Web 性能：Core Web Vitals（LCP / INP / CLS）+ 补充指标（FCP、TBT、Speed Index），定位阻塞渲染资源、网络依赖链、布局偏移、缓存问题与可访问性缺口。**偏向实时检索最新文档**而不是凭记忆给阈值。

## 何时使用
- 客户抱怨"面板打开很慢""车间平板上卡"
- 交付前给出可量化的性能基线（数字比形容词有说服力）
- 上线后 CWV 漂移监测

**不用于**：Python 后端接口慢（→ 看服务端 profile / [starops](starops.md)）；只要 LCP 单点深挖（→ [debug-optimize-lcp](debug-optimize-lcp.md)）；内存增长问题（→ [memory-leak-debugging](memory-leak-debugging.md)）。

## 新人上手

- **触发**：对 agent 说「体检一下这个页面的性能」「为什么 Lighthouse 分数这么低」「面板打开很慢」——audit / profile / optimize page load 都算
- **第一步**：先确认 chrome-devtools MCP 可用（调一次 `navigate_page` 或 `performance_start_trace`，没有就先在 MCP 配置加 `"chrome-devtools": {"command": ["npx", "-y", "chrome-devtools-mcp@latest"]}`），然后 `navigate_page` → `performance_start_trace(autoStop: true, reload: true)` 录冷加载 trace
- **常见坑**：insight 名称跨 Chrome 版本会变——`LCPBreakdown`/`CLSCulprits` 调不通时，先看 trace 返回里的 `insightSetId` 列出可用 insight，别硬猜名字
- **常见坑**：只推荐有预估收益的动作——estimated savings 为 0ms 的渲染阻塞资源标记但不处理；给客户的建议要具体到资源（"compress hero.png (450KB) to WebP"，不是"优化图片"）

## 最佳实践
- 测量环境要固定：同一设备/网络/是否登录态，否则数字不可比；现场最好用客户真实设备测一次
- 先测后改：任何优化前先取基线，优化后复测并在交付文档里留下前后对比
- 阈值按客户 SLA 谈，不要拿 Google 推荐值直接当合同指标
- 常见收益顺序：图片/字体与阻塞资源 → 缓存与 CDN → JS 体积与初始化 → 布局稳定
- 报告输出：截图 + 指标表 + 三条以内可执行建议（客户看不完长报告）

## 项目应用位点
- Zone C：交付 Web 面板的持续性能门禁
- Zone D：验收材料中的性能证据

## 相关
[debug-optimize-lcp](debug-optimize-lcp.md) · [chrome-devtools](chrome-devtools.md) · [memory-leak-debugging](memory-leak-debugging.md)

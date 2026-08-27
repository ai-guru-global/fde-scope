# debug-optimize-lcp

> 状态：✅ 已安装（chrome-devtools-mcp 插件 v1.2.0）· 类型：性能专项 · FDE 位点：Zone C operate

## 能做什么
LCP（最大内容绘制）专项：用 DevTools MCP 工具找出拖慢首屏主内容出现的原因——资源加载链、字体阻塞、图片尺寸与优先级、渲染阻塞 CSS/JS、服务端 TTFB，并给出针对性修复与复测路径。

## 何时使用
- 用户明确说"首屏慢"/"表格第一屏要等好几秒"
- CWV 报告里 LCP 是唯一超标项
- Hero 图 / 大表格首屏渲染优化

**不用于**：全面性能体检（→ [web-perf](web-perf.md)）；交互延迟 INP 问题（→ web-perf）；后端接口本身慢（先看服务端）。

## 最佳实践
- 先确认 LCP 元素是谁（DevTools 里高亮），不同元素对应完全不同的修法，别猜
- 高频有效手段排序：预加载/优先级设置 LCP 资源 → 图片格式与尺寸 → 消除同步阻塞脚本 → 字体 `display: swap` + 预加载
- 现场带宽受限（车间 Wi-Fi/内网）时，收益最大的是**减少资源数量与体积**，而不是花哨的加载策略
- 每次只改一项并复测，LCP 波动 ±10% 属噪声，不要为了噪声改代码
- 把 LCP 数值与截图记入验收材料，避免上线后扯皮

## 项目应用位点
- Zone C：交付面板首屏性能整改
- Zone B：demo 阶段的加载体验（客户第一眼）

## 相关
[web-perf](web-perf.md) · [chrome-devtools](chrome-devtools.md) · [memory-leak-debugging](memory-leak-debugging.md)

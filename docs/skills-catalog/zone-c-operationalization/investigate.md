# investigate

> 状态：✅ 已安装（gstack 插件 v1.58.5 · 该插件共 53 个 skill）· 类型：调试方法论 · FDE 位点：Zone C operate

## 能做什么
GStack（YC CEO Garry Tan 的技能包）里的**根因导向系统排查**流程：从现象出发建立可复现证据链，逐步二分/缩小范围，反对"猜了就改"。附带同类项：`debug`、`qa`、`review`、`health`、`retro`。

## 何时使用
- 现场交付环境出现异常但原因不明（数据没进来、指标突然掉了、模型输出变差）
- 需要一个可写进交接文档的排查过程记录，而不是一次性口头解释
- 团队/客户方工程师接手前，示范"怎么查"

**不用于**：已知原因的小修改（直接改）；纯前端性能问题（→ [debug-optimize-lcp](debug-optimize-lcp.md) / [web-perf](web-perf.md)）；需要方法论约束的测试失败（→ [systematic-debugging](systematic-debugging.md)，superpowers 版更严格）。

## 最佳实践
- 先固定"复现三件套"：环境、输入、期望 vs 实际，再动代码
- 排查日志与结论落盘（`docs/incidents/` 或 engagement 记录），这是 Zone C→D 的交接资产
- gstack 是**大插件**（53 skill、含 browser/headless 工具链），只启用你实际用的几个，避免 skill 路由互相抢触发
- 与 `systematic-debugging` 二选一拍板：日常代码 bug 用 superpowers 版；现场跨系统排障用 gstack 版。两者都装时要在指令里写明优先级

## 项目应用位点
- Zone C operate：现场故障与数据异常定位
- `fde_scope/connectors/` 排障（连接器拿到空数据/超时）

## 相关
[systematic-debugging](systematic-debugging.md) · [starops](starops.md) · [chrome-devtools](chrome-devtools.md)

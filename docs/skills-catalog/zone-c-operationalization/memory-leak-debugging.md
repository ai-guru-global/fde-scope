# memory-leak-debugging

> 状态：✅ 已安装（chrome-devtools-mcp 插件 v1.2.0）· 类型：内存专项 · FDE 位点：Zone C operate

## 能做什么
诊断并解决 **JavaScript/Node.js** 内存泄漏：高内存占用与 OOM 的定位、heapsnapshot 对比分析、`memlab` 等检测工具的使用，以及常见泄漏模式（事件监听未解绑、闭包持有、缓存无上限、DOM 引用）的修复。

## 何时使用
- 交付面板长时间开着就越来越卡/崩（车间大屏、值班终端常年不刷新）
- Node 侧服务（pawapp 前端构建、脚本工具）RSS 持续上涨
- 客户运维抱怨"每天要重启一次"

**不用于**：Python 侧内存问题（fde-scope 主体是 Python，用 `tracemalloc`/`objgraph`/`memray`，此 skill 不适用）；单纯页面慢（→ [web-perf](web-perf.md)）。

## 最佳实践
- 判定前先区分"泄漏"和"高占用"：增长后趋平不是泄漏，别急着改代码
- 采集两次 heapsnapshot（操作前/重复 N 次操作后）做 diff，看** retained size 增长的对象类型**
- 用 memlab 的 repeatable flow 固化复现步骤，修完能回归
- 前端长驻场景的常见解法：列表虚拟化、事件/定时器随组件卸载清理、给缓存加 LRU 上限
- 与运维配合：设置内存告警阈值与自动 dump，现场问题才有证据

## 项目应用位点
- Zone C：长驻 Web 控制台/值班终端稳定性
- 注意：`fde_scope` 是 Python，本 skill 只覆盖交付面（前端/Node 工具链）

## 相关
[web-perf](web-perf.md) · [chrome-devtools](chrome-devtools.md) · [investigate](investigate.md)

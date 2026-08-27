# drawio

> 状态：✅ 已安装（架构可视化插件）· 类型：基础/交付格式 · FDE 位点：Zone A/D · 可编辑图交付

## 能做什么
把架构证据模型导出为 Draw.io / diagrams.net 可编辑 `.drawio` 文件，供客户方人员手工修改；含本地 Draw.io MCP 设置指引。

## 何时使用
- 用户**明确**要 Draw.io、`.drawio`、diagrams.net、"可编辑的图"或本地 Draw.io MCP
- 交付物需要客户拿回去自己改图（他们没装 Qoder/Graphviz）

**不用于**：默认出图路径（文本型 DOT/DSL 更可维护）；把 `.drawio` 当事实源。

## 最佳实践
- Do：证据模型（JSON/DOT/DSL）永远是 source of truth，Draw.io 只是派生的可编辑交付层
- Do：改了 `.drawio` 要同步回证据模型，否则下次重生成会覆盖手工修改
- Don't：不要因为"好看"而手改导出件偏离模型事实（插件明确禁止）
- 现场技巧：air-gap 客户用 diagrams.net 桌面版打开即可，无需网络

## 项目应用位点
- Zone D 移交包里给运维团队的可编辑拓扑图
- 客户评审会上现场改图答疑

## 相关
[architecture-visualization-suite](../cross-cutting/architecture-visualization-suite.md) · [architecture-communicator](architecture-communicator.md)

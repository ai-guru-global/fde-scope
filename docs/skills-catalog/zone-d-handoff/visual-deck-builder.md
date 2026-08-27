# visual-deck-builder

> 状态：✅ 已安装（research-copilot 插件 v1.0.0）· 类型：演示生成 · FDE 位点：Zone D present

## 能做什么
**图像模型驱动**的 PPT 生产：从主题/材料/论文/报告/既有幻灯片出发，每页先由图像模型生成高质量整页幻灯片图，再打包成 PPTX，并产出 manifest、预览与证据化 QA 报告；需要时可选"分层可编辑重建"。

## 何时使用
- 给客户的汇报 deck 要**视觉冲击力**（方案汇报、成果展示、现场复盘会）
- 有大量素材（文档、数据、截图）需要在半天内变成一份成型的 deck
- 需要可追溯的 deck 质量检查（它自带 QA 与证据链，比手搓 PPT 更可审计）

**不用于**：需要逐字精确可编辑的正式商务模板（客户有固定 PPT 模板时 → [pptx](pptx.md)）；代码讲解型技术分享（→ [slidev](slidev.md)）；学术答辩专用流程（research-copilot 内有更窄的学术 skill）。

## 最佳实践
- 输入材料质量决定上限：先给结构化大纲 + 关键数据表，再让它出图，否则页面会很"好看但空洞"
- 数字与结论必须回源核对：图像模型可能把图表画得"看起来对"，交付前逐个数字比对（这类错误在客户现场代价极高）
- 客户品牌模板场景不要用它硬套——改走 [pptx](pptx.md) 在模板上填内容
- QA 报告与预览留档，作为"这版 deck 已经检查过"的记录
- 生成成本高（图像模型逐页出图），先出 3 页样张确认风格再全量

## 项目应用位点
- Zone D `handoff`：结项汇报 deck
- Zone A：售前方案 deck（配合 [firecrawl-search](../zone-a-pre-engagement/firecrawl-search.md) 的行业素材）

## 相关
[pptx](pptx.md) · [slidev](slidev.md) · [notion-infographic](notion-infographic.md)

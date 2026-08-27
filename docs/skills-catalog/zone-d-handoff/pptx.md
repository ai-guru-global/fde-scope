# pptx

> 状态：✅ 已安装（`~/.qoder/skills/pptx`，文档四件套之一）· 类型：文件操作 · FDE 位点：Zone D present

## 能做什么
PowerPoint 文件级操作：从零建 deck、改现有内容、管理版式与模板、插入备注与批注、解析既有演示文稿（提取文本/结构）。是"精确可控可编辑"的那条路。

## 何时使用
- 客户给定了 **PPT 模板/VI 规范**，必须在模板上填内容
- 需要修改别人给的 deck（补数据、改结论、加附录）
- 需要读取客户既有 PPT 做现状分析（培训材料、方案历史版本）
- 交付物要客户后续自己改（必须是真幻灯片，不是整页图片）

**不用于**：追求视觉冲击且无模板约束（→ [visual-deck-builder](visual-deck-builder.md)）；开发者技术分享（→ [slidev](slidev.md)）；只需打印分发（→ [make-pdf](make-pdf.md)）。

## 最佳实践
- 图表优先用**数据驱动**（从 xlsx/CSV 生成后插入），避免手工贴截图数字（无法随数据更新）
- 中文字体与客户机版本要检查；导出前用"兼容性检查"避免字体丢失
- 每页一个结论，标题写"结论句"而不是"话题词"——汇报效率差别极大
- 版本命名 + 附录页放数据来源，防止会后扯皮（"这页的数字哪来的"）
- 与 [xlsx](../zone-a-pre-engagement/xlsx.md) 组合：指标数据出表 → 图表进 deck，保持同一份来源

## 项目应用位点
- Zone D：结项/验收/培训 deck（客户模板场景）
- Zone A：售前提案（复用既有 deck 改造）

## 相关
[visual-deck-builder](visual-deck-builder.md) · [slidev](slidev.md) · [xlsx](../zone-a-pre-engagement/xlsx.md)

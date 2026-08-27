# slidev

> 状态：✅ 已安装（slidev 插件 v1.0.0）· 类型：演示/开发者工具 · FDE 位点：Zone D present + 对内分享

## 能做什么
用 Markdown + Vue 组件写**面向开发者的 web 幻灯**：代码高亮与可运行代码块、动画、演讲者模式、组件嵌入、导出 PDF/PPTX/图片、可托管为站点。

## 何时使用
- 技术型分享：架构讲解、代码走查、培训 workshop（内容以代码/命令为主）
- 希望 deck 进版本库、和文档同源（Markdown 可 diff、可 review）
- 需要把同一份材料既当演示又当文档站点

**不用于**：客户方用 PowerPoint 流程且要交 .pptx 源件（→ [pptx](pptx.md)，Slidev 导出的 pptx 可编辑性有限）；视觉冲击型汇报（→ [visual-deck-builder](visual-deck-builder.md)）；无技术背景的听众为主的场合（交互与代码块反而是干扰）。

## 最佳实践
- 代码块只放**关键几行**（`line-numbers`、`highlight` 配合），整屏代码在投影上不可读
- 现场投影前验证字体与终端渲染（Slidev 依赖浏览器，客户机上可能缺字体/不能联网取资源）
- 离线/内网：提前 `npm i` 与资源本地化，别在现场装包
- 导出留双份：演示用网页版 + 归档用 PDF（`export`）
- 与 [document-release](document-release.md) 协作：deck 里的架构数字要与文档同源，改一处就要同步

## 项目应用位点
- Zone D：技术交接与培训 deck（客户工程师受众）
- 对内：架构评审材料（配合 `docs/architecture-model/` 的图）

## 相关
[pptx](pptx.md) · [visual-deck-builder](visual-deck-builder.md) · [make-pdf](make-pdf.md)

# make-pdf

> 状态：✅ 已安装（gstack 插件 v1.58.5）· 类型：交付排版 · FDE 位点：Zone D handoff

## 能做什么
把任意 Markdown 转成**出版级 PDF**（排版、目录、页眉页脚、代码块与表格样式），用于正式交付物与打印材料。

## 何时使用
- 客户验收要"盖章的纸质/PDF 版"：方案书、验收报告、运维手册
- 把 `docs/` 下的模型说明 + 架构图打包成一份可分发文档
- 会议材料需要 A4 固定版式（而不是让人自己打开 Markdown）

**不用于**：需要复杂图文混排与精确页位的设计稿（用专业排版/设计工具）；PowerPoint 类演示（→ [pptx](pptx.md) / [slidev](slidev.md)）；只做 Markdown 解析（→ [pdf](../zone-a-pre-engagement/pdf.md) 的读取能力）。

## 新人上手

- **触发**：对 agent 说 "make a pdf" / "export to pdf" / "turn this markdown into a pdf"（SKILL.md 触发原句）
- **第一步**：对 agent 说"把 `docs/architecture.md` 转成 PDF，加封面和目录"——对应命令 `pdf generate docs/architecture.md out.pdf --cover --toc`（二进制在 `~/.claude/skills/gstack/make-pdf/dist/pdf`）；初稿可加 `--watermark DRAFT`
- **常见坑**：
  - 二进制未构建时会报 `MAKE_PDF_NOT_AVAILABLE`：先在 gstack 仓库根目录跑 `./setup` 构建出 `make-pdf/dist/pdf` 再重试
  - 远程图片（http/https）默认被拦截、渲染成 "[remote image blocked]" 占位块：把图下载到 Markdown 同目录用相对路径，或显式加 `--allow-network`；中文交付前打印一页实测字体，缺中文字体会整页豆腐块

## 最佳实践
- 先内容后排版：Markdown 结构（标题层级/表格/图）干净，PDF 才不会到处断裂
- 图片必须本地路径且分辨率足够（现场打印机 300dpi 起）；Mermaid/DOT 图先导出 SVG/PNG 再嵌入
- 中文字体是最大坑：确认 PDF 引擎已装中文字体，否则中文变豆腐块——正式交付前打印一页实测
- 交付命名规范：`<项目>_<文档类型>_v<版本>_<日期>.pdf`，并在扉页写版本与生成日期
- 与 [document-release](document-release.md) 配合：源 Markdown 更新后重新生成 PDF，不要手改 PDF（会造成双版本）
- 体积：含大量截图的 PDF 要压缩，客户邮件常有大小限制

## 项目应用位点
- Zone D：交付包 PDF 定稿（方案 / 验收 / 运维手册三件套）
- 与 `docs/architecture-model/` 的图配套输出

## 相关
[document-generate](document-generate.md) · [pptx](pptx.md) · [pdf](../zone-a-pre-engagement/pdf.md)

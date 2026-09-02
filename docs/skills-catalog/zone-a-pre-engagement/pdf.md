# pdf

> 状态：✅ 已安装 · 类型：工具/文档 · FDE 位点：横切（A 解读 / D 交付）

## 能做什么
PDF 全流程工具箱：文本与表格抽取、页面操纵（合并/拆分/旋转）、表单填写、专业文档生成。读 `.pdf` 附件时的默认技能。

## 何时使用
- 用户消息里出现 `.pdf` 附件或路径
- 需要生成正式交付 PDF（非 Markdown 转换场景，用本技能的生成能力）
- 填写/解析 PDF 表单（客户设备验收单等）

**不用于**：Markdown → PDF 出版级排版（→ [make-pdf](../zone-d-handoff/make-pdf.md)）；只要内容抽取且文件是纯文本型（firecrawl-parse 也可以）。

## 新人上手

- **触发**：用户消息里出现 `.pdf` 附件或路径，或要求"解析 PDF 文本/表格 / 合并拆分 / 填表单 / 生成 PDF"
- **第一步**：读内容从 pypdf 起手：`from pypdf import PdfReader` → `PdfReader("sample.pdf")` 数页、`pg.extract_text()` 抽文本；要表格用 pdfplumber 的 `pg.extract_tables()`
- **常见坑**：生成含中文的 PDF 后必须打开目检——Arial/Helvetica 等标准字体不支持 CJK，中文会渲染成黑方块 ■，需注册 CJK 字体（如 macOS `PingFang.ttc`）或安装 `fonts-noto-cjk`
- **常见坑**：扫描件抽取结果不可全信，关键数字（金额/参数/日期）交付前人工复核

## 最佳实践
- Do：先 extract 成结构化文本再处理，不要对二进制直接动手
- Do：交付生成的 PDF 带页眉版本号和日期，现场文件生命周期长
- Don't：扫描件 OCR 结果要人工复核关键数字（金额/参数/日期）
- 现场：车间设备手册多为 PDF，入库语料前先统一抽取

## 项目应用位点
- Zone A 合同/设备手册解读；Zone D 签字版报告
- `reports/` 产物的 PDF 化归档

## 相关
[firecrawl-parse](firecrawl-parse.md) · [make-pdf](../zone-d-handoff/make-pdf.md) · [docx](docx.md)

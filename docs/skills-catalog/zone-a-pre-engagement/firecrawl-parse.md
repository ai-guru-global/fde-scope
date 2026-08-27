# firecrawl-parse

> 状态：✅ 已安装（firecrawl 插件）· 类型：工具 · FDE 位点：Zone A/B · 客户本地文件接入

## 能做什么
把**本地文件**（PDF/DOCX/DOC/ODT/RTF/XLSX/XLS/HTML）抽取转换为干净的 Markdown 落盘，可附带 AI 摘要或基于内容问答。与 scrape 的分工：parse 处理磁盘路径文件，scrape 处理 URL。

## 何时使用
- 客户给了报价单、规格书、操作手册的本地文件
- 用户说"解析这个 PDF / 提取这个文件的内容"并给出本地路径
- 需要一次性从文档里直接回答问题（parse 的问答模式）

**不用于**：URL 页面（→ scrape）；结构化数据文件要看内容概况（→ read-file）；生成新 PDF（→ make-pdf / pdf）。

## 最佳实践
- Do：路径直接传本地文件，不要先转格式再喂
- Do：大文档先 parse 出 Markdown 再决定哪些进语料库
- Don't：不要用它做扫描件 OCR 质量保证——扫描件效果取决于源质量，重要合同类仍需人工核对

## 项目应用位点
- Zone A 合同/SOW/技术协议解读
- Zone B 非结构化客户文档 → 语料原料

## 相关
[read-file](../zone-b-build/read-file.md) · [pdf](pdf.md) · [docx](docx.md)

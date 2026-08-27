# read-file

> 状态：✅ 已安装（duckdb-skills 系）· 类型：工具/数据 · FDE 位点：Zone B · connect 前置画像

## 能做什么
读取任意数据文件（CSV/JSON/Parquet/Avro/Excel/spatial/SQLite）或远程 URL（S3/HTTPS），预览与画像数据。只读数据文件，**不用于源代码**。

## 何时使用
- 用户提到某个数据文件、问"这里面是什么"、要先看一眼数据集
- 决定后续走转换（convert-file）、查询（query）还是入管道（corpus）之前的探查

**不用于**：源代码阅读（用 Read）；Office 文档的格式级操作（→ docx/xlsx/pdf 技能）。

## 最佳实践
- Do：接到客户数据第一步就画像：行数/列型/空值/编码，再谈清洗
- Do：与 `fde_scope.connectors` 分工——连接器管生产接入，read-file 管一次性探查
- Don't：不要用它打开二进制大文件全量进上下文，先看 schema 再看样本

## 项目应用位点
- Zone B `connect` 前的数据体检；examples/ 里 sample_tickets.csv、*.jsonl 的快速验证
- 语料入库前对 alarm_corpus.jsonl 之类的抽查

## 相关
[convert-file](convert-file.md) · [attach-db](attach-db.md) · [query](query.md) · [xlsx](../zone-a-pre-engagement/xlsx.md)

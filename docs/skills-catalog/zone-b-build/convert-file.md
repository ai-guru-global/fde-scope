# convert-file

> 状态：✅ 已安装（duckdb-skills 系）· 类型：工具/数据 · FDE 位点：Zone B · connect 格式归一

## 能做什么
任意方向的数据文件格式转换：CSV ↔ Parquet ↔ Excel ↔ JSON ↔ GeoJSON……包括 AI 原生无法直接产出的二进制格式（如 Parquet/xlsx 写入）。触发语："转成 parquet / 存成 xlsx / 导出 JSON / 做成 CSV"。

## 何时使用
- 客户给 xlsx 但连接器只吃 CSV；分析完要把结果落成 Excel 交付
- 大数据落 Parquet 压缩存储；跨工具交换格式

**不用于**：文档格式互转（PDF→Word 这类走 firecrawl-parse/pdf/docx）；数据库表迁移（SQL 层面解决）。

## 新人上手

- **触发**：说「转成 parquet」「存成 xlsx」「导出 JSON」「做成 CSV」这类格式到格式的话（SKILL.md 原文触发语）；AI 原生写不出的二进制格式（Parquet/xlsx）也由它兜底
- **第一步**：对 agent 说「把 data.csv 转成 data.parquet」——核心就是一条 `duckdb -c "COPY (FROM 'data.csv') TO 'data.parquet';"`；不指定输出文件时默认同名 `.parquet`
- **常见坑**：输出格式由扩展名决定，缺扩展会直接报错：`.xlsx` 要先 `INSTALL excel; LOAD excel;`，`.geojson`/`.gpkg`/`.shp` 要 `LOAD spatial;`，漏了必然失败
- **常见坑**：`PARTITION_BY (col)` 只对 Parquet/CSV 输出生效，`CODEC 'zstd'` 仅限 Parquet——对其他格式提分区/压缩会被忽略或报错；转换后要抽样验证行数与列型没劣化

## 最佳实践
- Do：转换后抽样验证行数和列型没劣化
- Do：现场归档统一 Parquet（列存、压缩、DuckDB 原生友好）
- Don't：不要对含公式的 xlsx 直接转 CSV——公式结果可以带走，公式本身丢失
- 组合：`convert-file` → DuckDB `query` 是轻量 ETL 标配，不必拉 Airflow

## 项目应用位点
- Zone B `connect`：多源格式归一后进 `fde_scope.connectors.csv_fallback`
- Corpus 原料准备：客户各种破格式 → JSONL/CSV

## 相关
[read-file](read-file.md) · [query](query.md) · [xlsx](../zone-a-pre-engagement/xlsx.md)

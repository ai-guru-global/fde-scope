# query

> 状态：✅ 已安装（duckdb-skills 系）· 类型：工具/数据 · FDE 位点：Zone B · 分析主力

## 能做什么
对挂载的 DuckDB 库或**临时对文件**跑 SQL：接受原生 SQL 或自然语言问题（"上周告警最多的设备"），用 DuckDB 方言习惯写法。覆盖 CSV/Parquet/Excel/JSON 直查。

## 何时使用
- 数据画像、聚合统计、异常切片、覆盖率分析
- 语料盘点（多少条、类别分布、重复率）与 eval 结果分析

**不用于**：源数据文件先要看结构（→ read-file / attach-db）；写操作类生产库（本技能偏只读分析）。

## 新人上手

- **触发**：直接问自然语言「上周告警最多的设备是哪些」或贴一段 SQL；SQL 里带 `'file.csv'` 文件引用或 `--file` 参数走 ad-hoc 模式，否则走 attach-db 挂载的会话模式（SKILL.md Step 1 的分模式规则）
- **第一步**：先 attach-db 挂库，再对 agent 说「统计每个工位的样本行数」；没有库文件也能临时直查：`duckdb :memory: -c "FROM 'data.csv' LIMIT 10;"`（ad-hoc 沙箱模式，DuckDB 直查 CSV 不用导入）
- **常见坑**：大结果会先被拦：表 >1M 行且查询无 `LIMIT`/聚合时 skill 会要求确认（建议加 `LIMIT 1000`），>10 GB 还会追加耗时警告——长跑查询先想好边界
- **常见坑**：多行 SQL 必须用 heredoc `<<'SQL'` 传（SKILL.md 明说避免 shell 引号问题），塞进 `-c "..."` 单引号字符串容易被引号坑；ad-hoc 模式是沙箱（`enable_external_access=false`），只允许 `allowed_paths` 里列出的文件

## 最佳实践
- Do：大 CSV 不导入，直接 `SELECT ... FROM 'file.csv'` 查——DuckDB 的杀手锏
- Do：分析结论落成 SQL 文件归档，移交时客户可复跑
- Don't：不要在自然语言模式下问跨越多个语义域的大杂问，拆成多查询
- 组合：query + coverage_analyzer 思路可以给 `fde_scope.corpus` 报告做二次挖掘

## 项目应用位点
- Zone B `corpus` 后的语料质量复盘；Zone C KPI（OEE/MTBF）临时口径计算
- examples/manufacturing 场景数据的即席分析

## 相关
[attach-db](attach-db.md) · [convert-file](convert-file.md) · [spatial](spatial.md)

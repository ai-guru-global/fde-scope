# attach-db

> 状态：✅ 已安装（duckdb-skills 系）· 类型：工具/数据 · FDE 位点：Zone B · 查询会话准备

## 能做什么
把 DuckDB 数据库文件挂进当前会话（`/duckdb-skills:query` 的前置）：探索表/列/行数，写 SQL 状态文件，让后续查询自动恢复会话。

## 何时使用
- 同一个数据文件/库要连续做多轮 SQL 分析
- 用户给了 `.duckdb`/`.db`/`.sqlite` 文件要长期用

**不用于**：一次性看一眼文件（→ read-file）；没有 DuckDB 环境时先 `install-duckdb`。

## 新人上手

- **触发**：拿到 `.duckdb`/`.db`/`.sqlite` 文件要连续做多轮 SQL 时，对 agent 说「attach 这个库」/「把这个库文件挂进会话」（SKILL.md：为 /duckdb-skills:query 准备会话）
- **第一步**：先验库再挂：`duckdb <库文件> -c "PRAGMA version;"` + `duckdb <库文件> -csv -c "SELECT table_name, estimated_size FROM duckdb_tables();"`，skill 会把 `ATTACH '<path>' AS <alias>;` 写进状态文件，之后 `duckdb -init .duckdb-skills/state.sql -c "SHOW TABLES;"` 即恢复会话
- **常见坑**：状态文件 `.duckdb-skills/state.sql`（或 `~/.duckdb-skills/<project-id>/state.sql`）是全 skill 共享、只追加不覆盖的——SKILL.md 明说 "Never overwrite it"，追加前先查重，别名冲突要让用户改名
- **常见坑**：文件不存在时 skill 会问"要不要新建空库"——DuckDB 首次写入才落文件，路径拼错不报错，挂完必须 `SHOW TABLES` 核对绑定的确是预期路径

## 最佳实践
- Do：挂完先看生成的状态文件确认绑定的是正确路径
- Do：多文件分析优先直接对文件查询（DuckDB 可查 CSV/Parquet），不必都导入
- Don't：不要挂载生产数据库文件副本以外的敏感数据到共享机器
- 现场：air-gap 环境 DuckDB 单机零服务，是最好的本地分析引擎

## 项目应用位点
- Zone B eval 结果集、KPI 时序的多轮分析会话
- 制造业样例 `station_samples.jsonl` 的深度切片

## 相关
[query](query.md) · [install-duckdb](#) · [read-file](read-file.md)

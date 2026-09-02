# bigquery-basics

> 状态：📦 可安装（registry 真名 `google/skills@bigquery-basics`）· 类型：工具/数据 · FDE 位点：Zone B · 数据接入（GCP 数仓）
> 安装：`npx skills add google/skills@bigquery-basics --directory ~/.qoder/skills -y` · 装机量：12.7K（skills.sh，2026-08-31）· 详情：https://skills.sh/google/skills/bigquery-basics

## 能做什么
Google 官方 BigQuery skill：管理数据集、表与作业——启用 API（`gcloud services enable bigquery.googleapis.com`）、建 dataset/table（`bq mk --dataset --location=US`、`bq mk --table` + `schema.json`）、跑标准 SQL（`bq query --use_legacy_sql=false`）。SKILL.md 附 references 目录：CLI 用法、client library（Python/Java/Node.js/Go）、Terraform IaC、IAM 安全、continuous queries、APPENDS/CHANGES 增量变更追踪、BigQuery remote MCP。同 repo 兄弟条目 `bigquery-ai-ml`（ai_forecast/ai_search 等 AI 函数）、`bigquery-bigframes`（DataFrame 规模分析）。

## 何时使用
- 客户数仓在 GCP BigQuery，需要建表、建 dataset、导数、跑分析查询
- 交付物要落到客户 GCP 项目：表结构设计、Terraform 建资源、IAM 角色梳理
- 产线数据（如 `station_samples` 样例）要上云做规模化分析

**不用于**：本地/内网一次性数据分析（→ [query](query.md) / [attach-db](attach-db.md)）；dbt 变换层建模（→ [using-dbt-for-analytics-engineering](using-dbt-for-analytics-engineering.md)）。

## 新人上手
- **触发**：对 agent 说「在客户的 BigQuery 项目里建表」「帮我在 BigQuery 上跑这个分析」
- **第一步**：`npx skills add google/skills@bigquery-basics --directory ~/.qoder/skills -y` 装完后先确认凭据：`gcloud auth application-default login` + `gcloud config get-value project`，再 `bq mk --dataset --location=US my_dataset` 建第一个 dataset 验通链路
- **常见坑**：`bq query` 默认走 legacy SQL，函数/语法直接报错——必须带 `--use_legacy_sql=false` 用标准 SQL
- **常见坑**：`--location` 必须与 dataset 所在 region 一致，跨 region 查询会报 dataset not found；建表用 `schema.json`（`name`/`type`/`mode` 三字段）而不是临时手写 DDL

## 最佳实践
- Do：优先走 SKILL.md 的 references/（cli-usage、iac-usage、iam-security），IaC 场景用 Terraform 而不是手敲 `bq` 命令
- Do：凭据走 gcloud ADC / 环境变量，遵守本仓规约——API key 不落 manifest、engagement JSON 或日志
- Don't：不做大表无分区全扫（按扫描字节计费，成本失控是 BigQuery 交付最常见事故）
- 现场：air-gap 客户意味着数据出境——BigQuery 是公有云服务，接入前先过合规评审，别默认客户接受

## 项目应用位点
- Zone B `data-ingestion`：客户 GCP 数仓接入与表结构落地
- Zone B `deploy`：评估/报表产物回写客户 BigQuery
- 与 [query](query.md) 分工：BigQuery 管云端数仓，DuckDB 管本地探查

## 相关
[query](query.md) · [attach-db](attach-db.md) · [read-file](read-file.md)

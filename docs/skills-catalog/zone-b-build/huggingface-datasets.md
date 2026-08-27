# huggingface-datasets

> 状态：✅ 已安装（huggingface 插件家族）· 类型：工具/数据 · FDE 位点：Zone B corpus

## 能做什么
基于 HF Dataset Viewer API 的数据集工作流：拉 subset/split 元数据、分页取行、全文搜索、过滤、拿 parquet 下载 URL、读规模与统计——不下载全量就能探查任意 Hub 数据集。

## 何时使用
- 为语料库找公开数据补充（中文指令集、故障诊断域数据）
- 对比候选数据集的规模/字段/样例后再决定下载
- 需要 parquet URL 直接喂给 DuckDB 分析

**不用于**：Hub 认证/仓库管理等泛操作（→ hf-cli）；训练本身（→ trl-training）。

## 最佳实践
- Do：先用 search+分页看 100 条样例判断质量，再 `convert-file`/parquet URL 拉全量
- Do：私有/受限数据集注意 license 与用途限制，交付客户前二次确认
- Don't：不要无脑 `load_dataset` 全量进内存，先 Viewer 探查
- 组合：Viewer 探查 → parquet URL → `query`（DuckDB 直查远程文件）是零落地分析链路

## 项目应用位点
- Zone B corpus 的外部语料补充源
- eval 基准数据（分类/检索 benchmark）的快速引入

## 相关
[convert-file](convert-file.md) · [query](query.md) · [train-sentence-transformers](train-sentence-transformers.md)

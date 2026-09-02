# firecrawl-crawl

> 状态：✅ 已安装（firecrawl 插件）· 类型：工具 · FDE 位点：Zone A/B · 文档区批量入库

## 能做什么
按站点/站点分区（如 `/docs`）批量抽取全部页面，支持深度限制、路径过滤、并发控制；异步任务，可用 `check_crawl_status` 轮询进度。

## 何时使用
- 客户产品文档站、开源项目文档整仓本地化
- 建立语料原料库（爬完 → 进 corpus forge 清洗）
- "把 X 网站 docs 下所有内容抓下来"类请求

**不用于**：只要 1-3 个页面（scrape 更快更省）；已知变更监控（用 monitor）。

## 新人上手

- **触发**：说 "crawl" / "get all the pages" / "extract everything under /docs"（SKILL.md 原文触发词），即"把这个站的 docs 全抓下来"
- **第一步**：`firecrawl crawl "<url>" --include-paths /docs --limit 50 --wait -o .firecrawl/crawl.json`；大站先小 `--max-depth` 试跑一轮估量级
- **常见坑**：不加 `--wait` 只返回异步 job ID，要立刻拿结果必须显式加上（之后可用 `firecrawl crawl <job-id>` 查进度）
- **常见坑**：按页计 credits，大爬前先 `firecrawl credit-usage` 查余额；用 `--include-paths` 圈死范围，别对整站无差别开爬

## 最佳实践
- Do：先用 map/URL 过滤确定范围，再 crawl；设置 `includePaths` 避免全站爆炸
- Do：大站先小深度试跑一轮估量级
- Don't：不要对客户内网/生产系统未经授权使用
- 后续衔接：爬出的 Markdown 进 `convert-file`/DuckDB 做结构化，再入 `fde_scope.corpus` 管道做脱敏与去重

## 项目应用位点
- Zone B `connect→corpus`：网页文档 → 原始语料 → 脱敏 → 质量门
- ACK/中间件官方文档的离线镜像，供现场 air-gap 环境查询

## 相关
[firecrawl-scrape](firecrawl-scrape.md) · [convert-file](../zone-b-build/convert-file.md) · [bailian-cli](../cross-cutting/bailian-cli.md)（知识库入库）

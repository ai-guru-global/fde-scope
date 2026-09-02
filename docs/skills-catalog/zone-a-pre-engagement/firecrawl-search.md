# firecrawl-search

> 状态：✅ 已安装（firecrawl 插件）· 类型：工具 · FDE 位点：Zone A · qualification / site-survey 前置研究
> MCP 工具：`firecrawl_firecrawl_search` · 依赖：Firecrawl API 认证（见 security-scan 类安装规约）

## 能做什么
真实时联网搜索，且不止返回摘要片段——可对命中结果**连带全文抽取**（Markdown/结构化 JSON），一次调用得到"搜索结果 + 页面正文"。比内置 WebSearch 多了内容落地能力。

## 何时使用
- 客户行业背景、竞品方案、技术选型的最新资料调研
- 需要"别人怎么说的"完整论据，而非 snippet
- 搜索后紧接着要抓取（省去 search→scrape 两步编排）

**不用于**：本地文件、内网系统、代码仓库内部检索（走 SearchCodebase/sourcegraph）。

## 新人上手

- **触发**：没给 URL、只要资料时对 agent 说 "search for …" / "find articles about …" / "what are people saying about X"（SKILL.md 原文触发词），即"帮我搜下竞品/行业最新说法"
- **第一步**：`firecrawl search "你的关键词" -o .firecrawl/result.json --json`；要连带全文就加 `--scrape`，一次调用顶 search→scrape 两步
- **常见坑**：结果必须用 `-o` 落到 `.firecrawl/` 再处理（`jq -r '.data.web[].url'` 提取链接），直接打屏会撑爆上下文窗口
- **常见坑**：一次 search 计 2 credits——先窄关键词加 `--limit` 锁定 2-3 条高相关结果再动；拿到结果列表后别逐条重新抓，该用 `--scrape` 一步到位

## 最佳实践
- Do：先窄关键词锁定 2-3 条高相关结果再抽全文，控制 token 与费用
- Do：对时效敏感话题限定时间范围
- Don't：不要用它替代本地代码搜索；不要一次抓几十个页面
- 成本：按次计费，调研阶段够用即可；认证失败时参考 `install` 规则技能修复

## 项目应用位点
- `pre_engagement.SiteSurveyGate` 之前的行业预研；`docs/manufacturing_scenario.md` 类素材收集
- 产出可归档进 `.fde_scope/engagements/<id>/` 调研笔记

## 相关
[firecrawl-scrape](firecrawl-scrape.md) · [firecrawl-crawl](firecrawl-crawl.md) · [firecrawl-monitor](../zone-c-operationalization/firecrawl-monitor.md)

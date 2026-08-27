# firecrawl-monitor

> 状态：✅ 已安装（firecrawl 插件 v0.1.0）· 类型：变更监测 · FDE 位点：Zone C watch

## 能做什么
监测网页内容变化并通过 **webhook / 邮件** 告警，无需自建 cron + 抓取 + diff。内置 AI judge 过滤排版、时间戳、跟踪参数等噪声，只在**真实内容变化**时通知。两类用法：① 盯已知 URL（定价页、文档、changelog、状态页、招聘页）；② 盯"网页本身"的新结果（新产品发布、融资、论文、动态），此时给搜索 query + 目标而不是 URL。

## 何时使用
- 客户竞品/供应商的定价与规格变更监测（售前素材保鲜）
- 依赖的第三方文档/API/固件版本页变更（现场设备 SDK 更新往往就这样发现）
- 同一 URL 需要重复检查第二次以上——就该用 monitor 而不是一次次 scrape

**不用于**：一次性抓取（→ [firecrawl-scrape](../zone-a-pre-engagement/firecrawl-scrape.md)）；站内多页首次建库（→ [firecrawl-crawl](../zone-a-pre-engagement/firecrawl-crawl.md)）；内部代码/配置变更监测（用 git CI，不用外网工具）。

## 最佳实践
- 明确"什么算变化"：盯价格就锁 price 元素区域，整页监测会被推荐位噪声打爆
- 频率按业务定：定价类日/周一次足够，状态页类可高频；高频会快速消耗额度
- 告警落地要有责任人和动作（收到 → 谁评估 → 是否影响交付），否则会变成静音噪音
- 结果需二次确认：AI judge 过滤后仍要在工单/记录里留证据链接，别只凭通知转述
- 合规：监测对象 robots/条款允许，避免登录墙后内容与个人隐私数据

## 项目应用位点
- Zone C watch：外部依赖变更发现（连接器涉及的设备固件/MES 版本页）
- Zone A：客户所在行业新闻、竞对信息保鲜

## 相关
[firecrawl-scrape](../zone-a-pre-engagement/firecrawl-scrape.md) · [firecrawl-crawl](../zone-a-pre-engagement/firecrawl-crawl.md) · [schedule](../cross-cutting/schedule.md)

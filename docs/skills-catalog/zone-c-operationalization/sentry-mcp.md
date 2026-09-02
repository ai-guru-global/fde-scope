# sentry-mcp

> 状态：✅ 已安装（sentry 插件 v1.0.0 · 提供 MCP server + `sentry-mcp` 子 agent）· 类型：错误/性能观测 · FDE 位点：Zone C operate

## 能做什么
用自然语言操作 Sentry：搜索/分析/分诊 errors 与 exceptions、读 stack trace、性能 trace 分析、release 与版本关联、snapshot（含 preprod 视觉回归快照）、CI snapshot 失败定位。适合"客户问今天线上报了什么错"这类问题一句话回答。

## 何时使用
- fde-scope Web 控制台/PawApp 上线后接入 Sentry，日常巡检 issue 与新版本回归
- 定位到具体 exception 需要完整堆栈 + 影响用户数 + 首次出现版本
- 用 release 关联"哪次发布引入的问题"

**不用于**：没有 Sentry 的客户环境（阿里云栈 → [starops](starops.md)；自建 → Datadog 插件 / Prometheus）；业务指标下降但无报错（→ 评估类：[phoenix-evals](../zone-b-build/phoenix-evals.md)）；需要复现的前端交互问题（→ [chrome-devtools](chrome-devtools.md)）。

## 新人上手

- **触发**：贴一个 Sentry issue URL 给 agent，或直接问「今天线上报了什么错」「这个 exception 影响了哪些用户」（SKILL.md 触发词覆盖 errors/stack traces/releases/snapshots/CI snapshot 失败）
- **第一步**：先用配置/授权流程打通 MCP server `sentry`：让 agent 调 `find_organizations`、`find_projects` 列出可访问的组织与项目，确认目标 `organizationSlug/projectSlug` 在列，再开始 `search_issues` 分诊
- **常见坑**：Sentry URL 必须原样传给 `issueUrl`/`url` 参数——SKILL.md 明确 NEVER 直接用 HTTP fetch Sentry 链接，那样会因缺认证拿到空结果或 401
- **常见坑**：`search_issues` 返回分组后的 issue 列表，`search_events` 才返回计数/聚合/单条事件——要"影响用户数、按版本聚合"这类数字用后者；另外接入时没带 `release`+`environment` 标签的话，issue 无法按发布版本区分

## 最佳实践
- 接入时务必带 `release` + `environment` 标签，否则 issue 无法按版本区分（现场最常见的接入缺陷）
- 用子 agent 做"分诊"而不是让它改配置：读操作放心交给它，写操作（mute/assign/项目设置）人工确认
- 注意 DSN 与 org token 的权限范围，交付项目里客户数据会进 Sentry event——**必须开 before_send 脱敏**（工单原文、设备标识）
- 与本项目衔接：把 Sentry issue 计数作为 SLO gate 的证据之一，写入 engagement 记录而不是只留在 Sentry 面板

## 项目应用位点
- Zone C `operationalize`：错误率与性能回归监控
- Zone D handoff：交接时给客户的 issue 清单与分诊规则

## 相关
[starops](starops.md) · [investigate](investigate.md) · [web-perf](web-perf.md)

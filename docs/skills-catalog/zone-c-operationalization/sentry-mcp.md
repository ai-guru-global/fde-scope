# sentry-mcp

> 状态：✅ 已安装（sentry 插件 v1.0.0 · 提供 MCP server + `sentry-mcp` 子 agent）· 类型：错误/性能观测 · FDE 位点：Zone C operate

## 能做什么
用自然语言操作 Sentry：搜索/分析/分诊 errors 与 exceptions、读 stack trace、性能 trace 分析、release 与版本关联、snapshot（含 preprod 视觉回归快照）、CI snapshot 失败定位。适合"客户问今天线上报了什么错"这类问题一句话回答。

## 何时使用
- fde-scope Web 控制台/PawApp 上线后接入 Sentry，日常巡检 issue 与新版本回归
- 定位到具体 exception 需要完整堆栈 + 影响用户数 + 首次出现版本
- 用 release 关联"哪次发布引入的问题"

**不用于**：没有 Sentry 的客户环境（阿里云栈 → [starops](starops.md)；自建 → Datadog 插件 / Prometheus）；业务指标下降但无报错（→ 评估类：[phoenix-evals](../zone-b-build/phoenix-evals.md)）；需要复现的前端交互问题（→ [chrome-devtools](chrome-devtools.md)）。

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

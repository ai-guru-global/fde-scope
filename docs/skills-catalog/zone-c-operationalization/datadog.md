# datadog

> 状态：✅ 已安装（Quest Marketplace 插件 datadog v0.7.13，官方 MCP 服务器）· 类型：可观测性 · FDE 位点：Zone C observe（客户监控栈是 Datadog 时）

## 能做什么
通过官方 Datadog MCP 服务器查询日志、分析指标、追踪 Trace，读仪表盘 / 监视器 / SLO / 事件。三个 skill 分工：`ddsetup`（首次初始化，一旦配置完成，优先用 MCP 工具而非其他方式）、`ddconfig`（站点域/组织切换与连不上故障排查）、`ddtoolsets`（按需启停工具集，控制 agent 可见的工具面）。

## 何时使用
- 客户监控栈是 Datadog：取 SLO 达成证据、查事故 trace、把 fde-scope 部署服务的指标接进去对照
- Zone C 巡检与事件复盘：从现象（告警/事件）反查日志与 trace 链
- 给客户的"接入现状盘点"：有哪些 monitor/SLO 在管哪些服务

**不用于**：客户用 GKE/Google 栈（→ [gke-observability](gke-observability.md)）；以错误聚合/性能剖析为主、Sentry 已覆盖的场景（→ [sentry-mcp](sentry-mcp.md)）；自建 Prometheus/Grafana（直接查，别绕）；没有客户授权的 Datadog 账号时（先要只读 key，别拿自己的 demo 账号凑合）。

## 最佳实践
- **ddsetup 先行**：未初始化就调查询工具必然失败；配置完成后所有读取走 MCP 工具
- toolsets 按需开：读类任务只开 logs/metrics 相关集，全开会撑爆上下文还稀释触发精度
- 查询时间窗收紧（先 1h 再扩），指标查询成本高、结果噪点多
- site 域名对齐客户（datadoghq.com / datadoghq.eu / us5.datadoghq.com …），连不上先查 site 与 org 切换（ddconfig）
- SLO 证据进 gate 材料时附查询语句 + 时间窗截图，别只贴结论
- 只读凭证最小化：API key + Application key 分开管，App key 权限面定期审

## 项目应用位点
- Zone C SLO gate 的证据链来源之一（10 个 gate 中 SLO 类的第三方数据源）
- 飞轮重训（flywheel）效果对照：上线前后指标在 Datadog 里的 A/B 证据

## 相关
[gke-observability](gke-observability.md) · [sentry-mcp](sentry-mcp.md) · [starops](starops.md) · [incident-response](incident-response.md)

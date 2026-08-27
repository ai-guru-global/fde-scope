# starops

> 状态：✅ 已安装（starops 插件 v0.1.3）· 类型：AIOps/诊断 · FDE 位点：Zone C operate（有云监控的客户）

## 能做什么
阿里云 STAROps（Agentic Ops）：查指标/APM/trace/日志、服务拓扑与依赖、告警分析与降噪、调用链追踪、影响面分析、k8s/主机诊断、变更守护、故障复盘与恢复建议——通过 STAROps Agent 以自然语言驱动。

## 何时使用
- 客户已经用阿里云 ARMS/SLS/云监控，上线后出现接口报错、慢请求、告警风暴
- 需要"影响面有多大"这类结论来做客户沟通（不只是"哪里坏了"）
- 变更后守护：判断这次发布是否引入了指标异常

**不用于**：客户自建 Prometheus/Grafana 栈（→ [gke-observability](gke-observability.md) 或直接读 Prometheus）；无云监控的离线现场（→ [investigate](investigate.md) + 手工日志）；代码级 bug 复现（→ [systematic-debugging](systematic-debugging.md)）。

## 最佳实践
- 提问题时带上**时间窗 + 服务名 + 现象**三要素，否则 agent 会给出泛化结论
- 把它的根因结论当"假设"：要求给出支撑的 trace/指标证据，再落到 runbook
- 恢复建议要走客户审批，不允许 agent 直接在生产执行写操作
- 与本项目衔接：SLO 类 gate（`slo` gate）所需的指标取数可以用它，但结论要写进交付文档而不是留在对话里
- 权限：只读 AK 即可满足大部分诊断，别为排障申请写权限

## 项目应用位点
- Zone C `operationalize`：SLO 验证与线上异常定位
- 阿里云客户的交接运维手册（配合 [alibabacloud-workbench-cli](../zone-b-build/alibabacloud-workbench-cli.md)）

## 相关
[investigate](investigate.md) · [sentry-mcp](sentry-mcp.md) · [sre-runbooks](sre-runbooks.md)

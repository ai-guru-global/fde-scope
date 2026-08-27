# gke-observability 📦

> 状态：📦 可安装（未装）· 类型：可观测性（K8s） · FDE 位点：Zone C operate
> 来源：`google/skills@gke-observability`（Google 官方 org）· 热度：3K installs · https://skills.sh/google/skills/gke-observability
> 同系列：`gke-upgrades`（3.2K）、`gke-cluster-creation`（2.9K）、`gke-cluster-autoscaler`（1.9K）、`gke-cost-optimization`（1.5K）
> 安装：`npx skills add google/skills@gke-observability --directory ~/.qoder/skills -y`

## 能做什么
GKE/K8s 可观测性接入与查询：日志（Cloud Logging）、指标（Cloud Monitoring / Prometheus 栈）、trace 采集与关联，Workload Identity 采集权限、告警规则与 SLO 预算视图，以及"看不到数据"时的采集链路排查。

## 何时使用
- 客户在 GCP/GKE 上跑 fde-scope 服务，需要把日志指标接进平台监控
- 自建 Prometheus + Grafana 的 K8s 环境（思路与资源定义可迁移，具体产品名要替换）
- 上线时要同时交付告警规则与 SLO 视图（Zone C 的必备材料）

**不用于**：阿里云客户（→ [starops](starops.md)）；单容器/ECS 部署（→ 直接 stdout 日志 + 平台监控，别为此上 K8s 观测栈）；应用内错误细节（→ [sentry-mcp](sentry-mcp.md)）。

## 最佳实践
- 先定义"要回答什么问题"再装采集器：只要 SLO（可用性/延迟）就先指标 + 告警，trace 等到有跨服务排障需求时再上
- 采集成本可控：K8s 默认全量采集在工业现场很容易爆盘/爆预算，明确采样率与保留期并写进交付文档
- 权限最小化：只读监控权限即可，绝不为排障给集群 admin
- 与 [kubernetes-specialist](../zone-b-build/kubernetes-specialist.md) 配套使用：前者管拓扑与发布，本 skill 管可观测信号
- 交接视角：告警通知要接到客户既有值班通道（邮件/IM/PagerDuty），否则等于没有监控
- 官方 skill 可信度高，但因平台强绑定 GCP——非 GCP 客户装它收益有限，按客户平台决定是否安装

## 项目应用位点
- Zone C：`slo` gate 的指标来源与告警落地
- Zone B deploy：容器化交付（[docker-build-deploy](../zone-b-build/docker-build-deploy.md) / K8s）之后的观测面

## 相关
[kubernetes-specialist](../zone-b-build/kubernetes-specialist.md) · [starops](starops.md) · [sre-runbooks](sre-runbooks.md)

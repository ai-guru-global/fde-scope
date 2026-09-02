# kubernetes-specialist 📦

> 状态：📦 可安装（未装）· 类型：部署/运维 · FDE 位点：Zone B deploy + Zone C operate
> 来源：`jeffallan/claude-skills@kubernetes-specialist` · 热度：12.5K installs · 详情：https://skills.sh/jeffallan/claude-skills/kubernetes-specialist
> 安装：`npx skills add jeffallan/claude-skills@kubernetes-specialist --directory ~/.qoder/skills -y`

## 能做什么
K8s 现场交付与排障的通用专家技能：manifest/Helm 编写、Deployment/Service/Ingress/ConfigMap/Secret 语义、探针与资源配额、滚动发布与回滚、`kubectl` 排障路径（Pod 卡住、CrashLoopBackOff、OOMKilled、镜像拉取失败、网络策略阻断）。

## 何时使用
- 客户侧已有 K8s 平台，fde-scope 要以 Deployment 形式落地（含 GPU device plugin 场景）
- 现场发布出问题时按"先定位后修"的排障流程走，而不是逐个改 yaml 试
- 写交付物的 `deploy/` 目录（ Helm chart / kustomize overlay）需要规范基线

**不用于**：单客户内网只有一台 ECS 的小规模交付（→ [alibabacloud-workbench-cli](alibabacloud-workbench-cli.md) 或 [docker-build-deploy](docker-build-deploy.md)）；纯本地 dev（docker compose 足够）。

## 新人上手

- **触发**：现场 Pod 起不来或要写交付清单时直接说，如"帮我看看为什么 Pod 一直 CrashLoopBackOff"、"给这个服务写一套 Deployment + Ingress 的 manifest"
- **第一步**：先安装 `npx skills add jeffallan/claude-skills@kubernetes-specialist --directory ~/.qoder/skills -y`（社区源，装前按规约过一次 [skill-criticagent](../cross-cutting/skill-criticagent.md) 门禁），再让 agent 按该技能"先定位后修"的路径排障（如"排查 namespace prod 里 xxx 服务 Pod 卡在 Pending 的原因"），而不是逐个改 yaml 试
- **常见坑**：让 agent 裸跑 `kubectl` 不带 `--context`/`--namespace`——context 漂移是 agent 误操作客户集群的最大来源，任何命令都要显式指定；把 skill 生成的 manifest 直接 apply 到客户集群——必须先 dry-run + diff 再由客户确认

## 最佳实践
- 装前门禁：社区 skill（非官方），先用 [skill-criticagent](../cross-cutting/skill-criticagent.md) 评估；若不通过，可考虑热度更高的 `microsoft/azure-skills@azure-kubernetes`（375.4K）作为云平台特化替代
- 生产红线：不要让 skill 生成的 manifest 直接 apply 到客户集群——必须 dry-run + diff 后再由客户确认
- 明确 namespace/context：任何命令都带 `--context/--namespace`，agent 误操作集群的最大来源就是 context 漂移
- 优先声明式：所有变更走 git 中的 yaml，不接受 `kubectl edit` 类临时改动（会造成集群与仓库漂移）
- 记录到项目：把最终 topology 回写 `docs/architecture-model/`，配合 [deployment-topology-analyzer](../cross-cutting/architecture-visualization-suite.md)

## 项目应用位点
- Zone B deploy：多客户/规模化交付时的编排层
- Zone C operate：现场故障排查与回滚 SOP 的执行依据

## 相关
[docker-build-deploy](docker-build-deploy.md) · [vllm-deploy-docker](vllm-deploy-docker.md) · [skill-criticagent](../cross-cutting/skill-criticagent.md)

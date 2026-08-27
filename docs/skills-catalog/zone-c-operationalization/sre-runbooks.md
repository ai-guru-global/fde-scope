# sre-runbooks 📦

> 状态：📦 可安装（未装）· 类型：运维文档模板 · FDE 位点：Zone C operationalize（runbook 交付物）
> 候选 A（推荐）：`anthropics/knowledge-work-plugins@runbook`（官方 org）· 热度：2.6K installs · https://skills.sh/anthropics/knowledge-work-plugins/runbook
> 候选 B：`alphaonedev/openclaw-graph@sre-runbooks` · 50 installs · https://skills.sh/alphaonedev/openclaw-graph/sre-runbooks
> 安装：`npx skills add anthropics/knowledge-work-plugins@runbook --directory ~/.qoder/skills -y`
> 说明：早期建档名记作 `sre-runbooks`；registry 中该名存在但热度仅 50，官方 `runbook` 是更优来源，安装命令按候选 A 给出。审计状态本次未复核，安装前补查 skills.sh 页面。

## 能做什么
产出结构化 runbook：触发条件（告警/指标阈值）、影响面判定、定位步骤、恢复动作、升级路径、验证方式、复盘要点。让"排障知识"从人的脑子里搬到可执行文档。

## 何时使用
- fde-scope 交付上线前，客户运维团队要求"每类故障一页怎么办"
- `engagement/phases.py` 的 operationalize 阶段交付物（SLO 之后必须有 runbook）
- 现场排障结束后立刻沉淀：把 [investigate](investigate.md) 的排查过程转成可复用步骤

**不用于**：一次性问题的口头答复（不值得建档）；把 runbook 写成架构图（图走 [architecture-communicator](../zone-a-pre-engagement/architecture-communicator.md)）；用 skill 生成的模板直接签字交付（必须客户会签）。

## 最佳实践
- 一页一故障：标题就是"现象 + 服务名"，不要写"通用排障指南"
- 每条命令必须**现场验证过**再写进去；未验证的标 `TODO-验证`，否则就是误导
- 写清"不要做"（重启会丢什么、什么时候必须停线）——工业客户最看重这条
- 与告警一一对应：没有告警对应的 runbook 段落等于不会有人读
- 版本与责任人：每页顶部写适用范围（版本/环境）+ owner + 最后验证日期
- 存放位置：进交付仓库 `docs/runbooks/`，不要只存在 wiki（交接时要有可打包物）

## 项目应用位点
- Zone C `operationalize`：SLO gate 之后的必备交付物
- Zone D handoff：培训与值班手册的原料

## 相关
[incident-response](incident-response.md) · [investigate](investigate.md) · [starops](starops.md)

# sre-runbooks 📦

> 状态：📦 可安装（未装）· 类型：运维文档模板 · FDE 位点：Zone C operationalize（runbook 交付物）
> 候选 A（推荐）：`anthropics/knowledge-work-plugins@runbook`（官方 org）· 热度：2.6K installs · https://skills.sh/anthropics/knowledge-work-plugins/runbook
> 候选 B：`alphaonedev/openclaw-graph@sre-runbooks` · 50 installs · https://skills.sh/alphaonedev/openclaw-graph/sre-runbooks
> 安装：`npx skills add anthropics/knowledge-work-plugins@runbook --directory ~/.qoder/skills -y`
> 说明：早期建档名记作 `sre-runbooks`；registry 中该名存在但热度仅 50，官方 `runbook` 是更优来源，安装命令按候选 A 给出。
> 取证（2026-08-27）：源文件 `operations/skills/runbook/SKILL.md`（87 行，**单文件**，无 `scripts/`、无 `references/`、无网络调用）· https://github.com/anthropics/knowledge-work-plugins/blob/main/operations/skills/runbook/SKILL.md
> 安全：上游仓库对每个条目跑**强制 Claude policy scan**（`.github/workflows/scan-plugins.yml`，按 (plugin, sha) 缓存判定，不通过则被 `revert-failed-bumps.yml` 剔除）。风险面极小。

## 能做什么
产出结构化 runbook（已读源文件确认其固定模板）：Owner + Frequency + Last Updated/Last Run 头部 → Purpose → Prerequisites → **Procedure（每一步都有“确切命令 + Expected result + If it fails”三件套）** → Verification → Troubleshooting 表（症状/可能原因/处置）→ Rollback → Escalation 表（情形/联系人/方式）→ History 执行记录表。
上游提示词接得很死：“`Run the script` 不算一步，`从 ops 服务器跑 python sync.py --prod --dry-run` 才算”。

⚠️ 模板**不含**告警/指标阈值与影响面判定字段（那是 incident-response 的地盘）——要与客户告警一一对应，得手工加一节。

## 何时使用
- fde-scope 交付上线前，客户运维团队要求"每类故障一页怎么办"
- `engagement/phases.py` 的 operationalize 阶段交付物（SLO 之后必须有 runbook）
- 现场排障结束后立刻沉淀：把 [investigate](investigate.md) 的排查过程转成可复用步骤

**不用于**：一次性问题的口头答复（不值得建档）；把 runbook 写成架构图（图走 [architecture-communicator](../zone-a-pre-engagement/architecture-communicator.md)）；用 skill 生成的模板直接签字交付（必须客户会签）。

## 最佳实践
- 一页一故障：标题就是"现象 + 服务名"，不要写"通用排障指南"
- 每条命令必须**现场验证过**再写进去；未验证的标 `TODO-验证`，否则就是误导
- 写清"不要做"（重启会丢什么、什么时候必须停线）——工业客户最看重这条
- **拿它的 History 表当审计手段**：每次值班执行人签字 + 备注，一个季度就能看出哪份 runbook 在真实世界失效
- 它的 `If Connectors Available` 段默认接 knowledge base / ITSM：没接这些系统时该段就是死话，本地用直接忽略
- 补上模板缺的“告警对应”字段：没有告警对应的 runbook 段落等于不会有人读
- 版本与责任人：每页顶部写适用范围（版本/环境）+ owner + 最后验证日期
- 存放位置：进交付仓库 `docs/runbooks/`，不要只存在 wiki（交接时要有可打包物）

## 项目应用位点
- Zone C `operationalize`：SLO gate 之后的必备交付物
- Zone D handoff：培训与值班手册的原料

## 相关
[incident-response](incident-response.md) · [investigate](investigate.md) · [starops](starops.md)

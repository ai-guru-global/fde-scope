# deploy-checklist 📦

> 状态：📦 可安装（未装）· 类型：上线前核验清单 · FDE 位点：Zone B 收口 → Zone C operationalize 交界
> 真实条目：`anthropics/knowledge-work-plugins@deploy-checklist`（官方 org）· 热度：4.9K installs · https://skills.sh/anthropics/knowledge-work-plugins/deploy-checklist
> 源文件（已读，2026-08-27 取证）：`engineering/skills/deploy-checklist/SKILL.md`（78 行，无 scripts/、无 references/，纯模板 skill）· https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/deploy-checklist/SKILL.md
> 安装：`npx skills add anthropics/knowledge-work-plugins@deploy-checklist --directory ~/.qoder/skills -y`

## 能做什么
在**部署前**生成一份可勾选的 readiness 清单，输出结构固定为四段：Pre-Deploy（CI 全绿 / 已评审 / 无已知严重缺陷 / **迁移已测** / **flag 已配** / **回滚方案已写** / on-call 已通知）、Deploy（staging 验证 → smoke → 生产（有 canary 走 canary）→ 观察错误率与延迟 15 分钟 → 关键流程验证）、Post-Deploy（指标确认 / release notes / 通知干系人 / 关单）、以及 **Rollback Triggers**（错误率阈值、P50 延迟阈值、关键流程失败——**上线前就定好，不是出事时再想**）。

支持按场景定制：说明"有 feature flag / 含数据库迁移 / 是破坏性 API 变更"，它会追加对应核验步骤。

## 何时使用
- 每一次向客户生产环境投递（包括"例行的小版本"——清单存在的意义正是防"我忘了……"）
- 变更含 DB migration、feature flag、或破坏性接口变更时（这三类是现场事故高发源）
- 需要一份**能作为 gate 证据**的上线核验记录（fde-scope 的 SLO / HandoffSignoff gate）
- 交接给客户团队时，把清单本身当交付物

**不用于**：反复执行的操作步骤文档（→ [sre-runbooks](sre-runbooks.md)，runbook 是"怎么做"，本 skill 是"能不能做"）；事件发生时的处置（→ [incident-response](incident-response.md)）；架构层面的上线风险评估（→ 架构可视化插件 `risk-quality-reviewer`）；本地/演示环境的一次性部署（清单开销不划算）。

## 最佳实践
- **上游信源已核**：该 skill 是纯模板（无可执行脚本、无外部依赖、无网络调用），风险面极小；且上游仓库对每个条目跑**强制的 Claude policy scan 状态检查**（`.github/workflows/scan-plugins.yml`，按 (plugin, sha) 缓存判定，未通过会由 `revert-failed-bumps.yml` 自动剔除），供应链治理在同类 skill 里属最强一档
- 与已装的 [gstack-suite](../cross-cutting/gstack-suite.md) `land-and-deploy` / `setup-deploy` 有重叠：GStack 偏"自动化执行发布动作"，本 skill 偏"人工核验清单"。**在客户现场优先用本 skill**（核验留痕，不自动改远端）
- 阈值必须填**真实基线**：`P50 超过 X ms` 的空占位符等于没写；从 [web-perf](web-perf.md) / [sentry-mcp](sentry-mcp.md) / 现场历史指标取数
- 把"回滚触发条件"当作硬契约：与客户方书面确认后才算通过，口头共识不算（这是 gate 证据的关键一环）
- 制造业/具身场景要加自己的项：气隙环境离线包校验、固件/模型版本对照表、产线停机窗口确认、班次交接（ShiftHandover gate）
- 清单落地成文件（进交付包或 `.fde_scope/`），不要只留在会话里——否则无法追溯
- 装前门禁：按 [../README.md](../README.md) 规约第 3 条，安装后跑一次 [skill-criticagent](../cross-cutting/skill-criticagent.md) 记录本地行为判定，再把本页状态改为 ✅

## 项目应用位点
- Zone B→C 交界：`fde-scope engage advance` 触达 SLO / HandoffSignoff gate 前的固定核验动作
- 与 `docs/code_review_checklist.md` 配对：一个管代码合入前，一个管投递生产前
- 候选用法：把本 skill 的四段模板直接改造成 fde-scope 的 gate 证据模板（`fde_scope/engagement/gates/` 的工业 gate 各缺一份"上线核验"附件）

## 相关
[sre-runbooks](sre-runbooks.md) · [incident-response](incident-response.md) · [gstack-suite](../cross-cutting/gstack-suite.md) · [knowledge-work-suite](../cross-cutting/knowledge-work-suite.md) · 架构可视化插件的 `architecture-health`（文档/图与代码一致性，见 [architecture-visualization-suite](../cross-cutting/architecture-visualization-suite.md)）

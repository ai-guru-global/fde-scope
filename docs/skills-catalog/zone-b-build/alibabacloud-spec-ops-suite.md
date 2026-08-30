# alibabacloud-spec-ops 套件（阿里云 IaC 工作流 6 件套）

> 状态：✅ 已安装（Quest Marketplace 插件 alibabacloud-spec-ops v0.1.4，含 2 个评审 agent）· 类型：套件档案 · FDE 位点：Zone B deploy（IaC 交付流水线）

## 能做什么
把"基础设施需求"变成"可校验、可重放的 Terraform 落地"的完整流水线：`alibabacloud-planning`（需求 → 设计文档）→ `alibabacloud-writing-plans`（设计 → HCL/CLI 计划）→ `alibabacloud-terraform-codegen`（生成 Terraform 代码）→ `alibabacloud-validate`（并行派发 spec-reviewer + code-quality-reviewer 两个 agent 审规格符合性与代码质量）→ `alibabacloud-executing-plans`（执行 apply，**强制人工确认**）→ `alibabacloud-ram-permission-diagnose`（403/NoPermission 类权限诊断与修复建议）。

## 何时使用
- 客户要"资源开通 / 组网 / 上云"的 IaC 交付，需要可评审、可重放的过程资产（design.md → plan → code → apply 记录）
- 多环境（dev/staging/prod）一致开通，人工点控制台已经要出错的时候
- RAM 权限报错排查：先跑诊断，别盲改策略

**不用于**：单机 ECS 运维（→ [alibabacloud-workbench-cli](alibabacloud-workbench-cli.md)）；K8s 应用层部署（→ [kubernetes-specialist](kubernetes-specialist.md)）；非阿里云的 Terraform（本套件绑定 alicloud provider，通用流程自己写 plan）；只想查资源（→ [alibabacloud-core 套件](alibabacloud-core-suite.md)）。

## 最佳实践
- **流程顺序不可跳**：先 planning 再 codegen，validate 不过不 apply——跳步省下的时间都会在回滚时加倍还
- apply 前把 plan diff 展示给用户确认（工具强制 `--yes` 是底线不是充分条件）
- 权限报错先 `ram-permission-diagnose`，输出最小授权建议，别一上来给 `AdministratorAccess`
- 过程资产（design.md / plan 文件 / 生成代码）归档进交付物目录，Zone D 移交时就是"环境是怎么来的"的答案
- 存量资源先用 core 套件的 `terraform-import` 收编，再进本流水线管理增量
- state 文件是敏感资产：远端远端存储 + 锁，绝不进 git

## 项目应用位点
- fde-scope 制造业场景的云资源编排章节（数据源所在 VPC/白名单/对象存储开通）
- 与 connectors 的部署前置条件检查单互补：环境开通以 IaC 记录为准

## 相关
[alibabacloud-core-suite](alibabacloud-core-suite.md) · [kubernetes-specialist](kubernetes-specialist.md) · [docker-build-deploy](docker-build-deploy.md)

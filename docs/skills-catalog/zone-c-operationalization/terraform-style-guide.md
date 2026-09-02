# terraform-style-guide

> 状态：📦 可安装（registry 真名 `hashicorp/agent-skills@terraform-style-guide`；注意 canonical repo 是 `hashicorp/agent-skills`——`hashicorp/skills` 已 404 迁移，旧链接勿用）· 类型：代码规范 · FDE 位点：Zone C · IaC 交付/变更管理
> 安装：`npx skills add hashicorp/agent-skills@terraform-style-guide --directory ~/.qoder/skills -y` · 装机量：10.1K（skills.sh，2026-08-31）· 详情：https://skills.sh/hashicorp/agent-skills/terraform-style-guide

## 能做什么
HashiCorp **官方** Terraform 风格规范 skill（canonical repo `hashicorp/agent-skills` 的 `terraform` 插件下，同插件兄弟 skill：`terraform-test`——测试规范，references 含 CI/CD 集成、示例、mock provider；插件族另有 `packer`）。内容对应官方 Style Guide（developer.hashicorp.com/terraform/language/style）：标准文件组织（`terraform.tf` / `providers.tf` / `main.tf` / `variables.tf` / `outputs.tf` / `locals.tf`，vars/outputs 按字母序）、两空格缩进 + 等号对齐、块内顺序（meta-arguments → arguments → blocks，`lifecycle` 最后）、命名规则（小写下划线、单数、描述性名词且**不带资源类型**、单实例默认 `main`）、每个 variable 必带 `type` + `description`（建议加 `validation`）、每个 output 必带 `description`、敏感值 `sensitive = true`、`for_each` 优先于 `count`、版本约束钉死（`required_version`、provider `~>` 操作符）、`terraform fmt -recursive` + `terraform validate` 提交前必跑。

## 何时使用
- 交付物要 IaC 化：agent 生成的 Terraform 代码需要一套厂商中立的风格底线（多客户、多云环境通用）
- 评审客户已有 TF 代码：按官方规范出差距清单，而不是按个人口味
- 给客户定 IaC 规范文档：直接以官方 Style Guide 为基准，省一轮争论
- 代码评审 checklist：套件自带清单（fmt/validate、文件组织、vars/outputs 完整性、版本钉死、无硬编码凭证）

**不用于**：阿里云 IaC 的流水线与工具链落地（→ [alibabacloud-spec-ops-suite](../zone-b-build/alibabacloud-spec-ops-suite.md)，那边是阿里云 IaC 六件套：codegen/validate/executing-plans 等，管"怎么跑"；本页管"代码长什么样"）。分工：阿里云项目用那页生成与执行，用本页统一风格底线；非阿里云项目直接用本页。

## 新人上手
- **触发**：对 agent 说"按 HashiCorp 官方风格生成/整理这段 Terraform"、"review 这份 TF 代码的规范问题"
- **第一步**：装好后对存量模块跑一轮规范化：`terraform fmt -recursive` + `terraform validate` 先过机器检查，再让 agent 按套件 checklist 补齐（variables 的 `type`+`description`、outputs 的 `description`、`sensitive = true`、版本约束）
- **常见坑**：`terraform.tfstate`、`terraform.tfstate.backup`、`.terraform/`、`*.tfplan`、含敏感值的 `.tfvars` **严禁进 git**——state 里含明文 secrets；而 `.terraform.lock.hcl`（依赖锁文件）**必须**提交，漏了会导致客户环境重装出不同 provider 版本
- **常见坑**：`count` 与 `for_each` 混用错场景——批量同构资源用 `for_each`（删中间一个不引发整体重建），`count` 只用于条件创建（`count = var.enable_monitoring ? 1 : 0`）；agent 生成代码最容易在这里翻车，review 时重点看

## 最佳实践
- 提交前机器检查是硬门禁：`terraform fmt -recursive` + `terraform validate` 不过不进 PR；加分项加 `tflint`（lint）与 `checkov`/`tfsec`（安全扫描）
- 版本约束显式钉死：`required_version` + provider 版本操作符（`=` 精确 / `>=` 下限 / `~>` 右侧递增 / 区间），别裸奔最新版
- 变量全部可配置化 + `validation` 块约束取值（如环境只允许 dev/staging/prod），消灭散落的魔法字符串
- 密码类 variable/output 一律 `sensitive = true`，凭证只从环境注入——与 fde-scope 仓库"凭证仅存 env 变量"的不变量同源
- 多 region 用 aliased provider（`alias = "east"`），tags 统一走 `default_tags`（`ManagedBy = "Terraform"` 便于盘点归属）

## 项目应用位点
- Zone C 变更管理 phase：客户环境 TF 代码的规范基线与评审 checklist 来源
- Zone B `deploy`：部署物 IaC 化时的代码生成规范（agent 生成 TF 的风格约束）
- 交付文档：给客户的 IaC 规范章节直接引用官方 Style Guide 口径
- air-gap 现场：state/plan 禁入 git 的检查项进交付 checklist（对齐凭证不变量）

## 相关
[alibabacloud-spec-ops-suite](../zone-b-build/alibabacloud-spec-ops-suite.md) · [deploy-checklist](deploy-checklist.md) · [starops](starops.md)

# alibabacloud-core 套件（阿里云 OpenAPI/CLI 9 件套）

> 状态：✅ 已安装（Quest Marketplace 插件 alibabacloud-core v1.0.20）· 类型：套件档案 · FDE 位点：Zone B deploy（客户资源在阿里云）

## 能做什么
通过受约束的 MCP 服务器操作阿里云 OpenAPI：CLI 命令生成与语法指引（`alibabacloud-cli-guidance` / `suggest-cli`）、**跨账号资源查询**（`multi-account-query`，RD ListAccounts 拿 UID → `x_assume_account_id` 代入）、SDK 代码生成（`sdk-usage` / `terraform-code-generation`）、存量资源 Terraform 导入（`terraform-import`）、沙箱 RunScript 脚本生成（`mcp-core-script-generate`）、阿里云生态技能发现（`alibabacloud-find-skills`）、MCP 用法总纲（`mcp-core-best-practices`）。

## 何时使用
- 客户资源在阿里云：资源盘点、多账号/多 Member 环境查询、组网与产品配置确认
- 要生成调用阿里云 OpenAPI 的 SDK/CLI 代码（fde-scope 集成代码或一次性脚本）
- 存量资源要转 Terraform 管理的起步（import）

**不用于**：百炼/DashScope（→ [bailian-cli 家族](../cross-cutting/bailian-cli.md)）；无公网 IP 的单机 ECS 运维（→ [alibabacloud-workbench-cli](alibabacloud-workbench-cli.md)）；带评审与执行门禁的 IaC 全流程交付（→ [alibabacloud-spec-ops 套件](alibabacloud-spec-ops-suite.md)）。

## 新人上手

- **触发**：客户资源在阿里云时直接提需求，如"列出 cn-hangzhou 区域所有 ECS 实例"、"有没有管理 ECS/RDS/OSS 的 skill"；跨账号场景说"把这两个账号（RD Member）的资源盘一遍"
- **第一步**：对 agent 说清目标产品与操作即可，套件经 MCP Core 的 `AlibabaCloud___SearchApis` 找到目标 API，再由 `GenerateCLICommand`/`CallCLI` 生成并执行命令；不确定入口就先让 agent 读 `mcp-core-best-practices` 总纲，技能发现走 `alibabacloud-find-skills`
- **常见坑**：多账号直接查只会看到主账号——先 `ListAccounts` 把 alias 解析成 UID，再用 `x_assume_account_id` 代入目标账号；让 agent 手拼 OpenAPI URL/签名——签名、版本、region 应由 MCP server 保证，写操作先 dry-run、输出用 JMESPath 过滤只取需要的字段

## 最佳实践
- 只读查询直连；**写操作先 dry-run/plan 思维**，确认 diff 再发，AccessKey/Secret 永不进命令行与日志
- 多账号先 `ListAccounts` 解析 alias → UID，再用 `x_assume_account_id` 切换，别手工翻控制台
- CLI 输出用 JMESPath 过滤（`--output` / query 参数）只取需要的字段——省 token 也省得误读
- 走 MCP 工具而不是手拼 OpenAPI URL：签名/版本/.region 由 server 保证
- 生成的 SDK 代码过一遍 mypy/ruff 再进仓库，别把生成器风格直接合入

## 项目应用位点
- Zone B 制造业客户的云资源前置检查（网络/白名单/账号权限），对接 connectors 的数据源可达性
- deploy/tenant_manager 的租户云资源初始化脚本来源

## 相关
[alibabacloud-spec-ops-suite](alibabacloud-spec-ops-suite.md) · [alibabacloud-workbench-cli](alibabacloud-workbench-cli.md) · [bailian-cli](../cross-cutting/bailian-cli.md)

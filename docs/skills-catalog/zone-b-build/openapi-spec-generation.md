# openapi-spec-generation

> 状态：📦 可安装 · registry 真名 `wshobson/agents@openapi-spec-generation`（与建档名一致）· 类型：领域知识 · FDE 位点：Zone B · 部署（契约优先集成）
> 安装：`npx skills add wshobson/agents@openapi-spec-generation --directory ~/.qoder/skills -y` · 装机量：14.4K（skills.sh，2026-08-31）· 详情：https://skills.sh/wshobson/agents/openapi-spec-generation

## 能做什么
从代码生成、维护并校验 OpenAPI 3.1 规范的参考 skill：覆盖 design-first / code-first / hybrid 三种路线，支持 TypeScript/Python/Go 与 FastAPI、Express 等框架，工具链覆盖 Spectral（规范 lint）、Redocly（文档与打包）、OpenAPI Generator（多语言 SDK 生成）。核心产出是可直接交付的 API 契约与合规检查清单（$ref 复用、描述具体性、security schemes 完整性）。

## 何时使用
- 交付前给客户 API 出契约文档：从 FastAPI 路由生成 OpenAPI 3.1 spec 并补齐响应模型与安全定义
- 与客户异构系统（MES/ERP 等）联调前冻结契约（contract-first），避免双方各自实现后对不上
- 校验客户已有 spec 的质量：Spectral lint 过一遍，补 $ref 复用与 security schemes

**不用于**：Postman Collection/环境与 agent-ready API 生命周期管理（→ [postman](postman.md)，那页管接口调用与运维，本页只管 spec 生成）；阿里云 OpenAPI 的调用本身（→ [alibabacloud-core-suite](alibabacloud-core-suite.md)）。

## 新人上手
- **触发**：对 agent 说"给我的 FastAPI 服务生成 OpenAPI 3.1 规范，按契约优先补齐响应模型和安全定义"
- **第一步**：装完后让 agent 从现有框架导出 spec 起步（FastAPI 自带 `/openapi.json`），再按 skill 检查表审三件事：`$ref` 复用、描述具体性、security schemes 完整性
- **常见坑**：FastAPI 路由不写 `response_model` 时自动生成的 spec 缺响应 schema——契约文档看着全、实际响应结构是空的，联调时才暴露
- **常见坑**：`servers` 字段别把内网 host/IP 直接带进交付件，气隙/制造业客户会视为内网拓扑泄漏

## 最佳实践
- 用 `$ref` 复用 schema/参数/响应；复制粘贴的定义改一处漏一处
- security schemes 全部定义（skill 明确要求 "Don't skip security"），交付件不留匿名可调的假设
- spec 与代码同步：Spectral lint 进 CI，spec 与实现不一致按 bug 处理而不是文档问题
- 描述写具体（"Don't use generic descriptions"）：字段含义、单位、枚举值写全，客户二开靠它

## 项目应用位点
- Zone B 部署阶段：交付物中的 API 契约文档生成与校验
- 制造业客户系统集成：contract-first 冻结接口后再联调
- 客户侧二开 SDK 生成（OpenAPI Generator 多语言产出）

## 相关
[postman](postman.md) · [alibabacloud-core-suite](alibabacloud-core-suite.md) · [vercel-deploy](vercel-deploy.md)

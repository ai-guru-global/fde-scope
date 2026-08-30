# postman

> 状态：✅ 已安装（Quest Marketplace 插件 postman v1.0.1，MCP 连接器）· 类型：API 生命周期 · FDE 位点：Zone B validate（客户 API 联调）

## 能做什么
Qoder 内的完整 API 生命周期：同步 Collection、生成类型化客户端代码、发现 API、运行测试、创建 Mock、改进文档、安全审计，并分析 API 对 AI Agent 的就绪度。三个 skill 分工：`postman-knowledge`（MCP 工具用法与取舍）、`postman-routing`（把 API 请求路由到正确命令）、`agent-ready-apis`（8 支柱 48 检查的 agent 就绪度评分与整改建议）。

## 何时使用
- 对接客户 MES/Historian/Zammad/Salesforce 等 REST API **之前**：先 Collection + Mock 验证契约，别拿生产环境试错
- 给 fde-scope 连接器写集成测试：请求/断言沉淀在 Collection 里随回归跑
- 评估客户 API 对 agent 调用的就绪度（agent-ready-apis 报告可直接当"给客户的 API 改进清单"交付物）

**不用于**：工业协议（OPC UA / MQTT / ROS2 不是 HTTP，→ [mqtt-development](mqtt-development.md) 与连接器代码）；一次性验证（为一次 curl 建 Collection 是负资产）；客户 API 无 OpenAPI/无文档时先做发现，别凭空猜端点。

## 最佳实践
- 先导入 OpenAPI/抓包生成 Collection，**不要手写请求**——手写版本两周后就没人信了
- Mock 先行：前端/agent 开发不必等客户排期联调，契约先冻结
- environment 变量隔离客户环境（dev/staging/prod），生产密钥绝不进 Collection 文件
- 断言写进请求的 Tests 标签，Collection Runner 就是免费回归套件
- agent-ready-apis 的评分维度（鉴权/分页/幂等/错误语义等）也是我们自己写 API 的检查单
- 与客户共享前清 Collection 的历史与变量快照，Postman 同步会把敏感值带上去

## 项目应用位点
- fde_scope/connectors 的 HTTP 类连接器（Zammad / Salesforce / MES REST）联调与契约回归
- integrations 模块对外暴露 API 的自检（发布前跑一遍 agent-ready-apis）

## 相关
[mqtt-development](mqtt-development.md) · [query](query.md)（数据侧验证） · [code-review](../cross-cutting/code-review.md)

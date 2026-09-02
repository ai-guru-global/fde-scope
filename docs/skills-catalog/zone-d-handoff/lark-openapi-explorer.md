# lark-openapi-explorer

> 状态：📦 可安装（未装；registry 真名 `open.feishu.cn@lark-openapi-explorer`，与建档名一致，但 **owner 名是域名 `open.feishu.cn`**——skills.sh 上的特殊格式，与常见 owner/repo 形态不同）· 类型：API 集成（飞书/Lark 开放平台）· FDE 位点：Zone D · 文档/消息/审批集成
> 安装：官方通道（larksuite/cli README 确认）：`npx @larksuite/cli@latest install`（agent skills 经官方 CLI 安装）；skills.sh 形式 `npx skills add open.feishu.cn@lark-openapi-explorer --directory ~/.qoder/skills -y` 未经实测，装前以官方 README 为准 · 装机量：**635.6K（skills.sh，2026-08-31，本次行业调研全场最高）** · 详情：https://skills.sh/open.feishu.cn/lark-openapi-explorer
> 说明：skills.sh 条目页为 JS 渲染薄页（描述仅一句 "Skills from the open.feishu.cn/lark-openapi-explorer repository"），真实能力以飞书官方 `larksuite/cli`（github.com/larksuite/cli）为准。

## 能做什么
飞书/Lark 官方（larksuite org）的 OpenAPI 探索技能：帮 agent 检索并正确调用飞书开放平台 API——文档、消息（IM）、审批、通讯录、日历等域。配套官方 CLI 提供 `lark-cli docs`、`lark-cli im`（如 `messages-send`）、`lark-cli approval`、`lark-cli contact`、`lark-cli calendar` 等命令族（2026-08-31 读官方 README 核对）。635.6K 装机是本次调研全场最高，侧面说明飞书生态的 agent 化需求旺盛——客户协作平台在飞书时这是首选集成入口。

## 何时使用
- 客户协作平台在飞书：交付物要写进飞书文档/知识库、给项目群发周报与验收通知
- Zone D 移交：培训材料分发、演示预约、审批流（`lark-cli approval`）对接
- 集成开发前查 API 真实定义：避免凭记忆拼 endpoint 和参数

**不用于**：企业微信场景——wecom 系（wecomcli-* 技能）已覆盖企微侧，与本页按客户平台二选一、互不替代；不做跨平台 IM 中间层抽象。

## 新人上手

- **触发**："把这份交付文档发到客户飞书群"/"查一下飞书审批 API 怎么创建审批实例"
- **第一步**：`npx @larksuite/cli@latest install`（官方 README 原话的安装通道），装完先让 agent 用 explorer 查一个最小 API（发一条测试消息）打通凭证链路，再接真实业务
- **常见坑**：owner 是域名 `open.feishu.cn`，按 owner/repo 解析 registry 名的工具可能失败——装不上时换官方 CLI 通道
- **常见坑**：飞书 API 要应用凭证（自建应用/商店应用 + 对应权限范围）——在客户环境必须走客户自己的飞书应用与开通审批，不要拿个人测试应用打客户租户；凭证只进 env（本仓库不变量第 3 条）

## 最佳实践
- Do：先 explorer 查 API 定义再写代码，不凭记忆猜 endpoint/参数
- Do：气隙/内网客户先确认飞书私有化部署形态与出口策略（feishu.cn 与 larksuite.com 域名差异），再谈集成
- Don't：不把机器人凭证写进交付物、manifest 或日志
- Don't：不与 wecomcli-* 技能混用——按客户的协作平台选一边，避免两套通知通道打架

## 项目应用位点
- Zone D：交付文档推送（飞书文档/群消息）、培训材料分发、验收与结项通知自动化
- Zone C：运维告警经飞书群/审批的通知集成位
- 阿里云生态客户常见"钉钉/飞书并存"：本页只覆盖飞书；钉钉侧本库暂无对应页

## 相关
[document-generate](document-generate.md) · [anthropic-documentation](anthropic-documentation.md) · [pptx](pptx.md)

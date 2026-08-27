# troubleshooting

> 状态：✅ 已安装（chrome-devtools-mcp 插件 v1.2.0）· 类型：工具排障 · FDE 位点：Zone C operate（浏览器自动化通道）

## 能做什么
专治 **Chrome DevTools MCP 本身**连不上/起不来的问题：`list_pages` / `new_page` / `navigate_page` 失败、server 初始化失败、target 丢失、连接超时。会用 MCP 文档 + 环境检查定位是浏览器、扩展、端口还是配置的问题。

## 何时使用
- 浏览器自动化突然不动了（agent 报 MCP 工具错误）
- 现场机器上 Chrome 版本/无头模式/代理设置导致 MCP 无法附加
- 需要在新环境（客户笔记本、内网机器）第一次打通浏览器调试通道

**不用于**：网页业务逻辑 bug（→ [chrome-devtools](chrome-devtools.md)）；性能问题（→ [web-perf](web-perf.md)）；MCP server 的选型评估（→ [mcp-criticagent](../cross-cutting/mcp-criticagent.md)）。

## 最佳实践
- 顺序：确认 Chrome 进程与远程调试端口 → 确认 MCP server 日志 → 再动配置；不要一上来就重装
- `--slim` 模式不支持该 skill 的能力，注意配置差异
- 内网/代理环境要检查 loopback 与证书拦截，这是最常见的静默失败原因
- 打通后把可用配置固化到项目（README 或本地脚本），避免每台现场机重排一次

## 项目应用位点
- Zone B/C：Web 控制台与 PawApp 的 UI 自动化前置通道
- 交付现场的浏览器验证（客户只允许用他们自己的机器时）

## 相关
[chrome-devtools](chrome-devtools.md) · [web-perf](web-perf.md) · [mcp-criticagent](../cross-cutting/mcp-criticagent.md)

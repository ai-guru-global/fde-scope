# browser-use（MCP server）

> 状态：✅ 已连接（客户端内置，磁盘无安装文件）· 类型：MCP 服务器 · **16 个工具** · FDE 位点：Zone B 验证 / Zone C 排障（轻量侧）

## 能做什么

面向**已开页面**的轻量浏览器自动化，16 个工具：`list_pages` / `select_page` / `navigate_page`、交互 `click` / `fill` / `hover` / `drag` / `press_key`、取证 `take_snapshot` / `take_screenshot` / `evaluate_script` / `upload_file` / `handle_dialog` / `wait_for`、诊断 `list_console_messages` / `list_network_requests`。

与 [chrome-devtools](chrome-devtools-mcp.md)（29 工具）的关系：**browser-use 少而轻**——没有 `new_page`/`resize_page`/`emulate`，没有性能追踪、堆快照、单请求详情。它是"把页面点一遍"的工具，不是"把页面查透"的工具。

## 何时使用

- 快速的页面操作验证：登录、点按钮、填表单、确认跳转
- 简单取证：页面截图、控制台报错扫一眼、请求列表扫一眼
- 已有标签页里的连续小步骤操作（无需新建/调整视口）

**不用于**：性能/内存分析、设备仿真、响应式检查（→ [chrome-devtools](chrome-devtools-mcp.md)）；桌面原生应用（→ [computer-use](computer-use.md)）；批量抓取（→ [firecrawl](firecrawl-mcp.md)）。注意另有一个 agent-browser 插件/skill 与本 server 场景重叠，能力调研时不要混淆三者。

## 新人上手

- **触发**：对 agent 说"帮我点一下这个页面 / 登录一下 / 截个图看看"
- **第一步**：已有标签页里的轻量操作直接说需求即可；需要新建标签页/调视口/性能分析时明确让 agent 换 chrome-devtools
- **常见坑**：它没有 `new_page`/`resize_page`/`emulate`——在 browser-use 里绕新标签页是死路；`handle_dialog` 会代答原生确认框，调用前想清楚业务上该确认还是取消

## 最佳实践

- 同样遵循**先 `take_snapshot` 再交互**：AX 树是元素定位的依据
- 没有 `new_page`——需要新标签页/新视口时直接换 chrome-devtools，别在 browser-use 里绕
- `handle_dialog` 会代答浏览器原生确认框：调用前想清楚业务上该确认还是取消
- `wait_for` 等待条件而非固定延时；页面慢时配合 `list_network_requests` 看卡在哪个请求
- 与 chrome-devtools 操作的是同一个 Chrome：并行会话下的页面抢占问题同样存在

## 项目应用位点

- Zone B：交付 demo 的冒烟路径（打开 → 登录 → 核心动作 → 截图）用 browser-use 走最快
- Zone C：客户报障时快速复现"我这里也点不出来"的轻量取证
- 与 fde-scope 门户 `site/index.html` 的验收互补：重验收用 chrome-devtools，日常检查用 browser-use

## 相关

[总览](overview.md) · [chrome-devtools](chrome-devtools-mcp.md) · [computer-use](computer-use.md) · [firecrawl](firecrawl-mcp.md)

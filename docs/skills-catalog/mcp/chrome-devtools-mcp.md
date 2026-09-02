# chrome-devtools（MCP server）

> 状态：✅ 已连接（插件 chrome-devtools-mcp v1.2.0）· 类型：MCP 服务器 · **29 个工具** · FDE 位点：Zone B 验证 / Zone C 排障
> skill 页：[chrome-devtools](../zone-c-operationalization/chrome-devtools.md)（方法论）· [web-perf](../zone-c-operationalization/web-perf.md) / [debug-optimize-lcp](../zone-c-operationalization/debug-optimize-lcp.md)（性能专项）

## 能做什么

本地 Chrome 的**调试全栈**工具面，29 个工具分五族：

| 工具族 | 工具 | 用途 |
|---|---|---|
| 页面管理 | `list_pages` / `new_page` / `navigate_page` / `select_page` / `close_page` / `resize_page` / `emulate` | 多标签管理、导航、视口调整、**设备/网络仿真** |
| 交互 | `click` / `fill` / `fill_form` / `hover` / `drag` / `type_text` / `press_key` / `upload_file` / `handle_dialog` / `wait_for` | 表单、点击、键盘、上传、对话框、条件等待 |
| 取证 | `take_snapshot` / `take_screenshot` / `evaluate_script` | AX 树快照（给 agent 看的结构）、截图、页内 JS 执行 |
| 网络与控制台 | `list_network_requests` / `get_network_request` / `list_console_messages` / `get_console_message` | 请求瀑布/单请求详情、报错与日志取证 |
| 性能 | `performance_start_trace` / `performance_stop_trace` / `performance_analyze_insight` / `lighthouse_audit` / `take_heapsnapshot` | 性能追踪与 insight 解读、Lighthouse 审计、堆快照（内存泄漏） |

## 何时使用

- **Web 交付验收**：功能走查（snapshot + 交互）+ 性能（trace/lighthouse）+ 网络（请求取证）一站式
- **排障取证**：console 报错、失败请求的响应体、竞态时的时序截图
- **性能专项**：LCP/INP 调优走 trace → `performance_analyze_insight` 读结论，配合 [debug-optimize-lcp](../zone-c-operationalization/debug-optimize-lcp.md)
- **内存泄漏**：`take_heapsnapshot` + [memory-leak-debugging](../zone-c-operationalization/memory-leak-debugging.md)
- **响应式检查**：`resize_page` / `emulate` 模拟移动视口与弱网

**不用于**：纯数据抓取（[firecrawl](firecrawl-mcp.md) 更省）；非浏览器桌面应用（[computer-use](computer-use.md)）；需要离线确定性产物的批量截图（并行会话共用 Chrome 会互相干扰，用隔离 profile 的 headless CLI）。

## 新人上手

- **触发**：对 agent 说"打开页面走一遍并截图 / 看看 console 报什么错 / 测下 LCP / 跑个 Lighthouse"
- **第一步**：交互前先让 agent `take_snapshot` 拿 AX 树——click/fill 都基于快照元素定位；取证顺序固定 snapshot → console → network
- **常见坑**：并行会话共用同一个 Chrome，`select_page`/视口互相抢占——确定性截图改用隔离 profile 的 headless CLI；`wait_for` 等条件而非固定 sleep

## 最佳实践

- **先 `take_snapshot` 再交互**：AX 树快照给出可寻址的元素结构，比"截图猜坐标"可靠一个数量级；`click`/`fill` 都基于快照里的元素定位
- **并行会话抢 Chrome**：多个 agent 会话共用同一个浏览器时，`select_page`/视口设置会互相抢占——长流程取证前确认没有并行会话在操作浏览器，或改用 headless CLI
- `wait_for` 等条件而不是 `sleep`：等文本出现/请求完成，避免固定延时造成的假阳性
- `emulate` 可仿真 CPU 降速与网络节流——性能问题客户"复现不出来"时先用它
- `evaluate_script` 是双刃剑：取证方便，但注入的脚本要幂等、无副作用，别在客户页面留状态
- 网络取证先 `list_network_requests` 看瀑布，再对可疑请求 `get_network_request` 看请求/响应体——报障单里这对组合最有说服力

## 项目应用位点

- fde-scope 的 Web 交付（pawapp 前端、门户 site/index.html）验收：双模式（浅/深）+ 多视口截图就是用本 server 的 `resize_page` + `take_screenshot` 完成的
- Zone C runbook：浏览器类故障的第一取证步骤固定为 snapshot → console → network
- 客户现场 Demo：`emulate` 弱网演示降级表现，是讲弹性的好素材

## 相关

[总览](overview.md) · [browser-use](browser-use.md) · [computer-use](computer-use.md) · [chrome-devtools skill 页](../zone-c-operationalization/chrome-devtools.md) · [web-perf](../zone-c-operationalization/web-perf.md) · [troubleshooting](../zone-c-operationalization/troubleshooting.md)

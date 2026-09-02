# extension-market（MCP server）

> 状态：✅ 已连接（客户端内置，磁盘无安装文件）· 类型：MCP 服务器 · **2 个工具** · FDE 位点：横切（能力获取）
> skill 入口：[skill-discovery](../cross-cutting/skill-discovery.md)（skills.sh 生态检索）

## 能做什么

插件市场的会话内工具面，2 个工具：

- `search_extensions`：按关键词检索可安装的插件/skill/MCP 连接器
- `install_extension`：把选中的插件安装到本机（写入 `~/.qoder/plugins/`）

与 skill-discovery 的分工：`find-skills` 面向 skills.sh 社区源（`npx skills add`），本 server 面向 Qoder 官方市场——两边都查再决定装哪个。

## 何时使用

- 用户问"有没有能做 X 的插件/skill"：先 `search_extensions` 查官方市场，再用 [skill-discovery](../cross-cutting/skill-discovery.md) 查社区源，对比后推荐
- 本手册库 📦 项的安装执行端：建档时标记可安装，用户点头后从这里装
- 新客户环境初始化：按手册库清单快速补齐能力

**不用于**：未经用户同意的主动安装/升级——改的是用户环境，必须先展示候选与来源再装；装前评估走 [skill-criticagent](../cross-cutting/skill-criticagent.md) / [mcp-criticagent](../cross-cutting/mcp-criticagent.md)（见维护规约的装前门禁）。

## 新人上手

- **触发**：对 agent 说"有没有能做 X 的插件 / 帮我装个 Y skill"
- **第一步**：先 `search_extensions` 查官方市场，再用 [skill-discovery](../cross-cutting/skill-discovery.md) 查社区源——两边对比后给用户候选清单，不直接装
- **常见坑**：未经用户同意的主动安装是红线（改的是用户环境）；装完必须跑 `make check-local` 对账并回填手册库状态（📦 → ✅ + 安装日期）

## 最佳实践

- **先搜后装、先评估后装**：搜索结果给出候选 → 用户确认 → criticagent 评估 → 安装 → 回填手册库状态（📦 → ✅ + 安装日期）
- 安装后跑 `make check-local` 对账：手册库与真实安装保持一致是本库的生命线
- 记录版本号：页内声明的版本与实装版本不一致会被 `check-local` 提醒
- 推荐时给用户对比信息（功能、来源、维护活跃度），而不是只给一个名字

## 项目应用位点

- 手册库维护流：本库 89+ 页的 📦 项巡检与回填（[维护规约](../README.md)）
- 新人上手：环境缺什么能力，从这里和 skill-discovery 两个入口补齐

## 相关

[总览](overview.md) · [skill-discovery](../cross-cutting/skill-discovery.md) · [skill-criticagent](../cross-cutting/skill-criticagent.md) · [mcp-criticagent](../cross-cutting/mcp-criticagent.md)

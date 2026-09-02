# 内置工具总览

> 状态：✅ 随客户端自带（零安装，永远可用）· 类型：能力底座总览 · FDE 位点：横切（所有 Zone 的执行层）

## 能做什么

内置工具是 agent 的"手和脚"：不需要安装、不需要配置，会话开始就可用。新人先记住三层分工（详见 [MCP 服务器总览](../mcp/overview.md)）：**内置工具管本地执行，MCP 管外部系统，skill 管方法论**。

按用途分组的全景清单：

| 分组 | 工具 | 一句话 |
|---|---|---|
| 文件读写 | `Read` / `Write` / `Edit` | 读文件/图片/PDF/notebook、新建文件、精确字符串替换编辑 |
| 搜索定位 | `Glob` / `Grep` | 按文件名模式找文件、按正则搜内容（ripgrep） |
| 执行 | `Bash` | 跑 shell 命令，支持后台运行（`run_in_background`）与超时控制 |
| Web | `WebFetch` / `WebSearch` | 抓取单个 URL 并按提示提取、联网搜索 |
| 规划与确认 | `EnterPlanMode` / `ExitPlanMode` / `AskUserQuestion` | 进入规划模式出方案、提交计划待批、向用户提问选择题 |
| 任务与目标 | `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate` / `TaskStop` + `CreateGoal` / `GetGoal` / `UpdateGoal` | 多步任务的建/查/改/停；会话级目标管理 |
| 委派与并行 | `Agent` | 派发子 agent（Explore/Plan/general-purpose 等类型）跑独立任务 |
| 技能 | `Skill` | 调用已安装的 skill（本手册库的主角） |
| Notebook | `NotebookEdit` | Jupyter notebook 单元格替换/插入/删除 |
| 图像生成 | `ImageGen` | 按提示生成图片到指定路径 |
| MCP 元工具 | `mcp_list` / `mcp_get` / `mcp_call` | 发现/读 schema/调用 MCP 工具（lazy-loading 三步） |
| 多会话 | `create_chat_session` / `fork_chat_session` / `list_chat_sessions` / `read_chat_session` / `send_message_to_chat_session` / `wait_chat_sessions` | 开独立会话、从已有 Turn 分叉、跨会话读写与等待 |

## 何时使用

- **任何任务都从这里起步**：先确认"这件事是内置工具的组合就能做，还是要 MCP/skill"——能用 `Read`/`Grep`/`Bash` 直接完成的不要绕道
- **接手陌生环境**：`Glob` + `Grep` + `Read` 三件套是摸底基本功；大范围探索派 `Agent(Explore)` 省自己的上下文
- **多步任务**：3 步以上先 `TaskCreate` 列清单，边做边更新状态——既是进度条也是防遗漏

**不用于**：本页是地图不是手册，工具参数以工具自身 schema 为准；"哪些能力需要安装"的问题看 [MCP 服务器总览](../mcp/overview.md) 与 [skill-discovery](../cross-cutting/skill-discovery.md)。

## 新人上手

- **触发**：零安装、随会话可用——任何任务都从本页 12 组工具的组合里起步，新人入职先通读一遍分组表
- **第一步**：拿一个陌生目录练 `Glob` + `Grep` + `Read` 三件套摸底，再用 `TaskCreate` 把手头多步任务列成清单体验进度跟踪
- **常见坑**：专用工具优先于 Bash——`cat`/`sed`/裸 `grep` 能干但不如 `Read`/`Edit`/`Grep` 结构化且权限清晰；`Edit`/`Write` 前没 `Read` 会直接报错

## 最佳实践

- **专用工具优先于 Bash**：读文件用 `Read` 不用 `cat`，改文件用 `Edit` 不用 `sed`，搜索用 `Grep`/`Glob` 不用裸 `grep`/`find`——专用工具权限更清晰、输出更结构化
- **改之前先读**：`Edit`/`Write` 要求本会话先 `Read` 过目标文件；文件被外部改动后读状态会失效，需重读再改
- **独立调用并行发**：多个互不依赖的调用（如同时读三个文件）放在同一条消息里并行；有依赖的必须等前一个结果
- **长任务进后台**：构建/测试用 `Bash` 的 `run_in_background`，完成会收到通知——不要 `sleep` 轮询
- **委派的选择**：只找位置用 `Explore`（快、只读）；要方案用 `Plan`；开放性多步调研用 `general-purpose`——但"理解"不能委派，结论要自己核对

## 项目应用位点

- fde-scope 的开发流：`make test` / `make check-catalog` / `make lint` 就是 `Bash` 跑的验证命令；改代码前 `Read` 目标文件是硬约束
- 本手册库的批量维护：页面改动 → `Bash` 跑门禁 → 确认输出后再报告完成（见 [使用纪律](discipline.md)）
- 客户现场：`Glob`/`Grep` 是在陌生仓库里找证据的第一选择

## 相关

[使用纪律](discipline.md) · [MCP 服务器总览](../mcp/overview.md) · [using-superpowers-family](../cross-cutting/using-superpowers-family.md) · [dispatching-parallel-agents](../cross-cutting/dispatching-parallel-agents.md)

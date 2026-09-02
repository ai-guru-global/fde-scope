# record-and-replay（MCP server）

> 状态：✅ 已连接（客户端内置，磁盘无安装文件）· 类型：MCP 服务器 · **3 个工具** · FDE 位点：横切（经验 → skill 的转化器）
> skill 入口：record-and-replay（录制工作流 → 生成可复用 skill）

## 能做什么

把**真人演示的 macOS 操作流**录制成事件流，再加工成可复用 skill 的管道，3 个工具：

- `event_stream_start`：开始录制（键盘/鼠标/应用事件流）
- `event_stream_status`：查询录制状态
- `event_stream_stop`：结束录制，产出事件流供 skill 生成

配合 record-and-replay skill：用户在屏幕上把流程做一遍 → 事件流被捕获 → agent 从中提炼步骤、参数与分支 → 产出一份 SKILL.md。是"会做"到"可复用"的转化器。

## 何时使用

- 客户或同事演示了一套**没有文档的操作流程**（内部系统、遗留软件）：录下来直接变成 skill，移交价值极高
- 自己反复做某套 GUI 流程（每周一次的数据导出、固定的配置检查）：第一次录制，之后交给 agent
- 新人 FDE 想快速把"老师傅的手感"固化成团队资产

**不用于**：纯终端/代码流程（直接写 skill 更精确）；有官方 API 的系统（API 优先于 UI 回放）；含密码/敏感输入的流程（录制会捕获输入内容）。

## 新人上手

- **触发**：对 agent 说"把我接下来这遍操作录下来做成 skill / 记录这个流程"
- **第一步**：`event_stream_start` 开始录制 → 用户在屏幕上完整做一遍 → `event_stream_stop` 结束并产出事件流 → agent 提炼成 SKILL.md
- **常见坑**：回放质量上限就是演示质量——录制前想清楚剧本一次做对；密码/敏感输入会被捕获，需要凭证的步骤在生成的 skill 里改成环境变量

## 最佳实践

- **录制前想清楚剧本**：一次做对，少走死路——回放技能的质量上限就是演示质量
- 敏感信息（密码、客户数据）不进录制流；需要凭证的步骤在生成的 skill 里改为环境变量
- 录制产出的事件流只是原料：**生成 skill 后必须人工审阅**步骤描述与边界条件，再进 [writing-skills](../cross-cutting/writing-skills.md) 的校验流程
- 命名与建档：生成的 skill 按手册库六段模板补一页，登记进 README

## 项目应用位点

- 客户移交（Zone D）：把客户专家的操作经验录制成 skill，作为移交物的一部分
- [computer-use](computer-use.md) 的黄金搭档：录制真人桌面流 → skill 化 → 以后由 computer-use/agent 代做
- fde-scope 团队内部：重复性 GUI 巡检流程的固化

## 相关

[总览](overview.md) · [computer-use](computer-use.md) · [writing-skills](../cross-cutting/writing-skills.md) · [create-skill](../cross-cutting/create-skill.md)

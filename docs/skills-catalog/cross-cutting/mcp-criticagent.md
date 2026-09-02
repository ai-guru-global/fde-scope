# mcp-criticagent

> 状态：✅ 已安装（research-copilot 插件 v1.0.0）· 类型：元能力/门禁 · FDE 位点：横切（MCP 安装前置）

## 能做什么
端到端评估 **MCP server / tool**：从 GitHub URL 或 npm 包部署、测协议通信与工具调用、跑 AI 生成的智能测试、并给出仓库可持续性与热度评分。回答"这个 MCP 到底能不能用、值不值得接"。

## 何时使用
- 客户/团队要接一个新 MCP server（数据库、监控、内部平台）前的验收
- MCP 在本地起不来、工具调用失败，需要区分是 server 问题还是客户端配置
- 对比同类 MCP（例如两种 Sentry/两种数据库接入）选一个长期依赖
- 本项目相关：评估 QwenPaw 宿主可选 MCP 扩展（见 [qmind-mcp](../zone-a-pre-engagement/qmind-knowledge.md) 的 MCP Server 模式）

**不用于**：评估 skill（→ [skill-criticagent](skill-criticagent.md)）；MCP 的线上故障排障（→ [troubleshooting](../zone-c-operationalization/troubleshooting.md)）；写 MCP server（用 SDK 直接开发）。

## 新人上手

- **触发**：贴一个 GitHub URL 或 npm 包名问 agent「这个 MCP 能不能接 / does this MCP work」——SKILL.md 声明只贴链接也触发
- **第一步**：仓库根目录先 `uv sync`（另需 Node 18+ 供 npx 部署），再跑三层评估：`uv run python -m src.main test-url "https://github.com/OWNER/REPO" --no-db-export`，报告落在 `data/test_results/`（JSON + HTML）
- **常见坑**：没配 `DASHSCOPE_API_KEY` 时第 2 层智能测试会退化为基础协议测试——报告必须说清哪层跑了、哪层跳过，不许把部分结果当完整评估
- **常见坑**：部署会在本机执行第三方 npm 包，不受信的包放沙箱/容器里跑；`final_score` 只评仓库可持续性（星标/提交活跃），第 1 层部署或调用失败照样判"不可用"，别被高分迷惑

## 最佳实践
- 先在**隔离环境**部署评估，再进个人/团队配置：MCP server 会拿到工具调用权限，等于给 agent 手
- 重点看三件事：凭据处理方式（是否明文/env）、工具副作用（有没有写操作）、错误语义是否可诊断
- 智能测试要人工补一轮"危险用例"：让它删/改数据的工具必须在评估阶段就发现
- 评估结论进 catalog：为将来要用的 MCP 建页（本手册库目前以 skill 为主，MCP 只在 architecture-visualization 等插件里出现过）
- 版本锁定：MCP 协议与 server 版本演进快，评估通过的版本要记进页面头部
- 与交付场景对齐：现场气隙环境通常禁止外连 MCP，评估通过也要确认网络策略可行性

## 项目应用位点
- 横切：MCP 接入的唯一入口评估
- Zone B deploy：客户平台 MCP（数据库/监控）接入前的把关

## 相关
[skill-criticagent](skill-criticagent.md) · [troubleshooting](../zone-c-operationalization/troubleshooting.md) · [qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md)

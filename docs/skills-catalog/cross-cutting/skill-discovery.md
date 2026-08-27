# find-skills

> 状态：✅ 已安装（`~/.qoder/skills/find-skills`）· 类型：元能力/skill 发现 · FDE 位点：横切
> 本 catalog 的 📦 条目全部经由它检索（`npx skills find`），registry 站点：https://skills.sh/

## 能做什么
把"我需要一个能力"变成"找到并安装对的 skill"：`npx skills find <query>` 检索开放 skill 生态、`npx skills add <owner/repo@skill> --directory ~/.qoder/skills -y` 安装、`npx skills check` / `update` 做版本巡检；无结果时提示用 `npx skills init` 自建。

## 何时使用
- 遇到"这件事我该怎么做"且明显属于通用重复任务（测试、部署、评审、文档、设计）
- 每次季度巡检：确认已装项是否有更新、是否有更优替代
- 建/维护本手册库时：核实 registry 真实条目名与热度（本 catalog 已用它更正过 4 处失真条目名）

**不用于**：已经知道要装什么（直接 `add`）；评估质量与安全（→ [skill-criticagent](skill-criticagent.md) / [mcp-criticagent](mcp-criticagent.md)）；生态内没有时（→ [create-skill](create-skill.md) 自建）。

## 最佳实践
- 检索词要具体："docker deploy" 优于 "deploy"；同义词多试几组（evaluation / evals / benchmark）
- **以热度 + 官方 org + 安全审计三项做初筛**，再进 critic 门禁：热度高不代表适合本项目
- 安装目录固定在 `~/.qoder/skills`，避免多处安装导致同名 skill 路由冲突
- 装完立刻在本 catalog 建档（五段模板）+ 更新 README 索引——否则一个月后没人记得为什么装它
- 同名条目要甄别来源（例：`evaluating-llms-harness` 有 firecrawl 与第三方两个同名版本）
- 巡检节奏：季度一次 `npx skills check`，只处理真正在用的 skill，不追求"全部最新"

## 项目应用位点
- 横切：本手册库的维护入口；Zone B/C/D 每个阶段的能力补齐都从它开始

## 相关
[skill-criticagent](skill-criticagent.md) · [create-skill](create-skill.md) · [create-plugin](create-plugin.md)

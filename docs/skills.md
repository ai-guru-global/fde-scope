# Skill 沉淀系统（Skills / Methodology capture）

> FDE 在现场的每一步（调研、实施、调优、方法论）都可以沉淀为可复用的技能，
> 跨 engagement、跨客户复用。这是 FDE 从"做项目"到"积累资产"的关键机制。

## 设计原则

1. **文件库，零数据库依赖** —— 技能存为 `.fde_scope/skills/`（每个技能一个目录：
   `skill.md` 正文 + `meta.json` 元数据），随项目携带，git 友好。
2. **草稿优先** —— 自动捕获与 gate 提示产生的都是草稿（`draft`），不直接入库，
   由 `skill review` 人工审阅后发布，保证库的信噪比。
3. **可导出给 Agent** —— 导出产物遵循 Anthropic Agent Skills 规范
   （`<skill-name>/SKILL.md` + YAML frontmatter），可直接被 AgentScope 2.0 与
   QwenPaw 消费——沉淀的经验即时变成 Agent 能力。

## 数据模型

| 字段 | 说明 |
|---|---|
| `title` / `body_md` | 标题与 Markdown 正文 |
| `category` | 四类：`research`（调研）/ `implementation`（实施）/ `optimization`（调优）/ `methodology`（方法论） |
| `tags` | 自由标签（如 `opcua`、`fat`） |
| `status` | 生命周期：`draft` → `published` → `archived` |
| `source` | 来源：`manual` / `auto_capture` / `gate_hint` / `journal` |
| `source_engagement` / `phase_slug` / `gate_slug` | 关联上下文（哪个项目、哪个阶段、哪个 gate） |
| `version` | 每次 `edit` 自增 |

## 三种沉淀入口

| 入口 | 触发方式 | 说明 |
|---|---|---|
| 手动 | `fde-scope skill add` | 随时沉淀，四类分类 + 标签 |
| gate 阻塞提示 | `engage advance` / `gate check` 失败时自动 | 生成预填草稿（`gate_hint`，含 gate slug 与 blockers），`skill review` 完善 |
| 操作自动捕获 | `engage advance` 成功 / `gate check` 通过时自动 | 轻量记录（`auto_capture`），`skill review` 完善 |
| 现场记录桥接 | Web 工作台 Journal → "沉淀为技能" | `kind` 映射到 `category`（research/implementation/optimization） |

## CLI

```bash
fde-scope skill add --title "OPC UA 连接踩坑" --category implementation --tags opcua --body "# 步骤..."
fde-scope skill review                  # 审阅自动捕获/gate 提示产生的草稿队列
fde-scope skill publish <skill-id>      # draft → published（可检索、可导出）
fde-scope skill list --category implementation --tag opcua [--status published]
fde-scope skill show <skill-id>         # 正文 + 元数据
fde-scope skill edit <skill-id>         # 编辑（version+1）
fde-scope skill archive <skill-id>      # 归档
fde-scope skill export <skill-id> --format qwenpaw --out exports/   # 或 --format agentscope
```

## 导出格式（两种，同源）

AgentScope 2.0 与 QwenPaw 都遵循 Anthropic Agent Skills 规范，共用一个渲染器：

```markdown
---
name: opc-ua-连接踩坑
description: OPC UA 连接踩坑
---

（正文 Markdown）
```

- `name` 为标题 slugify（保留 CJK 以避免导出碰撞）
- **AgentScope**：导出目录交给 `Toolkit.register_agent_skill()`
- **QwenPaw**：放入 `customized_skills` 目录自动发现；或经 PawApp 的
  `skill_provider()` 注册（见 [`qwenpaw_integration.md`](qwenpaw_integration.md)）

`fde-scope qwenpaw export` 还可把 tenant 拓扑 + published 技能 + corpus 说明
打包为 QwenPaw 兼容产物（`qwenpaw validate` 校验结构、必填字段与 agent id 规则）。

## Web / Workbench API

```
GET    /api/skills?q=&category=&tag=&status=&profile=&gate=&phase=
POST   /api/skills
GET    /api/skills/drafts
GET    /api/skills/{id}
PATCH  /api/skills/{id}
POST   /api/skills/{id}/publish | /archive | /export
POST   /api/engagements/{eid}/journal/{jid}/skill   # 现场记录一键沉淀
GET    /api/workbench                                # 统计含 draft/total skills
```

工作台（`fde-scope web` → Console）提供技能库视图：检索、草稿审阅队列、
发布/归档、现场记录到技能的一键桥接。

## 模块结构

| 文件 | 职责 |
|---|---|
| `fde_scope/skills/models.py` | SkillDraft / SkillPatch / SkillRecord / 枚举 |
| `fde_scope/skills/store.py` | 文件库读写（`.fde_scope/skills/`） |
| `fde_scope/skills/service.py` | 生命周期（create/publish/archive）+ 检索 |
| `fde_scope/skills/exporters.py` | SKILL.md 渲染（agentscope / qwenpaw） |

测试：`tests/test_skills.py`（26 用例）+ `tests/test_web.py` 中的 skills API 覆盖。

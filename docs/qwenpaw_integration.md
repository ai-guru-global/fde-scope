# QwenPaw 集成指南

> 本文档基于 2026-08-25 对 QwenPaw 官方仓库（github.com/qwen-paw/qwenpaw，main
> 分支）与官方文档站的检索结论编写。字段名与结构对齐官方，不虚构。

## 1. 背景与范围

FDE Scope 通过两种方式与 QwenPaw 协作：

- **产物导出**：把 tenant 的 agent 拓扑、published 技能、corpus 说明导出为
  QwenPaw 可消费的目录树（`fde-scope qwenpaw export`）。
- **ACP 适配**：把 FDE 能力（如 SOP 状态机）暴露为 QwenPaw 的外部 agent
  （`delegate_external_agent` tool），走 Agent Client Protocol（ACP）。

**真实 QwenPaw 实例的对接不在本期**（spec §5.1）：本期交付导出器、校验器与
`AcpEndpoint` 占位基类，不做 QwenPaw 运行时的网络/进程对接。

## 2. QwenPaw 配置两层结构

QwenPaw 使用两层配置：

| 层 | 路径 | 内容 |
| --- | --- | --- |
| 全局 | `~/.qwenpaw/config.json` | `agents.profiles[agent_id]`（多 Agent 声明）+ `active_agent` |
| workspace | `~/.qwenpaw/workspaces/{agent_id}/agent.json` | 单 Agent 详细配置 + persona 引用 |

`config.json` 的 `agents.profiles` 结构（每 profile 必填 `id` / `name` /
`enabled`，可选 `description` / `workspace_dir`）：

```json
{
  "agents": {
    "active_agent": "researcher",
    "profiles": {
      "researcher": { "id": "researcher", "name": "researcher", "description": "调研员", "enabled": true },
      "coder":      { "id": "coder", "name": "coder", "description": "实施员", "enabled": true }
    }
  }
}
```

`agent.json` 的常用字段：`id` / `name` / `description` / `language` /
`system_prompt_files`（persona 文件引用）/ `tools` / `channels` / `security` 等。

**persona**：workspace 内的 `AGENTS.md` / `SOUL.md` / `PROFILE.md`，由
`system_prompt_files` 引用。

**agent id 规则**（官方 `src/qwenpaw/config/config.py`）：
`^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$`（单字符也合法），2-64 字符，
`default` 为保留 id。

## 3. 导出与放置

### 3.1 导出

```bash
fde-scope qwenpaw export \
  --tenant acme --name "Acme" \
  --agent "researcher:调研员" --agent "coder:实施员:qwen-max" \
  --out qwenpaw-out
```

产出（`qwenpaw-out/`）：

```
config.json                        # 全局多 Agent 拓扑（agents.profiles）
workspaces/{agent_id}/agent.json   # 每 Agent 配置（system_prompt_files=["AGENTS.md"]）
workspaces/{agent_id}/AGENTS.md    # persona（spec.system_prompt 或默认文案）
skills/<name>/SKILL.md             # published 技能包（QwenPaw/AgentScope 同源格式）
corpus.json                        # 传 --corpus 时：collection 说明
qwenpaw_validate.json              # 校验报告
```

### 3.2 放置到 QwenPaw

- `config.json` 的 `agents` 段合并进 `~/.qwenpaw/config.json`；
- `workspaces/{agent_id}/` 目录拷贝进 `~/.qwenpaw/workspaces/`；
- `skills/` 目录拷贝进 workspace（或 `skill_pool/`）。

### 3.3 校验

```bash
fde-scope qwenpaw validate --out qwenpaw-out
```

规则（`fde_scope/integrations/validator.py`）：

- `config.json` 存在且 `agents.profiles` 非空；
- 每 profile 必填 `id` / `name` / `enabled`，profile 键 == `id`；
- agent id 匹配官方规则；
- 每 profile 有 `workspaces/{id}/agent.json`，必填 `id` / `name`，
  `system_prompt_files` 指向存在的 persona 文件；
- `skills/` 下每个 `SKILL.md` 含 frontmatter（`name:` / `description:`）。

exit 0 = VALID；exit 1 = INVALID（打印错误列表）。

## 4. ACP 适配（占位）

QwenPaw 的 ACP 有两种模式：

1. **QwenPaw 作为 client / orchestrator**：内置 `delegate_external_agent`
   tool，连接外部 ACP runner（如 opencode / qwen_code / claude_code / codex），
   经 **stdio 子进程协议**通信。runner 配置字段：
   `enabled` / `command` / `args` / `env` / `trusted` / `tool_parse_mode` /
   `stdio_buffer_limit_bytes`。
2. **QwenPaw 作为 ACP server**：QwenPaw 自己暴露 ACP 端点。

FDE 侧接入步骤（本期只交付第 1 步）：

1. 实现 `fde_scope.integrations.acp.AcpEndpoint` 子类（声明 `name` /
   `description` / `acp_command` / `acp_env`，实现 `handle()`）；
2. 调用 `runner_config()` 得到 QwenPaw 的 ACP runner 配置；
3. 把配置填入 QwenPaw Workspace → ACP 页面（或 runner 配置文件），启用
   `delegate_external_agent` tool。

stdio 协议实现、真实 runner 对接不在本期（spec §5.2 占位条款）。

## 5. PawApp 插件（pawapp/）

`pawapp/` 是一个可安装进 QwenPaw App Center 的完整 PawApp（`plugin.json`
声明 + `backend/main.py` FastAPI router + `ui/index.js` React 页面），把 FDE
引擎以 `/api/fde-scope/*` 路由与两个 agent tools（`fde_sop_status` /
`fde_sop_advance`）暴露给宿主 QwenPaw。安装：把 `pawapp/` 拷贝进 QwenPaw
插件目录即可（`qwenpaw plugin install ./pawapp`）。详见 `pawapp/README.md`。

**已实现能力（路线图 10/10）**：

| 能力 | 实现 |
|---|---|
| SOP 全生命周期 | 17 路由：engagement CRUD / 18 阶段 / gate 实时校验 / 推进拦截 |
| 语料锻造 / KPI / 技能库 | forge（LLM 合成自动感知 MIMO key）、双 profile KPI、草稿审阅+发布 |
| handoff + runbook | `ctx.chat()` 宿主 LLM 起草（失败回退模板，`used_llm` 如实标注）——不再需要外部 LLM key |
| 技能即能力 | 导出的 SKILL.md 写盘到 `.fde_scope/skills/export/`，经 `skill_provider()` 注册给宿主 Agent |
| Agent 可查状态 | `ctx.storage` 同步 engagement 快照（`engagements_index`，文件仍为唯一事实源） |
| 前端 | 5 Tab 工作台：SOP 流水线 / 语料锻造 / KPI / 技能库 / 交接 |

**版本兼容**：PyPI 2.1.0 版 PawApp SDK 无 `skill_provider()`（GitHub main
分支才有），代码用 `hasattr` 探测降级：新宿主自动注册，2.1.0 上导出文件留在
磁盘供手动发现。

**验证**：真实 QwenPaw 2.1.0 `PluginLoader` 管线加载通过（manifest 解析 →
模块加载 → `register(PluginApi)` → 17 路由挂载 + 工具注册），全部路由 HTTP
冒烟 200。自动化回归：`tests/test_pawapp.py`（stub `qwenpaw.pawapp` SDK，
无需安装 QwenPaw）。

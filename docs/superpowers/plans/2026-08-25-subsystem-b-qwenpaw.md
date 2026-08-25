# 子系统 B（QwenPaw 集成）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 FDE Scope 的产物（tenant agent 拓扑、corpus 说明、published 技能）导出为 QwenPaw 可消费的形态（`config.json` 多 Agent profiles + `agent.json` + persona + skills 包），提供校验器与 ACP 适配占位接口，并输出集成文档。

**Architecture:** 新增 `fde_scope/integrations/` 包：`qwenpaw_exporter.py`（`QwenPawExporter.export(tenant, out_dir, skills, corpus) -> ExportBundle`，字段对齐 QwenPaw 官方 `config.json`/`agent.json` schema，persona 落为 `AGENTS.md`，技能包复用 `skills/exporters.py` 的 qwenpaw 格式）、`validator.py`（`validate_export(out_dir) -> ValidationReport`，结构 + 必填字段 + agent id 规则校验）、`acp.py`（`AcpEndpoint` 基类占位 + 文档化 QwenPaw ACP 真实形态）。CLI 加 `qwenpaw export` / `qwenpaw validate` 子命令组。**真实 QwenPaw 实例对接不在本期**（spec §5.1，依赖外部产品环境），交付导出器 + 校验器 + 集成文档。

**Tech Stack:** Python 3.11+ / Pydantic v2 / Typer / pytest / ruff+mypy（CI 门禁）。零新增运行时依赖（不 import qwenpaw 包）。

## Global Constraints

- 零新增运行时依赖；`qwenpaw` 包保持不 import（导出器只产出文件，不做实例对接）。
- 真实 QwenPaw 字段以检索结论为准（见 Task 0），**不虚构不存在的字段**；`except` 内 `raise` 必须 `from None`（B904）。
- 测试先失败再实现（TDD）；每个 task 结束全量测试通过后 commit。
- ruff 规则集 E/W/F/I/C4/B/SIM/UP、line-length 110；ruff format 与 mypy 是 CI 门禁。
- 向后兼容：不修改子系统 A 的 `TenantConfig`/`AgentSpec` 已有字段；`pawapp/` 目录（未跟踪草稿，含 bug）不在本期范围，不修改不 commit。

---

### Task 0: QwenPaw 官方形态检索结论（实现依据，无需代码）

检索来源（2026-08-25）：QwenPaw GitHub `agentscope-ai/QwenPaw` main 分支 `website/public/docs/config.en.md`（官方配置文档源码）、`website/public/docs/acp-integration.en.md`（官方 ACP 集成文档）、`src/qwenpaw/config/config.py`（ACPConfig 模型）：

- **两层配置**：`~/.qwenpaw/config.json`（全局）+ `~/.qwenpaw/workspaces/{agent_id}/agent.json`（每 agent）。
- **多 Agent 拓扑声明**（config.json 的 `agents` 段，v0.1.0+ 多 agent 支持）：
  ```json
  {"agents": {"active_agent": "default", "profiles": {"default": {"id": "default", "name": "Default Agent", "description": "...", "enabled": true}}}}
  ```
  `agents.profiles[agent_id]` 字段：`id`（必填）、`name`（必填）、`description`（可选，多 Agent 协作用）、`enabled`（必填）、`workspace_dir`（可选）。
- **agent.json**（workspace 内）：`id`/`name`/`description`/`workspace_dir`/`channels`/`mcp`/`heartbeat`/`mail`/`running`/`active_model`/`language`/`system_prompt_files`（persona 文件列表，如 `["AGENTS.md", "SOUL.md"]`）/`tools`/`security`。persona 即 workspace 内的 `AGENTS.md`/`SOUL.md`/`PROFILE.md`。
- **技能**：workspace 内 `skills/` 目录 + `skill.json`（enabled 状态）；全局 `skill_pool/`。SKILL.md 机制与 AgentScope 同源（子系统 C 的 `exporters.py` 已实现 qwenpaw 格式）。
- **ACP（Agent Client Protocol）两种模式**（QwenPaw 官方）：
  1. QwenPaw 作为 **client/orchestrator**：内置 `delegate_external_agent` tool 连接外部 ACP runner（opencode/qwen_code/claude_code/codex 或自定义），runner 配置字段 = `enabled`/`command`/`args`/`env`/`trusted`/`tool_parse_mode`/`stdio_buffer_limit_bytes`（stdio 子进程协议，command+args 启动外部 agent 的 ACP 模式）；
  2. QwenPaw 作为 **ACP server**：外部客户端连 QwenPaw。
- **Agent ID 规则**（config.py 源码）：`^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$`，2-64 字符，`default` 保留。

**因此本计划落地**：导出器输出 `config.json`（agents.profiles 段）+ `workspaces/{agent_id}/agent.json` + `AGENTS.md` persona + `skills/` 包 + `corpus.json` 说明 + 校验报告；校验器按上述规则校验；`acp.py` 占位 `AcpEndpoint` 基类（docstring 记录 ACP 真实形态与接入方式）；集成文档说明导出产物如何放入 `~/.qwenpaw/` 与 SOP 引擎如何作为 ACP runner 接入。

---

### Task 1: integrations 包 + AcpEndpoint 占位

**Files:**
- Create: `fde_scope/integrations/__init__.py`
- Create: `fde_scope/integrations/acp.py`
- Test: `tests/test_integrations.py`（新建）

**Interfaces:**
- Produces: `fde_scope.integrations.acp.AcpEndpoint`（抽象基类：`name: str`、`description: str`、`acp_command: list[str]`、`acp_env: dict[str, str]`、`async def handle(self, payload: dict) -> dict`（NotImplementedError）、`def runner_config(self) -> dict`（返回 QwenPaw ACP 配置段：`{"enabled": True, "command": ..., "args": ..., "env": ..., "trusted": True, "tool_parse_mode": "call_title"}`））。Task 5 文档依赖其字段名。

- [x] **Step 1: 写失败测试**（新建 `tests/test_integrations.py`）

```python
"""Tests for the QwenPaw integration surface (spec §5.2 ACP placeholder)."""

from __future__ import annotations

import pytest

from fde_scope.integrations.acp import AcpEndpoint


def test_acp_endpoint_is_abstract() -> None:
    with pytest.raises(TypeError):
        AcpEndpoint()  # type: ignore[abstract]


def test_acp_endpoint_runner_config_matches_qwenpaw_fields() -> None:
    class SopEngine(AcpEndpoint):
        name = "fde_sop"
        description = "FDE SOP state machine"
        acp_command = ["python", "-m", "fde_scope.acp_server"]
        acp_env = {"FDE_SCOPE_TENANT": "acme"}

        async def handle(self, payload: dict) -> dict:
            return {"ok": True}

    ep = SopEngine()
    cfg = ep.runner_config()
    # 字段名对齐 QwenPaw ACPConfig.ACPAgentConfig（官方源码 config.py）
    assert cfg["enabled"] is True
    assert cfg["command"] == "python"
    assert cfg["args"] == ["-m", "fde_scope.acp_server"]
    assert cfg["env"] == {"FDE_SCOPE_TENANT": "acme"}
    assert cfg["trusted"] is True
    assert cfg["tool_parse_mode"] == "call_title"
```

- [x] **Step 2: 运行确认失败**

Run: `pytest tests/test_integrations.py -q`
Expected: FAIL（`ModuleNotFoundError: fde_scope.integrations`）

- [x] **Step 3: 最小实现**

`fde_scope/integrations/__init__.py`（空 docstring 文件）：

```python
"""QwenPaw / ACP integration surface (spec §5.2)."""
```

`fde_scope/integrations/acp.py`：

```python
"""ACP (Agent Client Protocol) adaptation placeholder.

QwenPaw 官方 ACP 形态（2026-08-25 检索，见 docs/qwenpaw_integration.md）：
两种模式——QwenPaw 作为 client/orchestrator（内置 ``delegate_external_agent``
tool 连接外部 ACP runner）与 QwenPaw 作为 ACP server。外部 runner 配置字段
（QwenPaw ``ACPAgentConfig``）：``enabled`` / ``command`` / ``args`` / ``env`` /
``trusted`` / ``tool_parse_mode`` / ``stdio_buffer_limit_bytes``，经 stdio
子进程协议通信。

本期（spec §5.2）只提供占位基类：FDE SOP 引擎作为 ACP runner 时实现
:class:`AcpEndpoint`，``runner_config()`` 的输出可直接填入 QwenPaw 的
Workspace → ACP 配置。网络协议实现不在本期。
"""

from __future__ import annotations

import abc
from typing import Any


class AcpEndpoint(abc.ABC):
    """Base class for exposing an FDE capability as a QwenPaw ACP runner.

    Subclasses declare the runner metadata; ``runner_config()`` emits the
    exact ``ACPAgentConfig`` fields QwenPaw expects.
    """

    name: str = ""
    description: str = ""
    acp_command: list[str] = []
    acp_env: dict[str, str] = {}

    @abc.abstractmethod
    async def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle one ACP task payload. Not implemented in this phase."""
        raise NotImplementedError

    def runner_config(self) -> dict[str, Any]:
        """QwenPaw ACP runner config (Workspace → ACP page fields)."""
        command, *args = self.acp_command
        return {
            "enabled": True,
            "command": command,
            "args": args,
            "env": self.acp_env,
            "trusted": True,
            "tool_parse_mode": "call_title",
        }
```

- [x] **Step 4: 运行确认通过**

Run: `pytest tests/test_integrations.py -q`
Expected: PASS

- [x] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/integrations/ tests/test_integrations.py && git commit -m "feat(integrations): AcpEndpoint placeholder for QwenPaw ACP"
```

---

### Task 2: QwenPawExporter（agent 拓扑 + corpus 说明 + 技能包）

**Files:**
- Create: `fde_scope/integrations/qwenpaw_exporter.py`
- Modify: `fde_scope/skills/__init__.py`（若需导出 `SkillStore` 便捷入口则不动；exporter 直接 import `fde_scope.skills.exporters.export_many`）
- Test: `tests/test_integrations.py`（追加）

**Interfaces:**
- Consumes: Task 1 的包结构；子系统 A 的 `AgentSpec`/`TenantConfig`；子系统 C 的 `SkillRecord`/`export_many`。
- Produces: `QwenPawExporter.export(tenant: TenantConfig, out_dir: Path, skills: list[SkillRecord] | None = None, corpus_report: CorpusReport | None = None) -> ExportBundle`；`ExportBundle`（dataclass：`out_dir: Path`、`written: list[str]`（相对路径）、`report: dict`（校验信息））。导出布局：
  - `config.json`：`{"agents": {"active_agent": <首个 agent id>, "profiles": {<agent_id>: {"id", "name", "description", "enabled": True}}}}`
  - `workspaces/{agent_id}/agent.json`：`{"id", "name", "description", "language": "en", "system_prompt_files": ["AGENTS.md"]}`
  - `workspaces/{agent_id}/AGENTS.md`：`# {name}\n\n{system_prompt or 默认}`（默认文案含 role 与 tenant）
  - `skills/<name>/SKILL.md`：published 技能批量导出（qwenpaw 格式，复用 `export_many`）
  - `corpus.json`（有 corpus_report 时）：`{"collection": "corpus_{tenant.id}", "total", "real", "synthetic"}`
  - `qwenpaw_validate.json`：校验报告（复用 Task 3 的 `validate_export`，Task 2 先写内联基础版，Task 3 替换为正式实现）
  - agent_id 由 `spec.name` 归一化（合法字符否则 `-`，非法则抛 `ValueError`）。Task 3/4 依赖 `ExportBundle` 与布局。

- [x] **Step 1: 写失败测试**（追加到 `tests/test_integrations.py`）

```python
def test_qwenpaw_export_writes_full_bundle(tmp_path) -> None:
    from fde_scope.config import TenantConfig
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter

    tenant = TenantConfig(
        id="acme",
        name="Acme",
        agents=[
            {"name": "researcher", "role": "调研员"},
            {"name": "coder", "role": "实施员", "system_prompt": "You code."},
        ],
    )
    ex = QwenPawExporter()
    bundle = ex.export(tenant, tmp_path)
    assert (tmp_path / "config.json").exists()
    assert (tmp_path / "workspaces" / "researcher" / "agent.json").exists()
    assert (tmp_path / "workspaces" / "coder" / "AGENTS.md").exists()
    assert "You code." in (tmp_path / "workspaces" / "coder" / "AGENTS.md").read_text(encoding="utf-8")
    # config.json 的 profiles 段对齐 QwenPaw 官方结构
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    profiles = cfg["agents"]["profiles"]
    assert set(profiles) == {"researcher", "coder"}
    assert profiles["researcher"]["enabled"] is True
    assert cfg["agents"]["active_agent"] == "researcher"
    # agent.json 必填字段 + persona 引用
    aj = json.loads((tmp_path / "workspaces" / "coder" / "agent.json").read_text(encoding="utf-8"))
    assert aj["name"] == "coder"
    assert aj["system_prompt_files"] == ["AGENTS.md"]
    # 校验报告写出
    assert (tmp_path / "qwenpaw_validate.json").exists()
    assert bundle.report["valid"] is True


def test_qwenpaw_export_includes_skills_and_corpus(tmp_path) -> None:
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter
    from fde_scope.skills.models import SkillRecord

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    skills = [
        SkillRecord(
            id="sk-1",
            title="现场调研清单",
            category="research",
            body_md="## Checklist\n1. 首件确认",
            source="manual",
            status="published",
            version=1,
        )
    ]
    ex = QwenPawExporter()
    ex.export(tenant, tmp_path, skills=skills)
    skill_md = tmp_path / "skills" / "现场调研清单" / "SKILL.md"
    assert skill_md.exists()
    assert "## Checklist" in skill_md.read_text(encoding="utf-8")
```

- [x] **Step 2: 运行确认失败**

Run: `pytest tests/test_integrations.py -q`
Expected: FAIL（`ModuleNotFoundError: fde_scope.integrations.qwenpaw_exporter`）

- [x] **Step 3: 最小实现**

`fde_scope/integrations/qwenpaw_exporter.py`：

```python
"""QwenPaw 导出器：FDE 产物 → QwenPaw 可消费形态（spec §5.2）。

字段对齐官方（2026-08-25 检索）：
- ``config.json`` 的 ``agents.profiles[agent_id]``：id/name/description/enabled
  （必填 id+name+enabled；description 用于多 Agent 协作）；
- workspace 内 ``agent.json``：id/name/description/language/system_prompt_files；
- persona 即 workspace 内 AGENTS.md（system_prompt_files 引用）；
- 技能 = workspace ``skills/`` 目录（SKILL.md，与 AgentScope 同源）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from fde_scope.config import AgentSpec, TenantConfig


def _agent_id(name: str) -> str:
    """归一化为 QwenPaw 合法 agent id（^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$）。"""
    s = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]|[a-zA-Z0-9]", s):
        raise ValueError(f"agent name {name!r} cannot form a valid agent id")
    return s


@dataclass
class ExportBundle:
    """一次导出的产物句柄。"""

    out_dir: Path
    written: list[str] = field(default_factory=list)
    report: dict = field(default_factory=dict)


class QwenPawExporter:
    """把 tenant 拓扑 / 技能 / corpus 导出为 QwenPaw 兼容目录树。"""

    def export(
        self,
        tenant: TenantConfig,
        out_dir: Path,
        skills: list | None = None,
        corpus_report=None,
    ) -> ExportBundle:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        specs = tenant.agents or [AgentSpec(name=f"{tenant.name}_agent", role=tenant.name)]
        ids = [_agent_id(s.name) for s in specs]
        bundle = ExportBundle(out_dir=out)

        # config.json — 全局多 Agent 拓扑（官方 agents.profiles 结构）
        cfg = {
            "agents": {
                "active_agent": ids[0],
                "profiles": {
                    aid: {
                        "id": aid,
                        "name": s.name,
                        "description": s.role,
                        "enabled": True,
                    }
                    for aid, s in zip(ids, specs)
                },
            }
        }
        self._write(out / "config.json", cfg, bundle)

        # workspaces/{agent_id}/ — 每 agent 配置 + persona
        for aid, s in zip(ids, specs):
            ws = out / "workspaces" / aid
            self._write(
                ws / "agent.json",
                {
                    "id": aid,
                    "name": s.name,
                    "description": s.role,
                    "language": "en",
                    "system_prompt_files": ["AGENTS.md"],
                },
                bundle,
            )
            prompt = s.system_prompt or (
                f"You are the {s.role} for {tenant.name} (tenant={tenant.id}). "
                "Answer customer tickets using only the tenant corpus. "
                "Never access other tenants' data."
            )
            (ws / "AGENTS.md").write_text(f"# {s.name}\n\n{prompt}\n", encoding="utf-8")
            bundle.written.append(f"workspaces/{aid}/AGENTS.md")

        # skills/ — published 技能包（qwenpaw 格式）
        if skills:
            from fde_scope.skills.exporters import export_many

            for f in export_many(skills, "qwenpaw"):
                p = out / "skills" / f.name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f.content, encoding="utf-8")
                bundle.written.append(f"skills/{f.name}")

        # corpus.json — collection 说明
        if corpus_report is not None:
            self._write(
                out / "corpus.json",
                {
                    "collection": f"corpus_{tenant.id}",
                    "total": corpus_report.total,
                    "real": corpus_report.real,
                    "synthetic": corpus_report.synthetic,
                },
                bundle,
            )

        # 校验报告（Task 3 起复用正式校验器）
        from .validator import validate_export

        bundle.report = validate_export(out)
        self._write(out / "qwenpaw_validate.json", bundle.report, bundle)
        return bundle

    @staticmethod
    def _write(path: Path, data: dict, bundle: ExportBundle) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        bundle.written.append(str(path.relative_to(bundle.out_dir)))
```

- [x] **Step 4: 运行确认通过**

Run: `pytest tests/test_integrations.py -q`
Expected: PASS（注：`validate_export` 尚不存在，Task 2 Step 3 的 import 会失败——先在同一 Step 内于 `validator.py` 放最小版 `validate_export`，Task 3 再增强）

```python
# fde_scope/integrations/validator.py（Task 2 最小版，Task 3 增强）
def validate_export(out_dir: Path) -> dict:
    return {"valid": True, "errors": []}
```

- [x] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/integrations/ tests/test_integrations.py && git commit -m "feat(integrations): QwenPaw exporter for agent topology + skills"
```

---

### Task 3: 校验器（结构 + 必填字段 + agent id 规则）

**Files:**
- Modify: `fde_scope/integrations/validator.py`（替换 Task 2 最小版）
- Test: `tests/test_integrations.py`（追加）

**Interfaces:**
- Consumes: Task 2 的导出布局。
- Produces: `validate_export(out_dir: Path) -> dict`（`{"valid": bool, "errors": list[str]}`）。规则：`config.json` 存在且 `agents.profiles` 非空、每 profile 必填 `id`/`name`/`enabled`、profile 键 == profile.id；每个 profile 对应 `workspaces/{id}/agent.json` 存在、agent.json 必填 `id`/`name` 且 `system_prompt_files` 指向存在的文件；agent id 匹配官方规则 `^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$`（或单字符）；`skills/` 下每个 SKILL.md 有 `---` frontmatter 且含 `name:`/`description:`。Task 4 的 CLI 依赖。

- [x] **Step 1: 写失败测试**（追加到 `tests/test_integrations.py`）

```python
def test_validate_export_rejects_missing_id(tmp_path) -> None:
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter
    from fde_scope.integrations.validator import validate_export

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    QwenPawExporter().export(tenant, tmp_path)
    # 篡改：删掉 profile 的 name → 校验必须报错
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    del cfg["agents"]["profiles"]["a1"]["name"]
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False
    assert any("name" in e for e in report["errors"])


def test_validate_export_rejects_bad_agent_id(tmp_path) -> None:
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter
    from fde_scope.integrations.validator import validate_export

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    QwenPawExporter().export(tenant, tmp_path)
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    cfg["agents"]["profiles"]["bad id!"] = dict(cfg["agents"]["profiles"]["a1"], id="bad id!")
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False


def test_validate_export_rejects_missing_skill_frontmatter(tmp_path) -> None:
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter
    from fde_scope.integrations.validator import validate_export
    from fde_scope.skills.models import SkillRecord

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    skills = [
        SkillRecord(
            id="sk-1",
            title="技巧",
            category="research",
            body_md="body",
            source="manual",
            status="published",
            version=1,
        )
    ]
    QwenPawExporter().export(tenant, tmp_path, skills=skills)
    (tmp_path / "skills" / "技巧" / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False
```

- [x] **Step 2: 运行确认失败**

Run: `pytest tests/test_integrations.py -q`
Expected: FAIL（最小版 validate_export 恒返回 valid=True）

- [x] **Step 3: 最小实现**（重写 `fde_scope/integrations/validator.py`）

```python
"""QwenPaw 导出产物校验器（spec §5.2）。

校验规则对齐官方形态（2026-08-25 检索）：config.json 的 agents.profiles
必填 id/name/enabled 且键 == id；每 profile 有 workspaces/{id}/agent.json
（必填 id/name，system_prompt_files 指向存在的 persona 文件）；agent id
匹配官方规则；skills/ 下 SKILL.md 含 frontmatter（name/description）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_AGENT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$")


def validate_export(out_dir: Path) -> dict:
    """结构 + 必填字段 + agent id 规则校验；返回 {"valid", "errors"}。"""
    errors: list[str] = []
    out = Path(out_dir)

    cfg_path = out / "config.json"
    if not cfg_path.exists():
        return {"valid": False, "errors": ["config.json missing"]}
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return {"valid": False, "errors": [f"config.json invalid JSON: {exc}"]}
    profiles = (cfg.get("agents") or {}).get("profiles") or {}
    if not profiles:
        errors.append("agents.profiles empty")
    for key, p in profiles.items():
        for required in ("id", "name", "enabled"):
            if required not in p:
                errors.append(f"profile {key!r} missing field {required!r}")
        if p.get("id") != key:
            errors.append(f"profile key {key!r} != id {p.get('id')!r}")
        aid = str(p.get("id", ""))
        if not _AGENT_ID_RE.fullmatch(aid):
            errors.append(f"agent id {aid!r} violates QwenPaw id rules")
        ws = out / "workspaces" / aid / "agent.json"
        if not ws.exists():
            errors.append(f"workspaces/{aid}/agent.json missing")
            continue
        try:
            aj = json.loads(ws.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"workspaces/{aid}/agent.json invalid JSON: {exc}")
            continue
        for required in ("id", "name"):
            if required not in aj:
                errors.append(f"agent.json {aid!r} missing field {required!r}")
        for persona in aj.get("system_prompt_files") or []:
            if not (out / "workspaces" / aid / persona).exists():
                errors.append(f"persona {persona!r} missing for agent {aid!r}")

    skills_dir = out / "skills"
    if skills_dir.exists():
        for skill_md in skills_dir.glob("*/SKILL.md"):
            text = skill_md.read_text(encoding="utf-8")
            if not text.startswith("---\n") or "name:" not in text or "description:" not in text:
                errors.append(f"skill {skill_md.parent.name!r} SKILL.md lacks frontmatter")

    return {"valid": not errors, "errors": errors}
```

- [x] **Step 4: 运行确认通过**

Run: `pytest tests/test_integrations.py -q`
Expected: PASS（含 Task 2 两个测试——export 的 bundle.report 现在走正式校验器）

- [x] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/integrations/validator.py tests/test_integrations.py && git commit -m "feat(integrations): QwenPaw export validator with id rules"
```

---

### Task 4: CLI `qwenpaw export` / `qwenpaw validate`

**Files:**
- Modify: `fde_scope/cli.py`
- Test: `tests/test_cli.py`（追加）

**Interfaces:**
- Consumes: Task 2/3 的 `QwenPawExporter`/`validate_export`；子系统 A 的 `AgentSpec`。
- Produces: CLI `qwenpaw export --tenant <id> --name <name> --agent "name:role[:model]"（可重复） --skills <published 技能导出> --out <dir>`；`qwenpaw validate --out <dir>`（exit 0 valid / exit 1 invalid + 错误列表）。Task 5 的 README 依赖。

- [x] **Step 1: 写失败测试**（追加到 `tests/test_cli.py` 末尾）

```python
def test_qwenpaw_export_and_validate(tmp_path: Path, monkeypatch) -> None:
    """qwenpaw export 产出可被 qwenpaw validate 验证通过。"""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    r = runner.invoke(
        app,
        [
            "qwenpaw",
            "export",
            "--tenant",
            "acme",
            "--name",
            "Acme",
            "--out",
            str(out),
            "--agent",
            "researcher:调研员",
            "--agent",
            "coder:实施员:qwen-max",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert (out / "config.json").exists()
    assert '"profiles"' in (out / "config.json").read_text(encoding="utf-8")
    r2 = runner.invoke(app, ["qwenpaw", "validate", "--out", str(out)])
    assert r2.exit_code == 0, r2.stdout
    assert "VALID" in r2.stdout


def test_qwenpaw_validate_reports_bad_bundle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "config.json").write_text('{"agents": {"profiles": {}}}', encoding="utf-8")
    r = runner.invoke(app, ["qwenpaw", "validate", "--out", str(out)])
    assert r.exit_code == 1
    assert "profiles" in r.stdout
```

- [x] **Step 2: 运行确认失败**

Run: `pytest tests/test_cli.py::test_qwenpaw_export_and_validate tests/test_cli.py::test_qwenpaw_validate_reports_bad_bundle -v`
Expected: FAIL（`No such command 'qwenpaw'`）

- [x] **Step 3: 最小实现**（`fde_scope/cli.py`）

在 `skill_app` 定义后新增：

```python
qwenpaw_app = typer.Typer(
    name="qwenpaw", help="[QwenPaw] 导出 / 校验 QwenPaw 兼容产物.", no_args_is_help=True
)
app.add_typer(qwenpaw_app)


@qwenpaw_app.command("export")
def qwenpaw_export(
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant ID"),
    name: str = typer.Option("Tenant", "--name", help="Tenant display name"),
    model: str = typer.Option("qwen-max", "--model", "-m", help="Model config name"),
    agent_specs: list[str] | None = typer.Option(
        None, "--agent", "-a", help="Agent spec 'name:role[:model]' (repeatable)"
    ),
    out: str = typer.Option(..., "--out", help="Output directory"),
    corpus: str | None = typer.Option(None, "--corpus", help="Path to forged corpus JSON (optional)"),
) -> None:
    """[QwenPaw] 导出 tenant 拓扑 + published 技能 + corpus 说明为 QwenPaw 兼容产物."""
    _banner(f"qwenpaw export · {tenant}")
    from .config import AgentSpec, TenantConfig
    from .integrations.qwenpaw_exporter import QwenPawExporter
    from .skills.service import SkillService
    from .skills.store import SkillStore

    agents = []
    for a in agent_specs or []:
        parts = a.split(":")
        if len(parts) == 2:
            agent_name, agent_role, agent_model = parts[0], parts[1], None
        elif len(parts) == 3:
            agent_name, agent_role, agent_model = parts
        else:
            console.print(f"[red]Invalid agent spec:[/red] {a} (expected name:role[:model])")
            raise typer.Exit(2)
        agents.append(AgentSpec(name=agent_name, role=agent_role, model=agent_model))
    cfg = TenantConfig(id=tenant, name=name, model=model, agents=agents or None)

    corpus_report = None
    if corpus:
        from .corpus import CorpusReport

        try:
            corpus_report = CorpusReport.model_validate_json(Path(corpus).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            console.print(f"[red]Cannot load corpus report:[/red] {corpus} ({exc})")
            raise typer.Exit(2) from exc

    skills = SkillService(SkillStore(Path(".fde_scope/skills"))).search(status="published")
    bundle = QwenPawExporter().export(cfg, Path(out), skills=skills, corpus_report=corpus_report)
    for w in bundle.written:
        console.print(f"📦 {w}")
    if bundle.report["valid"]:
        console.print(f"✅ Exported {len(bundle.written)} files → [green]{out}[/green]")
    else:
        console.print("[yellow]⚠ export contains validation errors (see qwenpaw_validate.json)[/yellow]")
    console.print(f"📋 Manifest → [green]{json.dumps(bundle.report, ensure_ascii=False)}[/green]")


@qwenpaw_app.command("validate")
def qwenpaw_validate(
    out: str = typer.Option(..., "--out", help="Export directory to validate"),
) -> None:
    """[QwenPaw] 校验导出产物（结构 + 必填字段 + agent id 规则）。"""
    _banner(f"qwenpaw validate · {out}")
    from .integrations.validator import validate_export

    report = validate_export(Path(out))
    if report["valid"]:
        console.print("✅ [green]VALID[/green] — QwenPaw-compatible bundle")
    else:
        for e in report["errors"]:
            console.print(f"[red]✗[/red] {e}")
        console.print(f"❌ [red]INVALID[/red] — {len(report['errors'])} error(s)")
        raise typer.Exit(1)
```

注意：`SkillStore`/`SkillService` 的构造与 `_skill_service()`（engage 命令用）一致——直接复用 `_skill_service()` 更稳（它已在文件内定义，含 store 路径约定）。

- [x] **Step 4: 运行确认通过**

Run: `pytest tests/test_cli.py::test_qwenpaw_export_and_validate tests/test_cli.py::test_qwenpaw_validate_reports_bad_bundle -q`
Expected: PASS

- [x] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/cli.py tests/test_cli.py && git commit -m "feat(cli): qwenpaw export and validate commands"
```

---

### Task 5: 收尾（集成文档 + README + 门禁）

**Files:**
- Create: `docs/qwenpaw_integration.md`
- Modify: `README.md`

- [x] **Step 1: 写集成文档** `docs/qwenpaw_integration.md`

内容（基于 Task 0 检索结论，不虚构）：
1. QwenPaw 配置两层结构（`~/.qwenpaw/config.json` + `workspaces/{agent_id}/agent.json`）与多 Agent profiles 结构；
2. 导出产物放置说明：`config.json` 合并进 `~/.qwenpaw/config.json` 的 `agents` 段；`workspaces/{agent_id}/` 目录拷贝进 `~/.qwenpaw/workspaces/`；`skills/` 拷贝进 workspace 或 `skill_pool/`；
3. ACP 两种模式（client/orchestrator + server）+ FDE SOP 引擎作为 ACP runner 的接入步骤：实现 `fde_scope.integrations.acp.AcpEndpoint` → `runner_config()` 填入 QwenPaw Workspace → ACP 配置（enabled/command/args/env/trusted/tool_parse_mode）→ 启用 `delegate_external_agent` tool；
4. 校验器用法与规则；
5. 明确"真实 QwenPaw 实例对接不在本期"（spec §5.1）。

- [x] **Step 2: README 更新**

1. CLI reference 增补行：`qwenpaw  [QwenPaw] Export / validate QwenPaw-compatible bundles (agents + skills + corpus)`
2. 新增小节（放 "🤖 多 Agent 拓扑" 后）：

```markdown
## 🐾 QwenPaw 集成

`fde-scope qwenpaw export --tenant acme --agent "researcher:调研员" --out qwenpaw-out`
把 tenant 的 agent 拓扑导出为 QwenPaw 兼容产物（`config.json` 的 `agents.profiles`
多 Agent 声明 + `workspaces/{agent_id}/agent.json` + `AGENTS.md` persona +
published 技能包 + corpus 说明），`qwenpaw validate --out ...` 按官方规则校验
（必填字段 / agent id 规则 / SKILL.md frontmatter）。ACP 适配：`AcpEndpoint`
基类把 FDE 能力暴露为 QwenPaw ACP runner（`delegate_external_agent`）。
详见 [`docs/qwenpaw_integration.md`](docs/qwenpaw_integration.md)。
```

- [x] **Step 3: 全量门禁**

```bash
ruff check fde_scope tests && ruff format --check fde_scope tests && mypy fde_scope && pytest -q
```

Expected: 全部通过。若有格式问题：`ruff check --fix fde_scope tests && ruff format fde_scope tests` 后重跑。

- [x] **Step 4: 提交**

```bash
git add docs/qwenpaw_integration.md README.md && git commit -m "docs: QwenPaw integration guide"
```

---

## 计划自审记录

- spec §5.2 覆盖：Agent 配置导出（Task 2）、corpus 说明（Task 2）、技能包批量导出（Task 2，复用子系统 C 的 qwenpaw 格式导出器）、校验报告（Task 2/3）、ACP 文档 + `acp.py` 占位（Task 1/5）、CLI export/validate（Task 4）。
- 求真原则：Task 0 检索记录写入计划；导出字段名全部对齐官方（config.json agents.profiles 的 id/name/description/enabled、agent.json 的 system_prompt_files、ACP 的 enabled/command/args/env/trusted/tool_parse_mode）；不虚构字段。
- 类型一致性：`runner_config()` 字段名（Task 1 定义）与集成文档 ACP 段（Task 5）一致；`validate_export` 返回 `{"valid", "errors"}`（Task 3 定义）被 Task 2 的 export 与 Task 4 的 CLI 消费；导出布局（Task 2 定义）被 Task 3 校验器与 Task 4 CLI 断言使用。
- 向后兼容：不修改子系统 A 已有字段；`pawapp/` 草稿目录（未跟踪、含 bug、不在 spec 范围）不修改不 commit，README 不提及。
- 已知偏差（YAGNI）：不实现真实 QwenPaw 对接（spec §5.1 明确不在本期）；ACP 只提供占位基类不实现 stdio 协议；`--agent` 解析与 deploy 命令一致（复用模式而非抽取公共函数）。

## 执行修正记录

- B-T2 Step 1：技能目录名断言原计划写死中文路径（`skills/现场调研清单/SKILL.md`），但 `exporters._slugify` 对中文标题会退化为 `skill`——改为 glob 断言结构与内容，不绑定 slugify 内部行为。
- B-T2 Step 1：第二个导出测试漏 import `TenantConfig`（NameError）——补 import。
- B-T2 实现：`corpus_report` 与 `skills` 参数显式类型标注（`CorpusReport | None` / `list[SkillRecord] | None`），满足 mypy `no_implicit_optional`。
- B-T3 Step 1：frontmatter 篡改测试同样写死中文路径——改为 glob 定位实际 SKILL.md 后再篡改。
- B-T4 Step 3：`_skill_service().search(status="published")` 触发 mypy `arg-type` 错误（`search` 收 `SkillStatus | None`）——改为 `SkillStatus("published")`。
- 已知：中文技能标题经 `_slugify` 全部退化为 `skill`，多中文技能会互相覆盖——E2E 演练实锤后已修复（`exporters._slugify` 保留 CJK，commit 03a4673），并同步更新 `test_export_agentscope_format` / `test_skill_add_publish_export` 断言。

# 子系统 A（AgentScope 2.0 真实部署运行时）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `fde-scope deploy` 支持一个 tenant 声明多个 Agent（多 Agent 拓扑），真实组装每个 Agent（模型 wiring），manifest 携带完整 `agents` 段与 SubAgentTemplate 蓝图；生命周期 `stop()` 按 2.0 实际 API 适配。

**Architecture:** `TenantConfig.agents: list[AgentSpec] | None`（缺省沿用单 Agent）；`TenantDeployer` 循环组装多个 `agentscope.agent.Agent`（model 从 `spec.model` wiring，缺失留 `None` 运行时注入）；多 Agent 交互层用 2.0 官方 `SubAgentTemplate` 蓝图导出（`agentscope.app.create_app` 的 `custom_subagent_templates` 参数），不启动真实 app 服务（依赖 Redis 等存储/消息总线，超出单机 FDE 范围，不虚构 API，见 spec §4.3 降级条款）。测试沿用 fake agentscope 模式。

**Tech Stack:** Python 3.11+ / Pydantic v2 / Typer / pytest / ruff+mypy（CI 门禁）。

## Global Constraints

- 零新增运行时依赖；`agentscope` 保持延迟导入（`[agentscope]` extra 可选）。
- 真实 2.0 API 以检索结论为准（见 Task 0），**不虚构不存在的类/方法**；`except` 内 `raise` 必须 `from None`（B904）。
- 测试先失败再实现（TDD）；每个 task 结束全量测试通过后 commit。
- 向后兼容：`TenantConfig.agents` 缺省 `None`；单 Agent 场景 `deployed.agent` 行为不变；现有 `test_deploy_assembly.py` 断言（`model is None`、`name == "Acme_agent"`）必须继续通过。
- ruff 规则集 E/W/F/I/C4/B/SIM/UP、line-length 110；ruff format 与 mypy 是 CI 门禁。

---

### Task 0: 2.0 多 Agent API 检索结论（实现依据，无需代码）

检索来源：GitHub `agentscope-ai/agentscope` main 分支 `src/agentscope/app/__init__.py`、`_app.py`、`_types.py`（2026-08-25 读取；官方 docs.agentscope.io/versions/2.0.x/ 404，与 docs/agentscope_api_mapping.md 的警告一致，以源码为准）：

- `agentscope.app` 导出 `create_app` + `SubAgentTemplate`（仅这两个 public 符号）。
- `create_app(storage, message_bus, workspace_manager, ..., custom_subagent_templates=None, ...) -> FastAPI`：**FastAPI 服务工厂**；Agent 在每次 chat turn 按需组装（不是预先实例化挂载）；生命周期归 FastAPI lifespan（storage/message_bus/workspace_manager 的 `__aenter__/__aexit__`）。需要真实的 storage（如 Redis）+ message_bus（如 RedisMessageBus）——单机 FDE 场景不引入。
- **2.0 官方多 Agent 机制 = `SubAgentTemplate`**（`_types.py`，纯数据 Pydantic BaseModel）：`type`（路由键，`AgentCreate` tool 的 `subagent_type` 枚举值）、`description`、`system_prompt_template`（Python format 串，占位符 `{team_name}/{team_description}/{member_name}/{member_description}/{leader_name}`）、`context_config`、`react_config`、`permission_context`、`tasks_context`。leader agent 通过 `AgentCreate` tool 创建子 agent、`TeamSay(to=name)` 协调。
- `Agent` 类无 `stop()` 方法；"优雅停止"= 关闭 workspace 等有生命周期句柄的对象。

**因此本计划落地**：多 Agent = 拓扑声明（manifest `agents` 段）+ 每个 spec 组装真实 `Agent` + `SubAgentTemplate` 蓝图导出（可直接喂 `create_app(custom_subagent_templates=...)`）+ stop 关闭可关闭句柄。真实 app 服务启动不在本期（spec §4.3 降级条款），README/文档说明接线方式。

---

### Task 1: AgentSpec 模型 + TenantConfig.agents

**Files:**
- Modify: `fde_scope/config.py`（`TenantConfig` 前加 `AgentSpec`；`TenantConfig` 加字段）
- Modify: `fde_scope/templates/tenant_config.yaml`
- Test: `tests/test_deploy.py`

**Interfaces:**
- Produces: `AgentSpec`（Pydantic BaseModel：`name: str`、`role: str`、`system_prompt: str | None = None`、`model: str | None = None`、`toolkit: dict = Field(default_factory=dict)`）；`TenantConfig.agents: list[AgentSpec] | None = None`。Task 2/3/4 依赖。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_deploy.py` 末尾）

```python
def test_agent_spec_defaults() -> None:
    from fde_scope.config import AgentSpec

    spec = AgentSpec(name="researcher", role="调研员")
    assert spec.system_prompt is None
    assert spec.model is None  # None → runtime injection
    assert spec.toolkit == {}


def test_tenant_config_agents_default_none_and_roundtrip() -> None:
    assert TenantConfig(id="t", name="T").agents is None  # 向后兼容
    cfg = TenantConfig(
        id="t",
        name="T",
        agents=[{"name": "researcher", "role": "调研员"}, {"name": "coder", "role": "实施员", "model": "qwen-max"}],
    )
    assert len(cfg.agents) == 2
    assert cfg.agents[1].model == "qwen-max"


def test_tenant_config_from_yaml_reads_agents(tmp_path) -> None:
    p = tmp_path / "tenant.yaml"
    p.write_text(
        "id: acme\nname: Acme\nagents:\n  - name: researcher\n    role: 调研员\n  - name: coder\n    role: 实施员\n",
        encoding="utf-8",
    )
    cfg = TenantConfig.from_yaml(p)
    assert [a.name for a in cfg.agents] == ["researcher", "coder"]
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_deploy.py -q`
Expected: FAIL（`AgentSpec` 不存在 → ImportError）

- [ ] **Step 3: 最小实现**（`fde_scope/config.py`，`TenantConfig` 类定义前插入 `AgentSpec`；`TenantConfig` 增加 `agents` 字段）

```python
class AgentSpec(BaseModel):
    """One agent in a tenant's multi-agent topology.

    ``model`` is the agentscope model config name; ``None`` means the
    runtime injects it (matches tenant-level model semantics).
    """

    name: str
    role: str
    system_prompt: str | None = None
    model: str | None = None
    toolkit: dict = Field(default_factory=dict)
```

`TenantConfig` 增加（放在 `profile` 之后）：

```python
    agents: list[AgentSpec] | None = None
```

模板 `fde_scope/templates/tenant_config.yaml` 末尾追加：

```yaml
# Multi-agent topology (optional). Each entry becomes one agentscope.agent.Agent
# at deploy time; the manifest carries them as the `agents` section.
#   model: agentscope model config name; omitted → runtime injection (None)
agents:
  - name: researcher
    role: 现场调研员
  - name: coder
    role: 实施工程师
    model: qwen-max
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_deploy.py -q`
Expected: PASS

- [ ] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/config.py fde_scope/templates/tenant_config.yaml tests/test_deploy.py && git commit -m "feat(config): add AgentSpec and TenantConfig.agents for multi-agent topology"
```

---

### Task 2: 多 Agent 组装 + 模型 wiring + manifest agents 段

**Files:**
- Modify: `fde_scope/deploy/tenant_manager.py`
- Test: `tests/test_deploy_assembly.py`

**Interfaces:**
- Consumes: Task 1 的 `AgentSpec`/`TenantConfig.agents`。
- Produces: `DeployedAgent.agents: list[Any]`（真实组装出的 Agent 列表）+ `DeployedAgent.agent`（单 Agent 兼容：`agents[0]` 或 None）；`deploy()` 在 dry-run 与 real 两种模式都生成 `manifest["agents"]`（`[{name, role, model, system_prompt, toolkit}]`，system_prompt 截 120 字符）；`_assemble_agent(tenant, spec, collection)` 按 spec 组装（model = spec.model，None 保留）。Task 3/4 依赖 `deployed.agents` 与 manifest 结构。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_deploy_assembly.py` 末尾，复用 `fake_agentscope` fixture 与 FakeAgent）

```python
def test_deployer_assembles_multi_agent_topology(fake_agentscope: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """每个 AgentSpec 组装一个 Agent；model 从 spec wiring；manifest 带 agents 段。"""
    calls: list[str] = []
    monkeypatch.setattr(tenant_manager, "build_workspace", lambda spec: ("workspace", spec.tenant_id))
    monkeypatch.setattr(tenant_manager, "build_engine", lambda bp: ("engine", bp.tenant_id))
    deployer = TenantDeployer(agentscope_extra=True)
    tenant = TenantConfig(
        id="acme",
        name="Acme",
        agents=[
            {"name": "researcher", "role": "调研员"},
            {"name": "coder", "role": "实施员", "model": "qwen-max", "system_prompt": "You code."},
        ],
    )
    deployed = deployer.deploy(tenant)
    assert len(deployed.agents) == 2
    assert deployed.agent is deployed.agents[0]  # 单 Agent 兼容
    assert deployed.agents[0].kwargs["name"] == "researcher"
    assert deployed.agents[0].kwargs["model"] is None  # spec.model 缺失 → 运行时注入
    assert "调研员" in deployed.agents[0].kwargs["system_prompt"]
    assert deployed.agents[1].kwargs["model"] == "qwen-max"
    assert deployed.agents[1].kwargs["system_prompt"] == "You code."
    # manifest agents 段（dry-run 与 real 都有）
    agents = deployed.manifest["agents"]
    assert [a["name"] for a in agents] == ["researcher", "coder"]
    assert agents[1]["model"] == "qwen-max"
    assert agents[0]["toolkit"] == ["corpus_collection", "ticket_api"]


def test_deployer_default_single_agent_manifest(fake_agentscope: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """agents 缺省时沿用现有单 Agent 行为（name = {tenant.name}_agent）。"""
    monkeypatch.setattr(tenant_manager, "build_workspace", lambda spec: ("w", spec.tenant_id))
    monkeypatch.setattr(tenant_manager, "build_engine", lambda bp: ("e", bp.tenant_id))
    deployer = TenantDeployer(agentscope_extra=True)
    deployed = deployer.deploy(TenantConfig(id="acme", name="Acme"))
    assert len(deployed.agents) == 1
    assert deployed.agents[0].kwargs["name"] == "Acme_agent"
    assert deployed.manifest["agents"][0]["name"] == "Acme_agent"


def test_dry_run_manifest_has_agents_section() -> None:
    """dry-run 也携带 agents 拓扑声明（计划可校验）。"""
    deployer = TenantDeployer(agentscope_extra=False)
    deployed = deployer.deploy(
        TenantConfig(id="acme", name="Acme", agents=[{"name": "r", "role": "调研"}]),
        dry_run=True,
    )
    assert deployed.manifest["agents"] == [
        {"name": "r", "role": "调研", "model": None, "system_prompt": "", "toolkit": ["corpus_collection", "ticket_api"]}
    ]
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_deploy_assembly.py -q`
Expected: FAIL（`deployed.agents` 不存在 → AttributeError）

- [ ] **Step 3: 最小实现**（`fde_scope/deploy/tenant_manager.py`）

`DeployedAgent` 增加字段（`agent` 后）：

```python
    agents: list[Any] = field(default_factory=list)
```

`deploy()` 重构（关键段）：

```python
        spec = SandboxSpec.from_quota_string(tenant.id, tenant.resource_quota)
        blueprint = default_blueprint(tenant.id, mode=tenant.approval_policy.mode)
        collection = f"corpus_{tenant.id}"
        specs = tenant.agents or [AgentSpec(name=f"{tenant.name}_agent", role=tenant.name)]

        manifest = {
            ...
            "corpus_collection": collection,
            "approval_policy": tenant.approval_policy.model_dump(),
            "started": False,
        }
        manifest["agents"] = [
            {
                "name": s.name,
                "role": s.role,
                "model": s.model,  # None → wired by the runtime
                "system_prompt": (s.system_prompt or self._build_prompt(tenant, s))[:120],
                "toolkit": sorted(self._build_toolkit(tenant, collection).keys()),
            }
            for s in specs
        ]
        ...
        if dry_run or not self._has_as:
            return DeployedAgent(
                tenant_id=tenant.id,
                corpus_collection=collection,
                manifest=manifest,
            )

        # -- real assembly (only when agentscope extra is installed) ----------
        workspace = build_workspace(spec)
        engine = build_engine(blueprint)
        agents = [self._assemble_agent(tenant, s, collection) for s in specs]
        manifest["started"] = True
        return DeployedAgent(
            tenant_id=tenant.id,
            agent=agents[0],
            agents=agents,
            workspace=workspace,
            engine=engine,
            corpus_collection=collection,
            manifest=manifest,
        )
```

`_assemble_agent` 签名改为 `(self, tenant: TenantConfig, spec: AgentSpec, collection: str) -> Any`，内部：

```python
        from agentscope.agent import Agent, ReActConfig

        sys_prompt = spec.system_prompt or self._build_prompt(tenant, spec)
        react = ReActConfig(max_iters=20)
        return Agent(
            name=spec.name,
            system_prompt=sys_prompt,
            model=spec.model,  # None → wired from tenant.model at runtime
            toolkit=self._build_toolkit(tenant, collection),
            react_config=react,
        )
```

`_build_prompt` 改为 `(tenant, spec)`：

```python
    @staticmethod
    def _build_prompt(tenant: TenantConfig, spec: AgentSpec) -> str:
        return (
            f"You are the {spec.role} for {tenant.name} (tenant={tenant.id}). "
            "Answer customer tickets using only the tenant corpus. "
            "Escalate (ASK) refunds above policy thresholds. "
            "Never access other tenants' data."
        )
```

需要 import `AgentSpec`（`from fde_scope.config import AgentSpec`，与 `TenantConfig` 同源）。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_deploy_assembly.py tests/test_deploy.py -q`
Expected: PASS（含旧断言：`name == "Acme_agent"`、`model is None`、`"Acme" in system_prompt` 仍成立——默认 spec role=tenant.name）

- [ ] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/deploy/tenant_manager.py tests/test_deploy_assembly.py && git commit -m "feat(deploy): assemble multi-agent topology with model wiring"
```

---

### Task 3: SubAgentTemplate 蓝图导出（2.0 官方多 Agent 机制）

**Files:**
- Modify: `fde_scope/deploy/tenant_manager.py`
- Test: `tests/test_deploy_assembly.py`

**Interfaces:**
- Consumes: Task 2 的 `deployed.agents`/manifest。
- Produces: `TenantDeployer.build_subagent_templates(tenant, specs) -> list[Any]`（lazy import `agentscope.app.SubAgentTemplate`；每 spec 一个 `SubAgentTemplate(type=spec.name, description=spec.role, system_prompt_template=spec.system_prompt or 默认模板串)`）；real 组装时 `DeployedAgent.subagent_templates` + `manifest["subagent_templates"] = [{"type", "description"}]`。Task 4 的文档/CLI 依赖。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_deploy_assembly.py` 末尾）

```python
class FakeSubAgentTemplate:
    """Stands in for ``agentscope.app.SubAgentTemplate``."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


@pytest.fixture
def fake_agentscope_app(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("agentscope.app")
    module.SubAgentTemplate = FakeSubAgentTemplate  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agentscope.app", module)


def test_build_subagent_templates_uses_2_0_blueprints(
    fake_agentscope_app: None, fake_agentscope: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """每个 AgentSpec → 一个 SubAgentTemplate（type 路由键 + 占位符模板串）。"""
    monkeypatch.setattr(tenant_manager, "build_workspace", lambda spec: ("w", spec.tenant_id))
    monkeypatch.setattr(tenant_manager, "build_engine", lambda bp: ("e", bp.tenant_id))
    deployer = TenantDeployer(agentscope_extra=True)
    tenant = TenantConfig(
        id="acme",
        name="Acme",
        agents=[
            {"name": "researcher", "role": "调研员"},
            {"name": "coder", "role": "实施员", "system_prompt": "You are {member_name}."},
        ],
    )
    deployed = deployer.deploy(tenant)
    templates = deployed.subagent_templates
    assert len(templates) == 2
    assert templates[0].kwargs["type"] == "researcher"
    assert templates[0].kwargs["description"] == "调研员"
    # 默认模板串必须含 2.0 占位符（{member_name} 等）
    assert "{member_name}" in templates[0].kwargs["system_prompt_template"]
    assert templates[1].kwargs["system_prompt_template"] == "You are {member_name}."
    assert deployed.manifest["subagent_templates"] == [
        {"type": "researcher", "description": "调研员"},
        {"type": "coder", "description": "实施员"},
    ]
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_deploy_assembly.py::test_build_subagent_templates_uses_2_0_blueprints -v`
Expected: FAIL（`subagent_templates` 不存在 → AttributeError）

- [ ] **Step 3: 最小实现**（`fde_scope/deploy/tenant_manager.py`）

`DeployedAgent` 增加字段：

```python
    subagent_templates: list[Any] = field(default_factory=list)
```

`deploy()` real 分支（`agents = [...]` 后）：

```python
        templates = self.build_subagent_templates(tenant, specs)
        manifest["subagent_templates"] = [{"type": t.type, "description": t.description} for t in templates]
```

real 分支 return 加 `subagent_templates=templates`。新增方法（`_build_toolkit` 后）：

```python
    def build_subagent_templates(self, tenant: TenantConfig, specs: list[AgentSpec]) -> list[Any]:
        """2.0 官方多 Agent 蓝图：喂给 ``create_app(custom_subagent_templates=...)``。

        ``SubAgentTemplate`` 是纯数据蓝图（agentscope.app._types），leader agent
        通过 ``AgentCreate`` tool 的 ``subagent_type`` 路由；占位符模板串使用
        官方支持的 {team_name}/{member_name}/{member_description}。
        """
        from agentscope.app import SubAgentTemplate

        return [
            SubAgentTemplate(
                type=s.name,
                description=s.role,
                system_prompt_template=(
                    s.system_prompt
                    or (
                        f"You are {{member_name}} ({s.role}) on the {{team_name}} team "
                        f"for tenant {tenant.id}. Work with the leader and other members "
                        "using TeamSay; never access other tenants' data."
                    )
                ),
            )
            for s in specs
        ]
```

注意默认模板串用 `{{member_name}}`（Python format 字面量转义后运行时输出 `{member_name}`）。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_deploy_assembly.py -q`
Expected: PASS

- [ ] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/deploy/tenant_manager.py tests/test_deploy_assembly.py && git commit -m "feat(deploy): export SubAgentTemplate blueprints for 2.0 multi-agent"
```

---

### Task 4: 生命周期 `stop()` + CLI agents 声明

**Files:**
- Modify: `fde_scope/deploy/tenant_manager.py`
- Modify: `fde_scope/cli.py`（`deploy` 命令）
- Test: `tests/test_deploy_assembly.py`、`tests/test_cli.py`

**Interfaces:**
- Consumes: Task 2/3 的 `DeployedAgent`。
- Produces: `TenantDeployer.stop(deployed) -> dict`（2.0 无 `Agent.stop`——优雅停止 = 关闭 workspace/engine 的可关闭句柄（`close()`/`__aexit__`），标记 `manifest["started"]=False`，返回 `{"closed": [...]}`）；CLI `deploy --agent "name:role[:model]"`（可重复）。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_deploy_assembly.py` 与 `tests/test_cli.py` 末尾）

```python
# tests/test_deploy_assembly.py 追加
class FakeClosable:
    def __init__(self, name: str) -> None:
        self.name = name
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_stop_closes_handles_and_flags_manifest(fake_agentscope: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """2.0 没有 Agent.stop——stop 关闭可关闭句柄并标记 manifest。"""
    monkeypatch.setattr(tenant_manager, "build_workspace", lambda spec: FakeClosable("ws"))
    monkeypatch.setattr(tenant_manager, "build_engine", lambda bp: FakeClosable("engine"))
    deployer = TenantDeployer(agentscope_extra=True)
    deployed = deployer.deploy(TenantConfig(id="acme", name="Acme"))
    ws, engine = deployed.workspace, deployed.engine
    report = deployer.stop(deployed)
    assert ws.closed is True and engine.closed is True
    assert report["closed"] == ["ws", "engine"]
    assert deployed.manifest["started"] is False
```

```python
# tests/test_cli.py 追加
def test_deploy_manifest_lists_agents(tmp_path: Path, monkeypatch) -> None:
    """--agent 可重复声明多 Agent 拓扑，manifest 输出 agents 段。"""
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(
        app,
        [
            "deploy", "--tenant", "acme", "--name", "Acme", "--dry-run",
            "--agent", "researcher:调研员",
            "--agent", "coder:实施员:qwen-max",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert '"agents"' in r.stdout
    assert "researcher" in r.stdout and "coder" in r.stdout


def test_deploy_invalid_agent_spec_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["deploy", "--tenant", "acme", "--dry-run", "--agent", "bad-spec"])
    assert r.exit_code == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_deploy_assembly.py::test_stop_closes_handles_and_flags_manifest tests/test_cli.py::test_deploy_manifest_lists_agents tests/test_cli.py::test_deploy_invalid_agent_spec_exits_2 -v`
Expected: FAIL（`stop` 不存在 / `--agent` 未知选项）

- [ ] **Step 3: 最小实现**

`fde_scope/deploy/tenant_manager.py` 新增方法（`build_subagent_templates` 后）：

```python
    @staticmethod
    def stop(deployed: DeployedAgent) -> dict:
        """Gracefully stop a deployment (2.0-adapted).

        AgentScope 2.0 has no ``Agent.stop`` — agents are assembled per
        chat turn and the app service owns lifecycle via FastAPI lifespan.
        We close whatever has a close handle (workspace, engine) and flag
        the manifest; anything without one is left to the process exit.
        """
        closed: list[str] = []
        for name, obj in (("workspace", deployed.workspace), ("engine", deployed.engine)):
            if obj is None:
                continue
            closer = getattr(obj, "close", None)
            if closer is not None:
                closer()
                closed.append(name)
        deployed.manifest["started"] = False
        return {"closed": closed}
```

`fde_scope/cli.py` `deploy` 命令签名增加：

```python
    agent_specs: list[str] = typer.Option([], "--agent", "-a", help="Agent spec 'name:role[:model]' (repeatable)"),
```

`cfg` 构造前解析（`corpus_report` 处理后）：

```python
    agents = []
    for a in agent_specs:
        parts = a.split(":")
        if len(parts) == 2:
            name, role, model = parts[0], parts[1], None
        elif len(parts) == 3:
            name, role, model = parts
        else:
            console.print(f"[red]Invalid agent spec:[/red] {a} (expected name:role[:model])")
            raise typer.Exit(2)
        agents.append(AgentSpec(name=name, role=role, model=model))
    cfg = TenantConfig(id=tenant, name=name, model=model, corpus_path=corpus, agents=agents or None)
```

`from .config import AgentSpec` 加入现有 import 行。`deploy` 输出在 `Manifest` 行前加：

```python
    for a in (deployed.manifest.get("agents") or []):
        console.print(f"🔄 Agent: [bold]{a['name']}[/bold] · {a['role']} · model={a['model'] or 'runtime'}")
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_deploy_assembly.py tests/test_cli.py::test_deploy_manifest_lists_agents tests/test_cli.py::test_deploy_invalid_agent_spec_exits_2 -q`
Expected: PASS

- [ ] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/deploy/tenant_manager.py fde_scope/cli.py tests/test_deploy_assembly.py tests/test_cli.py && git commit -m "feat(deploy): lifecycle stop() and CLI multi-agent specs"
```

---

### Task 5: 收尾（README + 门禁）

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README 更新**

1. CLI reference `deploy` 行改为：`deploy    [Layer 3] Assemble (and optionally start) a multi-tenant agent (multi-agent via --agent)`
2. `fde_scope/deploy/tenant_manager.py` 已含真实 API 对照说明；在 README 的 AgentScope 说明处（若存在）或 `## 🛠 CLI reference` 后新增小节：

```markdown
## 🤖 多 Agent 拓扑（AgentScope 2.0）

`tenant_config.yaml` 的 `agents` 段（或 CLI `--agent name:role[:model]`）声明一个
tenant 的多个 Agent。`fde-scope deploy` 为每个 spec 组装真实的
`agentscope.agent.Agent`（模型从 `spec.model` wiring，缺失留运行时注入），
manifest 携带完整 `agents` 段与 `subagent_templates`。

多 Agent 交互走 AgentScope 2.0 官方机制：`agentscope.app.SubAgentTemplate`
蓝图（`create_app(custom_subagent_templates=...)`），leader agent 通过
`AgentCreate` / `TeamSay` 协调子 Agent。真实 app 服务（storage + message_bus +
workspace_manager）需要独立后端，本期交付蓝图导出 + 拓扑声明（spec §4.3 降级条款），
不虚构 API。生命周期：2.0 无 `Agent.stop`，`TenantDeployer.stop()` 关闭
workspace/engine 句柄并标记 manifest。
```

- [ ] **Step 2: 全量门禁**

```bash
ruff check fde_scope tests && ruff format --check fde_scope tests && mypy fde_scope && pytest -q
```

Expected: 全部通过。若有格式问题：`ruff check --fix fde_scope tests && ruff format fde_scope tests` 后重跑。

- [ ] **Step 3: 提交**

```bash
git add README.md && git commit -m "docs: document multi-agent topology and lifecycle"
```

---

## 计划自审记录

- spec §4.2 差距（model wiring 未实现、无多 Agent 拓扑、无生命周期）→ Task 2/3/4；§4.3（TenantConfig.agents + AgentSpec、deploy/stop 生命周期、manifest agents 段、多 Agent 官方机制优先、降级条款）→ Task 1-4；§4.3 测试策略（fake agentscope 扩展 + @pytest.mark.agentscope）→ Task 2/3/4 测试。
- 求真原则：Task 0 检索记录写入计划；不虚构 `Agent.stop`（Task 4 用 close 句柄 + manifest 标记）。
- 类型一致性：`AgentSpec.model` 语义（None → runtime injection）在 Task 1 定义、Task 2 使用、Task 3 manifest 记录、Task 4 CLI 解析；`manifest["agents"]` 字段名 Task 2 定义、Task 4 CLI 消费。
- 向后兼容：单 Agent 缺省行为（`Acme_agent`、model None）由现有测试锁定，Task 2 实现时验证。
- 已知偏差（YAGNI）：不实现 `create_app` 真实启动（依赖 Redis 等）；CLI 无 `--stop`（stop 面向编程 API + 文档）。

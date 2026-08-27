"""Tenant deployment — assemble a multi-tenant agent system.

STATUS: assembly-only. ``TenantDeployer.deploy`` builds the real AgentScope
2.0 objects (workspace + permission context + tool kit + agent + sub-agent
blueprints) but does *not* start Docker or invoke the model — that's the
runtime step, gated behind the optional ``agentscope`` extra. The assembly path
is fully typed and unit-checkable today.

What "assembled for real" means here (all three are live objects, not plans):
  - ``toolkit=`` gets a genuine ``agentscope.tool.Toolkit`` whose tools read the
    tenant's actual connectors / forged corpus (see :mod:`fde_scope.deploy.toolkit`).
  - ``state=`` carries the permission context the agent enforces — rules written
    to a detached ``PermissionEngine`` would never be seen by it.
  - ``create_app(custom_subagent_templates=...)`` gets the multi-agent blueprints.

AgentScope 2.0 API reality (see docs/agentscope_api_mapping.md):
  - There is no ``HarnessAgent``. The unified class is ``agentscope.agent.Agent``
    configured with ``ReActConfig``; the "engineering layer over ReAct" is
    achieved by composing ``MiddlewareBase`` middlewares.
  - There is no ``VectorStore(collection=...)``; the RAG entry point is
    ``agentscope.rag.KnowledgeBase(collection=...)``, and it needs an embedding
    model — so corpus retrieval ships as a keyword tool until one is configured.
  - HITL is not a ``HumanInTheLoop(policy, timeout)`` object — it's the
    streaming event flow ``RequireUserConfirmEvent`` → ``UserConfirmResultEvent``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fde_scope.config import AgentSpec, TenantConfig

from .permission_builder import build_context, default_blueprint
from .roles import connectors_for_role
from .sandbox_config import SandboxSpec, build_workspace
from .toolkit import ToolBinding, build_toolkit, describe_bindings, plan_bindings

if TYPE_CHECKING:
    from fde_scope.corpus import CorpusReport


@dataclass
class DeployedAgent:
    """The handle returned by a successful deploy.

    ``agent``/``workspace``/``engine`` are real AgentScope objects when the
    extra is installed; ``None`` in dry-run / core-only mode. ``manifest``
    always carries the human-readable deployment record.
    """

    tenant_id: str
    agent: Any = None
    agents: list[Any] = field(default_factory=list)
    subagent_templates: list[Any] = field(default_factory=list)
    workspace: Any = None
    engine: Any = None
    corpus_collection: str = ""
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def is_assembled(self) -> bool:
        return self.agent is not None


def build_deploy_plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dry-run a deployment from an HTTP-style payload and return the tool plan.

    One code path answers "which role agent gets which connector tool, against
    which physical source — and which ones are still waiting for one?" for the
    web console and the PawApp backend, so neither can drift from what
    ``fde-scope deploy`` actually assembles.

    Forces ``agentscope_extra=False`` on the deployer: a plan is data, so asking
    for one must not import AgentScope, construct a model, or touch Docker.
    Raises ``pydantic.ValidationError`` for a bad payload — callers turn that
    into a 422 / exit-2, never into a plausible-looking empty plan.
    """
    body = payload or {}
    tenant_id = body.get("tenant") or body.get("id") or "acme"
    tenant = TenantConfig.model_validate(
        {
            "id": tenant_id,
            "name": body.get("name") or tenant_id,
            "model": body.get("model") or "qwen-max",
            "profile": body.get("profile") or "ticket",
            "sources": body.get("sources") or {},
            "agents": body.get("agents") or None,
            "approval_policy": body.get("approval_policy")
            or {"mode": body.get("approval_mode", "conservative")},
        }
    )
    manifest = TenantDeployer(agentscope_extra=False).deploy(tenant, dry_run=True).manifest
    bound = sorted({tool for agent in manifest["agents"] for tool in agent["bound"]})
    unbound = sorted({tool for agent in manifest["agents"] for tool in agent["unbound"]})
    return {
        "manifest": manifest,
        "summary": {
            "bound_tools": bound,
            "unbound_tools": unbound,
            "agents": len(manifest["agents"]),
        },
    }


def summarize_deploy_plan(plan: dict[str, Any]) -> str:
    """Render a plan as the short, honest text an FDE reads before typing a deploy."""
    lines: list[str] = []
    for agent in plan["manifest"]["agents"]:
        lines.append(f"{agent['name']} [{agent['role_bucket']}] · {agent['role']}")
        for tool in agent["tools"]:
            mark = "bound" if tool["bound"] else "TODO "
            lines.append(f"  {mark} {tool['tool']:24s} {tool['note']}")
    summary = plan["summary"]
    lines.append(
        f"{summary['agents']} agent(s) · {len(summary['bound_tools'])} bound tool(s)"
        f" · {len(summary['unbound_tools'])} waiting for a source"
    )
    return "\n".join(lines)


class TenantDeployer:
    """Assemble a tenant agent from a TenantConfig + forged corpus."""

    def __init__(self, agentscope_extra: bool | None = None) -> None:
        # Detect once whether the real types are importable.
        self._has_as = agentscope_extra
        if self._has_as is None:
            try:
                import agentscope  # noqa: F401

                self._has_as = True
            except ImportError:
                self._has_as = False

    def deploy(
        self,
        tenant: TenantConfig,
        corpus_report: CorpusReport | None = None,
        dry_run: bool = False,
    ) -> DeployedAgent:
        """Assemble (and in real mode, start) a tenant agent.

        In ``dry_run`` or core-only mode this returns a :class:`DeployedAgent`
        with a populated manifest but no live objects — enough to validate
        the deployment plan without Docker or a model.
        """
        spec = SandboxSpec.from_quota_string(tenant.id, tenant.resource_quota)
        specs = tenant.agents or [AgentSpec(name=f"{tenant.name}_agent", role=tenant.name)]
        # One tool plan per agent; the permission policy is derived from what the
        # agents can actually call, so capability and approval stay coherent.
        plans = {s.name: plan_bindings(tenant, s, corpus_report) for s in specs}
        bound_tools = tuple(
            sorted({name for plan in plans.values() for name in [b.name for b in plan if b.bound]})
        )
        # The approval policy decides which tool calls escalate to ASK (HITL).
        blueprint = default_blueprint(tenant.id, mode=tenant.approval_policy.mode, allow_tools=bound_tools)
        collection = f"corpus_{tenant.id}"

        manifest = {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "model": tenant.model,
            "sandbox": {
                "backend": spec.backend,
                "base_image": spec.base_image,
                "resource_quota": spec.resource_quota,
            },
            "permissions": {
                "allow": blueprint.allow,
                "deny": blueprint.deny,
                "ask": blueprint.ask,
            },
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
                "connectors": connectors_for_role(s.role),
                **describe_bindings(s, plans[s.name]),
            }
            for s in specs
        ]
        if corpus_report is not None:
            manifest["corpus"] = {
                "total": corpus_report.total,
                "real": corpus_report.real,
                "synthetic": corpus_report.synthetic,
            }

        if dry_run or not self._has_as:
            return DeployedAgent(
                tenant_id=tenant.id,
                corpus_collection=collection,
                manifest=manifest,
            )

        # -- real assembly (only when agentscope extra is installed) ----------
        workspace = build_workspace(spec)
        # The context, not just an engine: ``Agent`` enforces the one in its state.
        perm_context = build_context(blueprint, mode=tenant.approval_policy.mode)
        agents = [self._assemble_agent(tenant, s, perm_context, corpus_report, plans[s.name]) for s in specs]
        templates = self.build_subagent_templates(tenant, specs)
        manifest["subagent_templates"] = [{"type": t.type, "description": t.description} for t in templates]
        manifest["started"] = True
        return DeployedAgent(
            tenant_id=tenant.id,
            agent=agents[0],
            agents=agents,
            subagent_templates=templates,
            workspace=workspace,
            engine=perm_context,
            corpus_collection=collection,
            manifest=manifest,
        )

    # -- internals --------------------------------------------------------------
    def _assemble_agent(
        self,
        tenant: TenantConfig,
        spec: AgentSpec,
        perm_context: Any,
        corpus_report: CorpusReport | None = None,
        bindings: list[ToolBinding] | None = None,
    ) -> Any:
        """Build one real ``agentscope.agent.Agent`` from an AgentSpec (lazy import).

        This is the faithful 2.0 translation of the design doc's fictional
        ``HarnessAgent(...)`` block: same intent (corpus tool + role connector
        tools + workspace + permission + HITL), real types.
        """
        from agentscope.agent import Agent, ReActConfig
        from agentscope.model import OllamaChatModel
        from agentscope.state import AgentState

        sys_prompt = spec.system_prompt or self._build_prompt(tenant, spec)
        # ReActConfig replaces the implicit reasoning loop of the fictional
        # HarnessAgent; HITL emerges from rules with behavior=ASK.
        react = ReActConfig(max_iters=20)
        # 2.0 的 Agent 要求 ChatModelBase 实例（不接受字符串）：用 spec.model
        # （缺省 tenant.model）构造零配置占位模型，生产运行时以带凭证的
        # ChatModel 替换。
        model_name = spec.model or tenant.model
        if bindings is None:
            bindings = plan_bindings(tenant, spec, corpus_report)
        # Field experience → agent capability: exported skill directories (each a
        # <slug>/SKILL.md dir, see fde_scope.skills.exporters) ride the official
        # Toolkit registration channel — AgentSpec.toolkit["skills_dirs"], the same
        # per-agent override style as "sources". Directories that don't exist are
        # dropped, never pretending a skill the agent won't actually get.
        declared = (spec.toolkit or {}).get("skills_dirs")
        if isinstance(declared, str):
            declared = [declared]
        skills_dirs = [d for d in (declared or []) if isinstance(d, str) and d and Path(d).is_dir()]
        return Agent(
            name=spec.name,
            system_prompt=sys_prompt,
            model=OllamaChatModel(model=model_name),
            # A genuine ``Toolkit``. ``Agent`` does not validate this argument, so
            # passing a dict would assemble and then die on the first ReAct turn.
            toolkit=build_toolkit(bindings, corpus_report, skills_dirs),
            # What the agent actually enforces is the context inside its state,
            # not a detached engine built alongside it.
            state=AgentState(permission_context=perm_context),
            react_config=react,
        )

    def build_subagent_templates(self, tenant: TenantConfig, specs: list[AgentSpec]) -> list[Any]:
        """2.0 官方多 Agent 蓝图：喂给 ``create_app(custom_subagent_templates=...)``.

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

    @staticmethod
    def stop(deployed: DeployedAgent) -> dict:
        """Gracefully stop a deployment (2.0-adapted).

        AgentScope 2.0 has no ``Agent.stop`` — agents are assembled per
        chat turn and the app service owns lifecycle via FastAPI lifespan.
        We close whatever has a close handle (workspace, permission context)
        and flag the manifest; anything without one is left to the process exit.
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

    @staticmethod
    def _build_prompt(tenant: TenantConfig, spec: AgentSpec) -> str:
        return (
            f"You are the {spec.role} for {tenant.name} (tenant={tenant.id}). "
            "Answer customer tickets using only the tenant corpus. "
            "Escalate (ASK) refunds above policy thresholds. "
            "Never access other tenants' data."
        )

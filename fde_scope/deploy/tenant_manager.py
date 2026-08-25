"""Tenant deployment — assemble a multi-tenant agent system.

STATUS: assembly-only. ``TenantDeployer.deploy`` builds the real AgentScope
2.0 objects (workspace + permission engine + corpus index + agent) but does
*not* start Docker or invoke the model — that's the runtime step, gated
behind the optional ``agentscope`` extra. The assembly path is fully typed
and unit-checkable today.

AgentScope 2.0 API reality (see docs/agentscope_api_mapping.md):
  - There is no ``HarnessAgent``. The unified class is ``agentscope.agent.Agent``
    configured with ``ReActConfig``; the "engineering layer over ReAct" is
    achieved by composing ``MiddlewareBase`` middlewares.
  - There is no ``VectorStore(collection=...)``; the RAG entry point is
    ``agentscope.rag.KnowledgeBase(collection=...)``.
  - HITL is not a ``HumanInTheLoop(policy, timeout)`` object — it's the
    streaming event flow ``RequireUserConfirmEvent`` → ``UserConfirmResultEvent``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fde_scope.config import AgentSpec, TenantConfig

from .permission_builder import build_engine, default_blueprint
from .sandbox_config import SandboxSpec, build_workspace

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
        # The approval policy decides which tool calls escalate to ASK (HITL).
        blueprint = default_blueprint(tenant.id, mode=tenant.approval_policy.mode)
        collection = f"corpus_{tenant.id}"
        specs = tenant.agents or [AgentSpec(name=f"{tenant.name}_agent", role=tenant.name)]

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
                "toolkit": sorted(self._build_toolkit(tenant, collection).keys()),
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
        engine = build_engine(blueprint)
        agents = [self._assemble_agent(tenant, s, collection) for s in specs]
        templates = self.build_subagent_templates(tenant, specs)
        manifest["subagent_templates"] = [
            {"type": t.type, "description": t.description} for t in templates
        ]
        manifest["started"] = True
        return DeployedAgent(
            tenant_id=tenant.id,
            agent=agents[0],
            agents=agents,
            subagent_templates=templates,
            workspace=workspace,
            engine=engine,
            corpus_collection=collection,
            manifest=manifest,
        )

    # -- internals --------------------------------------------------------------
    def _assemble_agent(self, tenant: TenantConfig, spec: AgentSpec, collection: str) -> Any:
        """Build one real ``agentscope.agent.Agent`` from an AgentSpec (lazy import).

        This is the faithful 2.0 translation of the design doc's fictional
        ``HarnessAgent(...)`` block: same intent (corpus tool + ticket tool +
        workspace + permission + HITL), real types.
        """
        from agentscope.agent import Agent, ReActConfig

        sys_prompt = spec.system_prompt or self._build_prompt(tenant, spec)
        # ReActConfig replaces the implicit reasoning loop of the fictional
        # HarnessAgent; HITL emerges from rules with behavior=ASK.
        react = ReActConfig(max_iters=20)
        return Agent(
            name=spec.name,
            system_prompt=sys_prompt,
            model=spec.model,  # None → wired from tenant.model at runtime
            toolkit=self._build_toolkit(tenant, collection),
            react_config=react,
        )

    def _build_toolkit(self, tenant: TenantConfig, collection: str) -> Any:
        """Expose the tenant corpus + ticket API as agent tools.

        In 2.0 the corpus is surfaced via ``KnowledgeBase(collection=...)``
        and registered as a tool/middleware; the ticket API becomes a tool.
        Tool wiring detail is backend-specific, so we return a placeholder
        descriptor here and let the runtime resolve it.
        """
        return {
            "corpus_collection": collection,
            "ticket_api": tenant.ticket_api,
        }

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

    @staticmethod
    def _build_prompt(tenant: TenantConfig, spec: AgentSpec) -> str:
        return (
            f"You are the {spec.role} for {tenant.name} (tenant={tenant.id}). "
            "Answer customer tickets using only the tenant corpus. "
            "Escalate (ASK) refunds above policy thresholds. "
            "Never access other tenants' data."
        )

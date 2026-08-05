"""Permission-rule construction for a deployed tenant agent.

This is the one place the design doc's API lines up with reality:
``agentscope.permission.PermissionEngine`` genuinely exists in 2.0, with the
``PermissionRule`` / ``PermissionContext`` / ``PermissionMode`` (DEFAULT,
ACCEPT_EDITS, EXPLORE, BYPASS, DONT_ASK) / ``PermissionBehavior`` (ALLOW,
DENY, ASK, PASSTHROUGH) surface the doc described.

Three isolation layers (the FDE's data-leakage defense):
    1. Sandbox        — execution isolation (workspace backend)
    2. Collection     — data isolation (per-tenant vector collection)
    3. PermissionEngine — capability isolation (rule-based allow/deny/ask)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PermissionBlueprint:
    """A framework-neutral description of a tenant's permission rules.

    Translated to real ``PermissionRule`` objects in :meth:`build_engine`.
    """

    tenant_id: str
    allow: list[tuple[str, str | None]] = field(
        default_factory=lambda: [
            # (tool_name, rule_content) — None means "any args"
            ("read_corpus", None),
            ("write_ticket", None),
        ]
    )
    deny: list[tuple[str, str | None]] = field(
        default_factory=lambda: [
            ("access_other_tenant", None),
            ("delete_any", None),
            ("exec_shell", None),
        ]
    )
    ask: list[tuple[str, str | None]] = field(default_factory=list)

    def describe(self) -> str:
        lines = [f"Permission blueprint for tenant {self.tenant_id}:"]
        lines.append("  ALLOW:")
        for tool, content in self.allow:
            lines.append(f"    - {tool}" + (f" ({content})" if content else ""))
        lines.append("  DENY:")
        for tool, content in self.deny:
            lines.append(f"    - {tool}" + (f" ({content})" if content else ""))
        if self.ask:
            lines.append("  ASK (HITL):")
            for tool, content in self.ask:
                lines.append(f"    - {tool}" + (f" ({content})" if content else ""))
        return "\n".join(lines)


def default_blueprint(tenant_id: str) -> PermissionBlueprint:
    """The conservative default an FDE ships on day one."""
    return PermissionBlueprint(
        tenant_id=tenant_id,
        allow=[("read_corpus", None), ("write_ticket", None), ("call_approved_tools", None)],
        deny=[("access_other_tenant", None), ("delete_any", None), ("exec_shell", None)],
        ask=[("refund_high_value", "amount > 1000")],
    )


def build_engine(blueprint: PermissionBlueprint):
    """Construct a real AgentScope ``PermissionEngine`` with the blueprint's rules.

    Lazy-imports agentscope. The engine is constructed empty and rules are
    added one by one via ``add_rule`` — matching the 2.0 API where
    ``PermissionEngine(context)`` takes a ``PermissionContext`` and rules are
    mutable.
    """
    try:
        from agentscope.permission import (  # type: ignore
            PermissionBehavior,
            PermissionContext,
            PermissionEngine,
            PermissionRule,
        )
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Tenant deployment needs the optional 'agentscope' extra: pip install 'fde-scope[agentscope]'"
        ) from exc

    engine = PermissionEngine(PermissionContext())
    behavior_map = {
        "allow": PermissionBehavior.ALLOW,
        "deny": PermissionBehavior.DENY,
        "ask": PermissionBehavior.ASK,
    }
    for severity, rules in (("allow", blueprint.allow), ("deny", blueprint.deny), ("ask", blueprint.ask)):
        for tool_name, rule_content in rules:
            engine.add_rule(
                PermissionRule(
                    tool_name=tool_name,
                    rule_content=rule_content,
                    behavior=behavior_map[severity],
                    source=f"fde_scope:{blueprint.tenant_id}",
                )
            )
    return engine

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

#: ``ApprovalPolicy.mode`` -> AgentScope 2.0 ``PermissionMode`` value. The real
#: enum is imported lazily, so this maps by name and ``permission_mode`` falls
#: back to DEFAULT for anything unknown.
_MODE_NAMES = {
    "conservative": "DEFAULT",  # unmatched calls escalate to a human (ASK)
    "balanced": "DEFAULT",
    "autonomous": "DONT_ASK",  # unattended: a would-be ASK becomes DENY, never a prompt
}


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


# ASK-rule presets per ApprovalPolicy.mode. The policy's only effect on the
# deployed agent is *which* tool calls land in the ASK (HITL) bucket.
_ASK_BALANCED: list[tuple[str, str | None]] = [("refund_high_value", "amount > 1000")]
_ASK_CONSERVATIVE_EXTRA: list[tuple[str, str | None]] = [
    ("write_ticket", "external_customer"),
    ("call_approved_tools", "high_cost"),
]


def default_blueprint(
    tenant_id: str,
    mode: str = "conservative",
    allow_tools: tuple[str, ...] = (),
) -> PermissionBlueprint:
    """The default blueprint an FDE ships on day one, tuned by approval policy.

    ``mode`` (``ApprovalPolicy.mode``) moves only the ASK boundary:
    - ``autonomous``   — no ASK rules; nothing escalates to a human.
    - ``balanced``     — only clearly high-risk actions ask.
    - ``conservative`` — the balanced set plus routine external / high-cost actions.
    Unknown modes fall back to the balanced set.

    ``allow_tools`` are the *actually bound* read-only tool names from the role's
    tool plan. In ``DEFAULT`` mode an unmatched tool call is an ASK, so without
    this the agent would escalate every corpus / connector read it was given.
    """
    ask = list(_ASK_BALANCED)
    if mode == "autonomous":
        ask = []
    elif mode == "conservative":
        ask = ask + _ASK_CONSERVATIVE_EXTRA
    allow_rules: list[tuple[str, str | None]] = [
        ("read_corpus", None),
        ("write_ticket", None),
        ("call_approved_tools", None),
    ]
    allow_rules.extend((tool, None) for tool in allow_tools)
    return PermissionBlueprint(
        tenant_id=tenant_id,
        allow=allow_rules,
        deny=[("access_other_tenant", None), ("delete_any", None), ("exec_shell", None)],
        ask=ask,
    )


def permission_mode(mode: str):
    """Resolve an ``ApprovalPolicy.mode`` to the real ``PermissionMode`` (lazy import)."""
    from agentscope.permission import PermissionMode

    return PermissionMode[_MODE_NAMES.get(mode, "DEFAULT")]


def build_context(blueprint: PermissionBlueprint, mode: str = "conservative"):
    """Build the real ``PermissionContext`` that a deployed ``Agent`` carries.

    This is the part the agent actually enforces: ``Agent.__init__`` builds its
    engine from ``state.permission_context``, so rules written to a detached
    ``PermissionEngine`` never reach it. Lazy-imports agentscope.
    """
    try:
        from agentscope.permission import PermissionBehavior, PermissionContext, PermissionRule
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Tenant deployment needs the optional 'agentscope' extra: pip install 'fde-scope[agentscope]'"
        ) from exc

    behavior_map = {
        "allow": PermissionBehavior.ALLOW,
        "deny": PermissionBehavior.DENY,
        "ask": PermissionBehavior.ASK,
    }
    buckets: dict[str, dict[str, list]] = {"allow": {}, "deny": {}, "ask": {}}
    for severity, rules in (("allow", blueprint.allow), ("deny", blueprint.deny), ("ask", blueprint.ask)):
        for tool_name, rule_content in rules:
            rule = PermissionRule(
                tool_name=tool_name,
                rule_content=rule_content,
                behavior=behavior_map[severity],
                source=f"fde_scope:{blueprint.tenant_id}",
            )
            buckets[severity].setdefault(tool_name, []).append(rule)
    return PermissionContext(
        mode=permission_mode(mode),
        allow_rules=buckets["allow"],
        deny_rules=buckets["deny"],
        ask_rules=buckets["ask"],
    )


def build_engine(blueprint: PermissionBlueprint, mode: str = "conservative"):
    """Construct a real AgentScope ``PermissionEngine`` with the blueprint's rules.

    Thin wrapper over :func:`build_context` for callers that want a standalone
    checker; a deployed agent gets the same context through its state, so use
    :func:`build_context` when wiring one and ``engine.context`` is the same object.
    """
    from agentscope.permission import PermissionEngine

    return PermissionEngine(build_context(blueprint, mode))

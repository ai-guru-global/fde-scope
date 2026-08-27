"""Real AgentScope tool wiring for deployed role agents.

AgentScope 2.0 hands an ``Agent`` its capabilities through a
``agentscope.tool.Toolkit`` of ``ToolBase`` objects — and *only* a Toolkit. Passing
the constructor a plain dict builds without complaint (``Agent`` does not
validate the argument) but leaves the agent with zero callable tools: the first
ReAct turn calls ``toolkit.get_tool_schemas()`` and dies. So the deploy layer
needs two distinct things, and this module keeps them separate:

* :func:`plan_bindings` — pure and framework-free. It answers "which tools will
  this agent get, against which physical source?" so the deployment manifest can
  state it *before* AgentScope is imported, and so core-only mode can report it.
  A source that was never configured is reported as **unbound**, never faked.
* :func:`build_toolkit` — lazy-imports AgentScope and builds the real
  ``Toolkit`` from those bindings.

The role → connector mapping lives in :mod:`fde_scope.deploy.roles`; the physical
whereabouts of each connector's data lives in ``TenantConfig.sources`` (with a
per-agent override in ``AgentSpec.toolkit["sources"]``), because on site the same
role always reads a different customer's system.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fde_scope.config import AgentSpec, TenantConfig

from .roles import canonical_role, connectors_for_role

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fde_scope.corpus import CorpusReport

#: Rows a single tool call may return — keeps one tool result inside the model
#: context instead of dumping a customer's whole table.
MAX_TOOL_ROWS = 50

#: Slugs whose source is implied by an existing tenant field, so a ticket-profile
#: tenant bound to a ticketing connector works without a second config entry.
_IMPLICIT_SOURCE_FIELD = {
    "zammad": "ticket_api",
    "salesforce": "ticket_api",
}


@dataclass(frozen=True)
class ToolBinding:
    """One capability an agent will (or will not) get.

    ``bound=False`` bindings are kept, not dropped — the manifest must tell the
    FDE which role tool is missing and why, otherwise an unconfigured source
    looks like a working agent.
    """

    name: str
    kind: str  # "corpus" | "connector"
    slug: str | None  # connector slug (None for corpus tools)
    source: str | None
    bound: bool
    note: str

    def describe(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "kind": self.kind,
            "connector": self.slug,
            "source": self.source,
            "bound": self.bound,
            "note": self.note,
        }


def resolve_source(tenant: TenantConfig, spec: AgentSpec, slug: str) -> str | None:
    """Where does ``slug``'s data physically live for this agent?

    Precedence: per-agent ``spec.toolkit["sources"]`` → tenant ``sources`` →
    the implicit ticketing field (``ticket_api``) for the two connectors whose
    source *is* a ticket API URL. Anything else stays unbound.
    """
    per_agent = (spec.toolkit or {}).get("sources")
    if isinstance(per_agent, dict) and per_agent.get(slug):
        return str(per_agent[slug])
    if tenant.sources.get(slug):
        return str(tenant.sources[slug])
    field = _IMPLICIT_SOURCE_FIELD.get(slug)
    if field:
        value = getattr(tenant, field, None)
        if value:
            return str(value)
    return None


def plan_bindings(
    tenant: TenantConfig,
    spec: AgentSpec,
    corpus_report: CorpusReport | None = None,
) -> list[ToolBinding]:
    """The agent's capability plan — no AgentScope import, safe in core-only mode."""
    bindings: list[ToolBinding] = []

    if corpus_report is not None:
        bindings.append(
            ToolBinding(
                name="corpus_search",
                kind="corpus",
                slug=None,
                source=tenant.corpus_path,
                bound=True,
                note=f"{corpus_report.total} forged items (real={corpus_report.real}, synthetic={corpus_report.synthetic})",
            )
        )
        bindings.append(
            ToolBinding(
                name="corpus_coverage",
                kind="corpus",
                slug=None,
                source=tenant.corpus_path,
                bound=True,
                note="category distribution + remaining gaps",
            )
        )

    for slug in connectors_for_role(spec.role):
        source = resolve_source(tenant, spec, slug)
        for suffix, note in (
            ("_schema", "column / field discovery"),
            ("_sample", "read a bounded row sample"),
        ):
            bindings.append(
                ToolBinding(
                    name=f"{slug}{suffix}",
                    kind="connector",
                    slug=slug,
                    source=source,
                    bound=bool(source),
                    note=note
                    if source
                    else f"unbound: no source for connector {slug!r} (set tenant sources.{slug} or --connector-source {slug}=…)",
                )
            )
    return bindings


def bound_tools(bindings: list[ToolBinding]) -> list[str]:
    return [b.name for b in bindings if b.bound]


def unbound_tools(bindings: list[ToolBinding]) -> list[str]:
    return [b.name for b in bindings if not b.bound]


# ---------------------------------------------------------------------------
# the real AgentScope object
# ---------------------------------------------------------------------------
def build_toolkit(
    bindings: list[ToolBinding],
    corpus_report: CorpusReport | None = None,
    skills_dirs: list[str] | None = None,
) -> Any:
    """Build a real ``agentscope.tool.Toolkit`` from ``bindings``.

    Every tool is a ``FunctionTool`` wrapping a plain function that talks to the
    tenant's own :class:`~fde_scope.connectors.base.DataConnector` / forged
    corpus — so ``get_tool_schemas()`` advertises them and the model can
    actually call them. Connectors are instantiated *inside* the call, never
    while building, which keeps assembly free of network I/O.

    ``skills_dirs`` are Anthropic-style skill directories (each a ``<slug>/
    SKILL.md`` dir, as produced by :mod:`fde_scope.skills.exporters`) handed to
    the official registration channel — one entry per skill via
    ``Toolkit(skills_or_loaders=[...])`` in the same "basic" group (the loader
    does not scan a parent dir, and there is no ``register_agent_skill()`` in
    2.0).

    Tool functions return an ``agentscope.tool.ToolChunk`` (``FunctionTool``
    normalizes anything else, and a bare ``dict`` would lose the ERROR state the
    agent needs to decide whether to retry or escalate).
    """
    from agentscope.message import TextBlock, ToolResultState
    from agentscope.tool import FunctionTool, ToolChunk, Toolkit

    def _ok(payload: Any) -> Any:
        text = json.dumps(payload, ensure_ascii=False, default=str)
        return ToolChunk(content=[TextBlock(type="text", text=text)], state=ToolResultState.SUCCESS)

    def _err(message: str) -> Any:
        return ToolChunk(content=[TextBlock(type="text", text=message)], state=ToolResultState.ERROR)

    def _corpus_items() -> list[Any]:
        if corpus_report is None:
            return []
        return [*corpus_report.train.items, *corpus_report.eval.items, *corpus_report.test.items]

    def make_corpus_search() -> Any:
        async def corpus_search(query: str = "", category: str = "", limit: int = 10) -> Any:
            """Search the tenant's forged corpus for relevant ticket / event samples.

            Args:
                query (str): keyword to look for in the sample text (case-insensitive).
                category (str): restrict to one corpus category.
                limit (int): maximum samples to return.
            """
            n = max(1, min(int(limit or 10), MAX_TOOL_ROWS))
            hits = []
            for item in _corpus_items():
                if category and item.category != category:
                    continue
                if query and query.lower() not in item.content.lower():
                    continue
                hits.append(
                    {
                        "id": item.id,
                        "content": item.content,
                        "category": item.category,
                        "provenance": item.provenance.value,
                        "quality_score": item.quality_score,
                    }
                )
                if len(hits) >= n:
                    break
            return _ok({"query": query, "category": category, "count": len(hits), "items": hits})

        return corpus_search

    def make_corpus_coverage() -> Any:
        async def corpus_coverage() -> Any:
            """Report the forged corpus's category distribution and the coverage gaps left."""
            if corpus_report is None:
                return _err("no corpus report is attached to this deployment")
            return _ok(
                {
                    "total": corpus_report.total,
                    "real": corpus_report.real,
                    "synthetic": corpus_report.synthetic,
                    "dropped": corpus_report.dropped,
                    "pii_entities_masked": corpus_report.pii_entities_masked,
                    "category_counts": corpus_report.coverage.category_counts,
                    "diversity_index": corpus_report.coverage.diversity_index,
                    "gaps": [gap.model_dump() for gap in corpus_report.coverage.gaps],
                }
            )

        return corpus_coverage

    def make_connector_tools(slug: str, source: str) -> tuple[Any, Any]:
        async def connector_schema() -> Any:
            """Discover the shape of the customer data source behind this tool."""
            from fde_scope.connectors._registry import get as get_connector

            try:
                cls = get_connector(slug)
            except Exception as exc:  # noqa: BLE001 — optional driver missing
                return _err(f"connector {slug!r} is not importable here: {exc}")
            try:
                schema = await asyncio.to_thread(cls(source).discover_schema)
            except Exception as exc:  # noqa: BLE001 — surface the real failure
                return _err(f"{slug} discover_schema failed: {exc}")
            return _ok(
                {
                    "source": schema.source,
                    "row_count": schema.row_count,
                    "categories": schema.detected_categories,
                    "channels": schema.detected_channels,
                    "fields": [
                        {
                            "name": f.name,
                            "type": f.inferred_type,
                            "nullable": f.nullable,
                            "pii_candidate": f.pii_candidate,
                        }
                        for f in schema.fields
                    ],
                }
            )

        async def connector_sample(limit: int = 10) -> Any:
            """Read a small, bounded sample of rows from the customer data source.

            Args:
                limit (int): maximum rows to return.
            """
            from fde_scope.connectors._registry import get as get_connector

            n = max(1, min(int(limit or 10), MAX_TOOL_ROWS))
            try:
                cls = get_connector(slug)
            except Exception as exc:  # noqa: BLE001
                return _err(f"connector {slug!r} is not importable here: {exc}")
            try:
                rows = await asyncio.to_thread(cls(source).extract_sample, n)
            except Exception as exc:  # noqa: BLE001
                return _err(f"{slug} extract_sample failed: {exc}")
            return _ok({"source": source, "connector": slug, "count": len(rows), "rows": rows})

        return connector_schema, connector_sample

    tools: list[Any] = []
    made: set[str] = set()
    for binding in bindings:
        if not binding.bound or binding.name in made:
            continue
        if binding.kind == "corpus":
            func = make_corpus_search() if binding.name == "corpus_search" else make_corpus_coverage()
            tools.append(
                FunctionTool(
                    func, name=binding.name, description=func.__doc__.splitlines()[0], is_read_only=True
                )
            )
        else:
            schema_func, sample_func = make_connector_tools(binding.slug or "", binding.source or "")
            if binding.name.endswith("_schema"):
                tools.append(
                    FunctionTool(
                        schema_func,
                        name=binding.name,
                        description=schema_func.__doc__.splitlines()[0],
                        is_read_only=True,
                    )
                )
            else:
                tools.append(
                    FunctionTool(
                        sample_func,
                        name=binding.name,
                        description=sample_func.__doc__.splitlines()[0],
                        is_read_only=True,
                    )
                )
        made.add(binding.name)
    # Skills ride the same official constructor argument (same "basic" group).
    return Toolkit(tools=tools, skills_or_loaders=list(skills_dirs or []))


def describe_bindings(spec: AgentSpec, bindings: list[ToolBinding]) -> dict[str, Any]:
    """The manifest view of a role's tools: which are live, which are waiting.

    Kept separate from :func:`build_toolkit` so a core-only (or dry-run)
    deploy still reports the same truth the runtime would build.
    """
    return {
        "role_bucket": canonical_role(spec.role),
        "tools": [b.describe() for b in bindings],
        "bound": bound_tools(bindings),
        "unbound": unbound_tools(bindings),
        # Echoed as declared: a plan reports what the runtime would wire,
        # without touching the filesystem.
        "skills_dirs": (spec.toolkit or {}).get("skills_dirs"),
    }

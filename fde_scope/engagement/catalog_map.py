"""Phase → skills-catalog page mapping for guided mode.

``docs/skills-catalog/`` holds ~122 curated Markdown pages organized by zone,
but the pages carry no machine-readable phase slug (only a free-text
「FDE 位点」 line). This module is the hand-curated bridge: it maps each of
the 18 phase slugs to the catalog pages that best explain *how* to do that
phase, with a zone-level fallback.

The mapping lives inside the package (not in the catalog directory) on
purpose: ``scripts/check_skills_catalog.py`` guards the catalog's own format
and README consistency, and adding manifests there would trip that CI gate.

Page references are POSIX-relative routes without the ``.md`` suffix, which
is exactly the hash-route format of the generated portal
(``docs/skills-catalog/site/index.html#/zone-a-pre-engagement/firecrawl-search``,
see ``scripts/build_catalog_site.py``).
"""

from __future__ import annotations

from .phases import Zone

#: GitHub fallback for environments where the catalog portal is not served
#: locally (e.g. an installed wheel without the repo docs/ tree).
_GITHUB_BASE = "https://github.com/ai-guru-global/fde-scope/blob/master/docs/skills-catalog"

#: phase slug → catalog page routes (2-5 pages each, hand-curated).
CATALOG_BY_PHASE: dict[str, tuple[str, ...]] = {
    "qualification": (
        "zone-a-pre-engagement/brainstorming",
        "zone-a-pre-engagement/grill-me",
        "zone-a-pre-engagement/crm-lookup",
    ),
    "site_survey": (
        "zone-a-pre-engagement/firecrawl-search",
        "zone-a-pre-engagement/zread",
        "zone-a-pre-engagement/drawio",
    ),
    "stakeholder_map": (
        "zone-a-pre-engagement/architecture-communicator",
        "zone-a-pre-engagement/crm-lookup",
        "zone-a-pre-engagement/grill-me",
    ),
    "success_criteria": (
        "zone-a-pre-engagement/brainstorming",
        "zone-a-pre-engagement/grill-me",
        "zone-a-pre-engagement/xlsx",
    ),
    "connect": (
        "zone-b-build/attach-db",
        "zone-b-build/mqtt-development",
        "zone-b-build/modbus-debug",
        "zone-b-build/query",
        "zone-b-build/read-file",
    ),
    "corpus": (
        "zone-b-build/huggingface-datasets",
        "zone-b-build/train-sentence-transformers",
        "zone-a-pre-engagement/firecrawl-parse",
        "zone-a-pre-engagement/pdf",
    ),
    "prototype_real_data": (
        "zone-b-build/rag-agent-builder",
        "zone-b-build/building-pydantic-ai-agents",
        "zone-b-build/prompt-engineering-patterns",
        "zone-b-build/langgraph-persistence",
    ),
    "validate": (
        "zone-b-build/evaluating-llms-harness",
        "zone-b-build/phoenix-evals",
        "zone-b-build/mlflow-agent-evaluation",
        "cross-cutting/code-review",
    ),
    "deploy": (
        "zone-c-operationalization/deploy-checklist",
        "zone-b-build/docker-build-deploy",
        "zone-b-build/kubernetes-specialist",
        "zone-b-build/vllm-deploy-docker",
    ),
    "eval": (
        "zone-c-operationalization/llm-evaluation",
        "zone-b-build/evaluating-llms-harness",
        "zone-b-build/phoenix-evals",
        "zone-b-build/wandb-primary",
    ),
    "slo_sla": (
        "zone-c-operationalization/sre-runbooks",
        "zone-c-operationalization/incident-response",
        "zone-c-operationalization/datadog",
        "zone-c-operationalization/grafana-dashboarding",
    ),
    "runbook": (
        "zone-c-operationalization/sre-runbooks",
        "zone-c-operationalization/incident-response",
        "zone-c-operationalization/troubleshooting",
    ),
    "monitoring_drift": (
        "zone-c-operationalization/grafana-dashboarding",
        "zone-c-operationalization/datadog",
        "zone-c-operationalization/sentry-mcp",
        "zone-c-operationalization/firecrawl-monitor",
    ),
    "change_mgmt_training": (
        "zone-d-handoff/shifu",
        "zone-d-handoff/remember",
        "zone-d-handoff/slidev",
        "zone-d-handoff/pptx",
    ),
    "flywheel_productization": (
        "cross-cutting/writing-plans",
        "cross-cutting/create-skill",
        "cross-cutting/skill-discovery",
        "zone-a-pre-engagement/qmind-knowledge",
    ),
    "ops_handoff": (
        "zone-c-operationalization/sre-runbooks",
        "zone-c-operationalization/incident-response",
        "zone-c-operationalization/deploy-checklist",
    ),
    "knowledge_transfer": (
        "zone-d-handoff/document-generate",
        "zone-d-handoff/anthropic-documentation",
        "zone-d-handoff/make-pdf",
        "zone-d-handoff/shifu",
    ),
    "disengage": (
        "zone-d-handoff/document-release",
        "zone-d-handoff/anthropic-documentation",
        "cross-cutting/code-review",
    ),
}

#: Zone-level fallback (entry pages for a whole zone).
CATALOG_BY_ZONE: dict[Zone, tuple[str, ...]] = {
    Zone.PRE_ENGAGEMENT: (
        "zone-a-pre-engagement/brainstorming",
        "zone-a-pre-engagement/grill-me",
        "zone-a-pre-engagement/firecrawl-search",
    ),
    Zone.BUILD: (
        "zone-b-build/rag-agent-builder",
        "zone-b-build/prompt-engineering-patterns",
        "zone-b-build/docker-build-deploy",
    ),
    Zone.OPERATIONALIZATION: (
        "zone-c-operationalization/sre-runbooks",
        "zone-c-operationalization/incident-response",
        "zone-c-operationalization/grafana-dashboarding",
    ),
    Zone.HANDOFF: (
        "zone-d-handoff/document-generate",
        "zone-d-handoff/document-release",
        "zone-d-handoff/make-pdf",
    ),
}


def pages_for_phase(slug: str, *, local: bool = False) -> list[dict]:
    """Catalog pages for one phase, with ready-to-open URLs.

    ``local=True`` produces console-relative portal deep links
    (``/catalog/index.html#/<route>``); otherwise GitHub blob URLs.
    """
    from .phases import phase_by_slug

    routes = CATALOG_BY_PHASE.get(slug)
    if not routes:
        routes = CATALOG_BY_ZONE.get(phase_by_slug(slug).zone, ())
    out = []
    for route in routes:
        title = route.rsplit("/", 1)[-1]
        if local:
            url = f"/catalog/index.html#/{route}"
            url_en = f"/catalog/en/index.html#/{route}"
        else:
            url = f"{_GITHUB_BASE}/{route}.md"
            url_en = url
        out.append({"title": title, "route": route, "url": url, "url_en": url_en})
    return out

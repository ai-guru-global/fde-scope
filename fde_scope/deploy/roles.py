"""Role → data-source binding for multi-agent deployments.

On site an FDE opens three kinds of analyst — **data**, **logs**, **files** —
and each needs the right connectors behind it. ``AgentSpec.role`` is free text
(the CLI accepts ``--agent name:role[:model]`` in any language), so this module
normalizes a role string to a canonical bucket and maps it to the connector
slugs that actually carry that role's data. Unknown roles bind to nothing and
fall back to the tenant corpus alone.

Keeping the mapping here (not hard-coded in the deployer) means the role
vocabulary is one glanceable table and is unit-testable without AgentScope.
"""

from __future__ import annotations

# canonical bucket -> connector type slugs (must exist in connectors._registry)
ROLE_CONNECTORS: dict[str, list[str]] = {
    "data": ["csv", "mysql", "mes"],
    "logs": ["historian", "mqtt_sparkplug", "ros2_bag", "opcua"],
    "files": ["documents"],
}

# substring → bucket; matched against a lower-cased role, so English and the
# Chinese labels the CLI accepts both resolve. Order is irrelevant (buckets are
# disjoint) but we scan deterministically.
_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "data": ("data", "数据分析", "数据库", "database", "sql", "报表"),
    "logs": ("log", "日志", "historian", "时序", "tsdb", "scada", "mqtt", "ros"),
    "files": ("file", "document", "doc", "文件", "文档", "pdf", "资料", "手册"),
}


def canonical_role(role: str) -> str | None:
    """Map a free-text role to a canonical bucket (``data``/``logs``/``files``).

    Returns ``None`` when the role does not clearly name a data source.
    """
    text = (role or "").strip().lower()
    if not text:
        return None
    for bucket, keywords in _ROLE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return bucket
    return None


def connectors_for_role(role: str) -> list[str]:
    """Return the connector slugs bound to ``role`` (empty when unrecognized)."""
    bucket = canonical_role(role)
    return list(ROLE_CONNECTORS[bucket]) if bucket else []

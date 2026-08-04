"""FDE Scope — an AI Forward-Deployed Engineer toolkit.

"72h from raw data to a deployed agent." Built on AgentScope 2.0.

Layered design (see docs/architecture.md):
    Layer 1  connectors  — data ingestion (framework-agnostic)
    Layer 2  corpus      — the corpus forge engine (core differentiation)
    Layer 3  deploy      — multi-tenant deployment (lazy-imports agentscope)
    Layer 4  eval        — delivery evaluation framework
    Layer 5  flywheel    — the data flywheel (lazy-imports agentscope events)

Only the runtime layer (deploy / flywheel) touches AgentScope 2.0; the core
data layer (connectors / corpus / eval) has zero framework dependency so it
runs with zero configuration.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]

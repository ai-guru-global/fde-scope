"""Layer 2 — the corpus forge engine (FDE Scope's core differentiation).

The forge turns raw connector rows into an auditable, gap-aware corpus:

    raw rows
      → normalize → scrub PII → dedup → quality gate      (clean)
      → coverage analysis                                    (measure)
      → targeted synthesis to fill the gaps                  (augment)
      → train/eval/test split                                (deliver)
      → CorpusReport                                         (handoff)

This layer has zero AgentScope dependency. Every stage is a deterministic
function so the v0 runs with no LLM, no API key, no Docker.
"""

from .agents import (
    Deduplication,
    PIIScrub,
    QualityGate,
    SchemaNormalizer,
    build_stages,
)
from .coverage_analyzer import CoverageAnalyzer
from .pipeline import CorpusForge, load_items_jsonl, save_items_jsonl, save_report_json
from .quality_gate import score_item
from .report import render_html, save_html
from .synthesizer import CorpusSynthesizer
from .types import (
    CategoryGap,
    CorpusItem,
    CorpusReport,
    CorpusSplit,
    CoverageReport,
    Provenance,
)

__all__ = [
    "CorpusForge",
    "CoverageAnalyzer",
    "CorpusSynthesizer",
    "PIIScrub",
    "Deduplication",
    "QualityGate",
    "SchemaNormalizer",
    "build_stages",
    "score_item",
    "render_html",
    "save_html",
    "save_report_json",
    "load_items_jsonl",
    "save_items_jsonl",
    "CorpusItem",
    "CorpusReport",
    "CorpusSplit",
    "CoverageReport",
    "CategoryGap",
    "Provenance",
]

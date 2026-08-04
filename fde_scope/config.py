"""Shared configuration models for FDE Scope.

These pydantic models back the YAML templates in ``fde_scope/templates/`` and
are the single source of truth for both the corpus forge and tenant deploy
flows. Keeping them framework-agnostic means the core layer stays runnable
without AgentScope installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class PIIRules(BaseModel):
    """Rules for the PII scrubbing stage of the corpus forge.

    Every entry is a regex pattern; matches are replaced with the placeholder.
    The defaults below cover the most common Chinese PII encountered in
    ticket corpora (phone, email, ID card, bank card) and are overridable via
    ``corpus_config.yaml``.
    """

    patterns: dict[str, str] = Field(
        default_factory=lambda: {
            # Mobile / CN
            r"1[3-9]\d{9}": "[PHONE]",
            # Email
            r"[\w.+-]+@[\w-]+\.[\w.-]+": "[EMAIL]",
            # CN ID card (18-digit, last char X allowed)
            r"\b\d{17}[\dXx]\b": "[IDCARD]",
            # Bank card (16-19 digits)
            r"\b\d{16,19}\b": "[BANKCARD]",
        }
    )
    placeholder: str = "[REDACTED]"


class CorpusConfig(BaseModel):
    """Configuration consumed by :class:`fde_scope.corpus.pipeline.CorpusForge`.

    Mirrors ``templates/corpus_config.yaml``. Every threshold has a sensible
    default so the forge is one call away from running on a raw CSV.
    """

    pii_rules: PIIRules = Field(default_factory=PIIRules)
    dedup_threshold: float = Field(
        0.92,
        ge=0.0,
        le=1.0,
        description="Jaccard similarity at or above which two items are treated as duplicates.",
    )
    quality_min_score: float = Field(
        3.0,
        ge=0.0,
        le=5.0,
        description="Minimum quality score (1-5) for an item to survive the quality gate.",
    )
    # Normalization
    text_field: str = "content"
    category_field: str = "category"
    id_field: str = "id"
    # Coverage analysis — a category with fewer than this many samples is a gap.
    min_samples_per_category: int = 100
    # Synthesis — how many synthetic samples to generate per detected gap.
    synth_per_gap: int = 50
    synth_quality_min_score: float = 3.5
    # Split ratios (train / eval / test).
    split_ratios: tuple[float, float, float] = (0.8, 0.1, 0.1)
    # Scenario profile — selects connectors / KPIs / gates (ticket | manufacturing).
    profile: str = "ticket"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CorpusConfig":
        """Load a CorpusConfig from a YAML file.

        Missing keys fall back to the model defaults, so a minimal config
        (or even an empty file) is valid.
        """
        import yaml

        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)


class ApprovalPolicy(BaseModel):
    """How aggressively the deployed agent escalates to a human.

    Maps to AgentScope 2.0's HITL event flow: the agent emits a
    ``RequireUserConfirmEvent`` whenever a tool call resolves to ``ASK``; this
    policy governs *which* tool calls land in that bucket.
    """

    mode: str = "conservative"  # conservative | balanced | autonomous
    timeout_seconds: int = 300


class TenantConfig(BaseModel):
    """Per-tenant deployment descriptor.

    Mirrors ``templates/tenant_config.yaml``. The fields the FDE hands to the
    deploy step are intentionally minimal — everything else is derived or
    defaulted.
    """

    id: str
    name: str
    model: str = "qwen-max"
    corpus_path: Optional[str] = None
    ticket_api: Optional[str] = None
    resource_quota: str = "2cpu-4gb"
    profile: str = "ticket"  # ticket | manufacturing
    approval_policy: ApprovalPolicy = Field(default_factory=ApprovalPolicy)
    dashboard_config: dict = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TenantConfig":
        import yaml

        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)

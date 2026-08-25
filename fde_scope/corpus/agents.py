"""The forge stages — rule-based v0 implementations.

The original design doc named these ``PIIScrubAgent`` / ``DeduplicationAgent`` /
``QualityGateAgent`` / ``SchemaNormalizerAgent`` and composed them inside an
AgentScope 1.0 ``SequentialPipeline``. Neither construct exists in AgentScope
2.0 (pipelines were removed; the unified ``Agent`` + ``MiddlewareBase`` is the
2.0 model). Here they are plain, deterministic callables — which is the honest
v0: rule-based, zero-LLM, fully testable. The LLM-backed v1 keeps the same
function signature and swaps only the internals.

Each stage takes and returns ``list[CorpusItem]`` (the last stage, dedup, also
takes the config threshold). This uniform shape is what lets the forge chain
them as a plain Python function pipeline — see ``pipeline.py``.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from .types import CorpusItem

if TYPE_CHECKING:
    from fde_scope.config import CorpusConfig
    from fde_scope.llm import MiMoClient


# ---------------------------------------------------------------------------
# Stage 1: PII scrubbing
# ---------------------------------------------------------------------------
class PIIScrub:
    """Mask personally identifiable information via configurable regex rules."""

    def __init__(self, patterns: dict[str, str], placeholder: str = "[REDACTED]") -> None:
        # Each rule: {regex: label}. A match is replaced with placeholder+label.
        self._compiled = [(re.compile(p), label) for p, label in patterns.items()]
        self.placeholder = placeholder
        self.masked_count = 0

    def __call__(self, items: list[CorpusItem]) -> list[CorpusItem]:
        out: list[CorpusItem] = []
        for item in items:
            content = item.content
            masked = 0
            for rx, label in self._compiled:

                def _sub(m: re.Match, _label: str = label) -> str:
                    return f"{self.placeholder}({_label})"

                new_content, n = rx.subn(_sub, content)
                if n:
                    content = new_content
                    masked += n
            self.masked_count += masked
            out.append(item.with_trace("pii_scrub", content=content) if masked else item)
        return out


# ---------------------------------------------------------------------------
# Stage 2: Semantic-ish deduplication (hash + Jaccard)
# ---------------------------------------------------------------------------
class Deduplication:
    """Remove exact duplicates (hash) and near-duplicates (Jaccard similarity).

    Exact dupes are caught by a content hash for O(n). Near-dupes use token-set
    Jaccard similarity against the kept set — O(n²) but fine for the v0 sample
    sizes an FDE inspects on site.
    """

    def __init__(self, threshold: float = 0.92) -> None:
        self.threshold = threshold
        self.dropped_count = 0

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha1(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _tokens(content: str) -> set[str]:
        return {t for t in re.split(r"\s+", content.lower().strip()) if t}

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union else 0.0

    def __call__(self, items: list[CorpusItem]) -> list[CorpusItem]:
        kept: list[CorpusItem] = []
        seen_hashes: set[str] = set()
        kept_tokens: list[set[str]] = []

        for item in items:
            h = self._hash(item.content)
            if h in seen_hashes:
                self.dropped_count += 1
                continue
            tokens = self._tokens(item.content)
            # near-dup check against what we've already kept
            is_near_dup = False
            if tokens:
                for prev in kept_tokens:
                    if self._similar(tokens, prev):
                        is_near_dup = True
                        break
            if is_near_dup:
                self.dropped_count += 1
                continue
            seen_hashes.add(h)
            kept_tokens.append(tokens)
            kept.append(item.with_trace("dedup"))
        return kept

    def _similar(self, a: set[str], b: set[str]) -> bool:
        # Fast path: tiny token sets rarely collide; skip the ratio calc.
        if len(a) <= 2 and len(b) <= 2:
            return False
        return self._jaccard(a, b) >= self.threshold


# ---------------------------------------------------------------------------
# Stage 3: Quality gate
# ---------------------------------------------------------------------------
# Matches PIIScrub's default masking output, e.g. "[REDACTED]([PHONE])".
_REDACTION_RE = re.compile(r"\[REDACTED\]\([^)]*\)")


class QualityGate:
    """Score each item 1-5 on simple, transparent rules; drop below threshold.

    v0 rubric (no LLM):
        + length in a sane band (not empty, not a novel)
        + has a recognizable category
        + presence of question/issue keywords
        - gibberish / all-punctuation
        - pure redaction residue
    """

    def __init__(self, min_score: float = 3.0, llm: MiMoClient | None = None) -> None:
        self.min_score = min_score
        self.llm = llm
        self.dropped_count = 0

    @staticmethod
    def _score(item: CorpusItem) -> float:
        content = item.content.strip()
        score = 0.0
        length = len(content)
        # length band
        if 20 <= length <= 2000:
            score += 2.0
        elif 5 <= length < 20 or 2000 < length <= 8000:
            score += 1.0
        # category present
        if item.category and item.category != "uncategorized":
            score += 1.0
        # alphanumeric ratio (penalize gibberish)
        alnum = sum(c.isalnum() for c in content)
        ratio = alnum / max(length, 1)
        if ratio >= 0.6:
            score += 1.0
        elif ratio >= 0.3:
            score += 0.5
        # issue-signal keywords
        if any(kw in content.lower() for kw in ("?", "麻烦", "问题", "退款", "无法", "help", "error")):
            score += 1.0
        # pure redaction residue — content reduced to nothing but masking
        # placeholders (matches PIIScrub's default "[REDACTED](label)" shape)
        # carries no signal; push it below any sane gate threshold.
        residue = _REDACTION_RE.sub("", content)
        if not re.search(r"\w", residue):
            score -= 2.0
        return min(score, 5.0)

    def __call__(self, items: list[CorpusItem]) -> list[CorpusItem]:
        # Batch scoring stays rule-based: LLM-scoring a whole forge would
        # burn the token budget. LLM scoring is available per-item via
        # :meth:`score_text` (used for freshly synthesized samples).
        out: list[CorpusItem] = []
        for item in items:
            q = self._score(item)
            scored = item.with_trace("quality_gate", quality_score=q)
            if q >= self.min_score:
                out.append(scored)
            else:
                self.dropped_count += 1
        return out

    def score_text(self, content: str, category: str = "") -> float:
        """Score raw text 1-5 — rules, upgraded by the LLM when available.

        The LLM path is best-effort: on any failure (no key, network, bad
        output) the deterministic rule score is returned, so callers always
        get a number in [1, 5].
        """
        rule = self._score(CorpusItem(id="x", content=content, category=category))
        if self.llm is not None and self.llm.available:
            try:
                llm_score = self._score_llm(content)
                if llm_score is not None:
                    return llm_score
            except Exception:
                pass
        return rule

    def _score_llm(self, content: str) -> float | None:
        """Ask the LLM for a 1-5 integer quality score (None on bad output)."""
        if self.llm is None:
            return None
        raw = self.llm.complete(
            f"请给这条客服语料打质量分（1-5 整数，5 最好，考虑完整性与信息量）：\n\n"
            f"{content[:500]}\n\n只输出一个数字。",
            temperature=0.0,
            max_tokens=16,
        )
        m = re.search(r"\d+", raw)
        if not m:
            return None
        return min(max(float(m.group(0)), 1.0), 5.0)


# ---------------------------------------------------------------------------
# Stage 4: Schema normalization
# ---------------------------------------------------------------------------
class SchemaNormalizer:
    """Coerce connector rows into the canonical CorpusItem shape.

    This stage runs *first* conceptually (raw dict → CorpusItem), but lives
    here for cohesion. It maps connector field names to the canonical ones
    defined in :class:`CorpusConfig` and stamps an id when one is missing.
    """

    def __init__(
        self, text_field: str = "content", category_field: str = "category", id_field: str = "id"
    ) -> None:
        self.text_field = text_field
        self.category_field = category_field
        self.id_field = id_field

    def normalize_row(self, row: dict, index: int) -> CorpusItem:
        content = str(row.get(self.text_field, "") or "").strip()
        category = str(row.get(self.category_field, "uncategorized") or "uncategorized")
        channel = str(row.get("channel", "unknown") or "unknown")
        raw_id = row.get(self.id_field)
        item_id = str(raw_id) if raw_id not in (None, "") else f"item-{index:06d}"
        return CorpusItem(
            id=item_id,
            content=content,
            category=category,
            channel=channel,
            trace=["normalize"],
            metadata={
                k: v
                for k, v in row.items()
                if k not in (self.text_field, self.category_field, self.id_field, "channel")
            },
        )

    def __call__(self, rows: list[dict]) -> list[CorpusItem]:
        return [self.normalize_row(row, i) for i, row in enumerate(rows)]


# Convenience factory: build all stages from a CorpusConfig in one call.
def build_stages(
    config: CorpusConfig, llm: MiMoClient | None = None
) -> tuple[PIIScrub, Deduplication, QualityGate]:
    """Instantiate the three post-normalization stages from a config."""
    return (
        PIIScrub(config.pii_rules.patterns, config.pii_rules.placeholder),
        Deduplication(config.dedup_threshold),
        QualityGate(config.quality_min_score, llm=llm),
    )

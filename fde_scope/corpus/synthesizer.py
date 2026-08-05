"""Corpus synthesizer — fill the coverage gaps.

STATUS: rule-based v0 (template + synonym substitution). The real LLM-backed
v1 keeps the same ``fill_gaps`` signature and swaps internals.

The contract is the differentiator: the synthesizer *only* fills gaps the
coverage analyzer identified. It never generates "to pad the count" — every
synthetic item is tied to a specific ``CategoryGap`` and passes the quality
gate before it's admitted. That's what makes the corpus defensible to a
customer.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .agents import QualityGate
from .types import CategoryGap, CorpusItem, Provenance

if TYPE_CHECKING:
    pass


# Tiny paraphrase dictionary — enough to produce genuinely varied samples in
# the v0 rule mode. The LLM v1 replaces this entirely.
_PARAPHRASES: dict[str, list[str]] = {
    "退款": ["申请退款", "我想退款", "把钱退给我", "麻烦办理退款"],
    "退货": ["我要退货", "申请退货", "麻烦帮我退货", "商品想退掉"],
    "无法": ["用不了", "不能使用", "没法", "始终无法"],
    "问题": ["故障", "异常", "报错", "情况"],
    "help": ["assist", "support", "guidance", "advice"],
}

_OPENERS = [
    "你好，",
    "您好，",
    "Hi, ",
    "麻烦一下，",
    "请问一下，",
    "",
    "您好，咨询一下：",
    "客服你好，",
]

_CLOSERS = [
    "麻烦尽快处理。",
    "希望能帮忙解决。",
    "thanks.",
    "感谢！",
    "请问怎么处理？",
    "",
    "等您回复。",
]


class CorpusSynthesizer:
    """Generate synthetic samples to fill specific coverage gaps."""

    def __init__(
        self,
        strategies: list[str] | None = None,
        quality_gate: QualityGate | None = None,
        seed: int = 42,
    ) -> None:
        self.strategies = strategies or ["paraphrase", "adversarial", "multi_turn", "emotion_escalation"]
        self.quality_gate = quality_gate or QualityGate(min_score=2.5)
        self._rng = random.Random(seed)

    # -- public API -------------------------------------------------------------
    def fill_gaps(
        self,
        real_items: list[CorpusItem],
        gaps: list[CategoryGap],
        per_gap_cap: int | None = None,
    ) -> list[CorpusItem]:
        """Synthesize enough items to close each gap, gated by quality.

        ``per_gap_cap`` overrides each gap's ``shortfall`` (useful to bound
        synthesis cost in v0).
        """
        if not gaps:
            return []

        synthetic: list[CorpusItem] = []
        for gap in gaps:
            seeds = [i for i in real_items if i.category == gap.category]
            to_make = per_gap_cap if per_gap_cap is not None else gap.shortfall
            made = self._synthesize_category(gap.category, seeds, to_make)
            synthetic.extend(made)
        return synthetic

    # -- internals --------------------------------------------------------------
    def _synthesize_category(
        self,
        category: str,
        seeds: list[CorpusItem],
        count: int,
    ) -> list[CorpusItem]:
        out: list[CorpusItem] = []
        if count <= 0:
            return out
        # If we have seed items, mutate them; otherwise emit templated items.
        base_texts = [s.content for s in seeds] if seeds else [self._template(category)]
        attempts = 0
        max_attempts = count * 5 + 10
        while len(out) < count and attempts < max_attempts:
            attempts += 1
            base = self._rng.choice(base_texts)
            text = self._mutate(base, strategy=self._rng.choice(self.strategies))
            item = CorpusItem(
                id=f"syn-{category}-{len(out):04d}",
                content=text,
                category=category,
                channel=self._rng.choice(["email", "chat", "phone"]) if seeds else "synthetic",
                quality_score=self.quality_gate._score(CorpusItem(id="x", content=text, category=category)),
                provenance=Provenance.SYNTHETIC,
                trace=[f"synthesize:{self.strategies[0]}"],
            )
            # Only admit items that clear a lowered gate; v0 is permissive.
            if item.quality_score >= self.quality_gate.min_score:
                out.append(item)
        return out

    def _mutate(self, text: str, strategy: str) -> str:
        if strategy == "paraphrase":
            return self._paraphrase(text)
        if strategy == "adversarial":
            return self._adversarial(text)
        if strategy == "multi_turn":
            return self._multi_turn(text)
        if strategy == "emotion_escalation":
            return self._emotion(text)
        return text

    def _paraphrase(self, text: str) -> str:
        for src, variants in _PARAPHRASES.items():
            if src in text:
                text = text.replace(src, self._rng.choice(variants), 1)
                break
        return f"{self._rng.choice(_OPENERS)}{text}{self._rng.choice(_CLOSERS)}"

    def _adversarial(self, text: str) -> str:
        # Inject an edge-case signal so adversarial samples are recognizable.
        prefix = self._rng.choice(["紧急：", "已投诉过：", "第三次反馈：", "URGENT: "])
        return f"{prefix}{text}"

    def _multi_turn(self, text: str) -> str:
        return f"（上次回复没有解决）{text} 还是同样的问题。"

    def _emotion(self, text: str) -> str:
        suffix = self._rng.choice(["真的很失望。", "太糟糕了。", "I'm very frustrated!", "强烈不满。"])
        return f"{text} {suffix}"

    def _template(self, category: str) -> str:
        return f"关于「{category}」的咨询，请问怎么处理？需要协助。"

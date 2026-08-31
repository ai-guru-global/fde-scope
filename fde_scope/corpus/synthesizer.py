"""Corpus synthesizer — fill the coverage gaps.

STATUS: rule-based v0 (template + synonym substitution) with an optional
LLM-backed path. The LLM v1 keeps the same ``fill_gaps`` signature and swaps
internals: when an ``llm`` client is available, each gap is synthesized by
the model (realistic, category-specific samples); on any LLM failure the
rule-based path takes over, so a forge never dies on a flaky endpoint.

The contract is the differentiator: the synthesizer *only* fills gaps the
coverage analyzer identified. It never generates "to pad the count" — every
synthetic item is tied to a specific ``CategoryGap`` and passes the quality
gate before it's admitted. That's what makes the corpus defensible to a
customer.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from typing import TYPE_CHECKING

from .agents import QualityGate
from .types import CategoryGap, ConceptGap, CorpusItem, Provenance

if TYPE_CHECKING:
    from fde_scope.llm import MiMoClient
    from fde_scope.ontology.extract import ConceptExtractor


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
    """Generate synthetic samples to fill specific coverage gaps.

    Pass ``llm`` (a :class:`~fde_scope.llm.MiMoClient`) to enable the
    LLM-backed path; without it, or when the LLM call fails, the rule-based
    v0 strategies are used.
    """

    def __init__(
        self,
        strategies: list[str] | None = None,
        quality_gate: QualityGate | None = None,
        seed: int = 42,
        llm: MiMoClient | None = None,
    ) -> None:
        self.strategies = strategies or ["paraphrase", "adversarial", "multi_turn", "emotion_escalation"]
        self.quality_gate = quality_gate or QualityGate(min_score=2.5)
        self.llm = llm
        self._rng = random.Random(seed)

    # -- public API -------------------------------------------------------------
    def fill_gaps(
        self,
        real_items: list[CorpusItem],
        gaps: list[CategoryGap],
        per_gap_cap: int | None = None,
        concept_gaps: list[ConceptGap] | None = None,
        extractor: ConceptExtractor | None = None,
    ) -> list[CorpusItem]:
        """Synthesize enough items to close each gap, gated by quality.

        ``per_gap_cap`` bounds each gap's ``shortfall`` (useful to cap
        synthesis cost in v0) — it never synthesizes *more* than the gap
        actually needs.

        ``concept_gaps`` (with an ``extractor`` for ancestor resolution)
        enables ontology-aware synthesis: each concept gap is filled by
        mutating the real items annotated with that concept. A concept gap
        with no such anchor is skipped — no real evidence, no fabricated
        samples.
        """
        synthetic: list[CorpusItem] = []
        for gap in gaps:
            seeds = [i for i in real_items if i.category == gap.category]
            to_make = min(per_gap_cap, gap.shortfall) if per_gap_cap is not None else gap.shortfall
            made = self._synthesize_category(gap.category, seeds, to_make)
            synthetic.extend(made)
        for cgap in concept_gaps or []:
            if cgap.shortfall <= 0:
                continue
            seeds = [i for i in real_items if cgap.concept in i.metadata.get("ontology_concepts", [])]
            if not seeds:
                continue
            to_make = min(per_gap_cap, cgap.shortfall) if per_gap_cap is not None else cgap.shortfall
            ancestors = extractor.ancestors(cgap.concept) if extractor is not None else []
            synthetic.extend(self._synthesize_concept(cgap, seeds, to_make, ancestors))
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
        # LLM path first: realistic category-specific samples; any failure
        # (no key, network, bad JSON) falls through to the rule path.
        if self.llm is not None and self.llm.available:
            try:
                # Enforce the same cap + quality gate as the rule path. The
                # gate runs before the cap: truncating first would waste good
                # samples whenever the model leads with junk (and low-quality
                # strings would bypass the forge's contract).
                texts = self._synthesize_llm(category, seeds, count)
                seen = {s.content for s in seeds}
                for text in texts:
                    if len(out) >= count:
                        break
                    if text in seen:
                        continue
                    seen.add(text)
                    score = self.quality_gate.score_text(text, category=category)
                    if score < self.quality_gate.min_score:
                        continue
                    out.append(
                        CorpusItem(
                            id=f"syn-{category}-{len(out):04d}",
                            content=text,
                            category=category,
                            channel=self._rng.choice(["email", "chat", "phone"]) if seeds else "synthetic",
                            quality_score=score,
                            provenance=Provenance.SYNTHETIC,
                            trace=["synthesize:llm"],
                        )
                    )
                if out:
                    return out
            except Exception:
                # LLM unavailable/failed — fall back to rules below.
                out = []
        # If we have seed items, mutate them; otherwise emit templated items.
        base_texts = [s.content for s in seeds] if seeds else [self._template(category)]
        # The v0 mutation space is small, so the same text can come up again.
        # Synthetic items bypass the forge's dedup stage — dedupe here instead
        # (seed texts included, since a mutation can be a no-op).
        seen = {s.content for s in seeds}
        attempts = 0
        max_attempts = count * 5 + 10
        while len(out) < count and attempts < max_attempts:
            attempts += 1
            base = self._rng.choice(base_texts)
            strategy = self._rng.choice(self.strategies)
            text = self._mutate(base, strategy=strategy)
            if text in seen:
                continue
            seen.add(text)
            item = CorpusItem(
                id=f"syn-{category}-{len(out):04d}",
                content=text,
                category=category,
                channel=self._rng.choice(["email", "chat", "phone"]) if seeds else "synthetic",
                quality_score=self.quality_gate._score(CorpusItem(id="x", content=text, category=category)),
                provenance=Provenance.SYNTHETIC,
                trace=[f"synthesize:{strategy}"],
            )
            # Only admit items that clear a lowered gate; v0 is permissive.
            if item.quality_score >= self.quality_gate.min_score:
                out.append(item)
        return out

    def _synthesize_concept(
        self,
        gap: ConceptGap,
        seeds: list[CorpusItem],
        count: int,
        ancestors: list[str],
    ) -> list[CorpusItem]:
        """Rule-only synthesis for one concept gap (deterministic, no LLM)."""
        out: list[CorpusItem] = []
        if count <= 0:
            return out
        categories: Counter[str] = Counter(s.category for s in seeds)
        category = categories.most_common(1)[0][0]
        concepts = [*ancestors, gap.concept]
        base_texts = [s.content for s in seeds]
        seen = set(base_texts)
        attempts = 0
        max_attempts = count * 5 + 10
        while len(out) < count and attempts < max_attempts:
            attempts += 1
            base = self._rng.choice(base_texts)
            strategy = self._rng.choice(self.strategies)
            text = self._mutate(base, strategy=strategy)
            if text in seen:
                continue
            seen.add(text)
            score = self.quality_gate._score(CorpusItem(id="x", content=text, category=category))
            if score < self.quality_gate.min_score:
                continue
            out.append(
                CorpusItem(
                    id=f"syn-{gap.concept.replace(':', '-')}-{len(out):04d}",
                    content=text,
                    category=category,
                    channel=self._rng.choice(["email", "chat", "phone"]),
                    quality_score=score,
                    provenance=Provenance.SYNTHETIC,
                    metadata={"ontology_concepts": concepts},
                    trace=["synthesize:concept"],
                )
            )
        return out

    def _synthesize_llm(self, category: str, seeds: list[CorpusItem], count: int) -> list[str]:
        """Ask the LLM for ``count`` realistic samples for one category.

        Returns a list of texts (may be shorter than requested). Raises on
        transport/protocol errors so the caller can fall back to rules.
        """
        seed_block = "\n".join(f"- {s.content[:120]}" for s in seeds[:5])
        seed_part = f"\n\n参考同类样本（风格模仿，不要照抄）：\n{seed_block}" if seed_block else ""
        if self.llm is None:
            raise RuntimeError("LLM not configured")
        prompt = (
            f"你是客服语料工程师。请为类别「{category}」生成 {count} 条真实感的客户诉求样本"
            f"（工单/聊天/电话转写风格，每条 15-120 字，彼此不同）。"
            f"只输出 JSON 字符串数组，不要其他内容。{seed_part}"
        )
        raw = self.llm.complete(prompt, temperature=0.9, max_tokens=2048)
        return self._parse_json_list(raw)

    @staticmethod
    def _parse_json_list(raw: str) -> list[str]:
        """Parse a JSON string array, tolerating markdown fences / trailing text."""
        text = raw.strip()
        # Strip ```json ... ``` fences if present.
        fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if fence:
            text = fence.group(1)
        else:
            # Last-resort: grab the first [...] block.
            bracket = re.search(r"\[.*\]", text, re.DOTALL)
            if bracket:
                text = bracket.group(0)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned non-JSON list: {raw[:200]!r}") from exc
        if not isinstance(parsed, list):
            raise ValueError(f"LLM returned non-list JSON: {raw[:200]!r}")
        # Only keep strings — str() on nested lists/dicts would admit Python
        # repr garbage ("['a', 'b']") into the corpus.
        return [s.strip() for s in parsed if isinstance(s, str) and s.strip()]

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

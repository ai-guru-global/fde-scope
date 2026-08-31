"""概念抽取器：SKOS match_keywords 规则命中 + 祖先链并入 + narrower 闭包。

LLM 诚实原则：``annotate`` 的 ``llm`` 为可选；调用失败一律回退规则路径，
且来源标签回退为 ``rule`` —— trace 里绝不声称 LLM 参与过。
"""

from __future__ import annotations

import json

from ..llm import LLMError, MiMoClient
from .models import Concept, OntologySchema


class ConceptExtractor:
    """对一个 schema 内全部概念做关键词匹配与层级运算。"""

    def __init__(self, schema: OntologySchema) -> None:
        self._concepts: dict[str, Concept] = {}
        for scheme in schema.concept_schemes:
            for concept in scheme.concepts:
                self._concepts.setdefault(concept.curie, concept)

    # -- 规则抽取 ---------------------------------------------------------------
    def extract(self, text: str) -> list[str]:
        """关键词命中（大小写不敏感），祖先链随命中并入；声明顺序、去重。"""
        lowered = text.lower()
        out: list[str] = []
        seen: set[str] = set()

        def push(curie: str) -> None:
            if curie not in seen:
                seen.add(curie)
                out.append(curie)

        for curie, concept in self._concepts.items():
            if concept.deprecated:
                continue
            if any(kw and kw.lower() in lowered for kw in concept.match_keywords):
                for anc in self.ancestors(curie):
                    push(anc)
                push(curie)
        return out

    def annotate(self, text: str, *, llm: MiMoClient | None = None) -> tuple[list[str], str]:
        """返回（概念 CURIE 列表, 来源标签 ``rule``|``llm``）。

        llm 缺失/不可用/调用失败时走规则路径并如实标 ``rule``。
        """
        hits = self.extract(text)
        if llm is None or not llm.available:
            return hits, "rule"
        try:
            extra = self._llm_labels(text, llm)
        except LLMError:
            return hits, "rule"
        merged = list(hits)
        for curie in extra:
            if curie not in merged:
                merged.append(curie)
        return merged, "llm"

    # -- 层级运算 ---------------------------------------------------------------
    def ancestors(self, curie: str) -> list[str]:
        """沿 skos:broader 向上走到根；返回从直接父概念到根的链，不含自身。"""
        out: list[str] = []
        seen = {curie}
        cur = curie
        while True:
            concept = self._concepts.get(cur)
            if concept is None:
                break
            parents = [b for b in concept.broader if b not in seen]
            if not parents:
                break
            seen.add(parents[0])
            out.append(parents[0])
            cur = parents[0]
        return out

    def expand(self, curie: str) -> set[str]:
        """自身 + 全部 narrower 后代的闭包；未知 CURIE 返回仅含自身。"""
        out = {curie}
        frontier = [curie]
        while frontier:
            cur = frontier.pop()
            for cand, concept in self._concepts.items():
                if cand not in out and cur in concept.broader:
                    out.add(cand)
                    frontier.append(cand)
        return out

    # -- LLM 辅助 ---------------------------------------------------------------
    def _llm_labels(self, text: str, llm: MiMoClient) -> list[str]:
        catalog = "\n".join(
            f"- {c.curie}: {c.label_zh or c.label}" for c in self._concepts.values() if not c.deprecated
        )
        prompt = (
            "从下面的概念目录中选出文本所属的概念，只输出 JSON 数组（CURIE 字符串），"
            "没有合适概念则输出 []。\n\n概念目录：\n" + catalog + "\n\n文本：" + text
        )
        raw = llm.complete(prompt, temperature=0.0, max_tokens=256)
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end <= start:
            raise LLMError(f"MiMo annotation output is not a JSON array: {raw[:200]!r}")
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"MiMo annotation output is not valid JSON: {raw[:200]!r}") from exc
        if not isinstance(data, list):
            raise LLMError(f"MiMo annotation output is not a list: {raw[:200]!r}")
        return [c for c in data if isinstance(c, str) and c in self._concepts]

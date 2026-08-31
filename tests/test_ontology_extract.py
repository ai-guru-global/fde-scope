"""P2.2 概念抽取器：规则命中 + 祖先链 + expand 闭包。

覆盖规格 docs/superpowers/specs/2026-08-31-ontology-module-design.md §11 P2 行
（规则概念注解、LLM 失败回退不声称 LLM）。
"""

from __future__ import annotations

from fde_scope.llm import LLMError
from fde_scope.ontology.extract import ConceptExtractor
from fde_scope.ontology.models import OntologySchema
from fde_scope.ontology.store import OntologyStore


class _FakeLLM:
    """离线假客户端：available 控制可用性，reply=None 时 complete 抛 LLMError。"""

    def __init__(self, *, available: bool = True, reply: str | None = None) -> None:
        self._reply = reply
        self.available = available

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        if self._reply is None:
            raise LLMError("boom")
        return self._reply


def _extractor() -> ConceptExtractor:
    schema = OntologyStore().load_schema("fde-corpus-taxonomy")
    assert schema is not None, "builtin fde-corpus-taxonomy missing"
    return ConceptExtractor(schema)


def _taxonomy() -> OntologySchema:
    schema = OntologyStore().load_schema("fde-corpus-taxonomy")
    assert schema is not None, "builtin fde-corpus-taxonomy missing"
    return schema


def test_extract_hits_chinese_and_english_keywords() -> None:
    ex = _extractor()
    assert "fde:cc-billing-refund" in ex.extract("我想申请退款，订单号 123")
    assert "fde:cc-outage" in ex.extract("Service is down, outage confirmed")


def test_extract_case_insensitive_ascii() -> None:
    ex = _extractor()
    assert "fde:cc-billing-invoice" in ex.extract("Please send me the INVOICE")


def test_extract_returns_ancestor_chain() -> None:
    ex = _extractor()
    got = ex.extract("麻烦帮我办理退款")
    assert "fde:cc-billing-refund" in got
    assert "fde:cc-billing" in got  # 祖先随命中并入


def test_extract_no_hit_returns_empty() -> None:
    ex = _extractor()
    assert ex.extract("今天天气不错") == []


def test_ancestors_walks_broader_chain() -> None:
    ex = _extractor()
    assert ex.ancestors("fde:cc-billing-refund") == ["fde:cc-billing"]
    assert ex.ancestors("fde:cc-billing") == []


def test_expand_concept_closure() -> None:
    ex = _extractor()
    got = ex.expand("fde:cc-billing")
    assert {"fde:cc-billing", "fde:cc-billing-refund", "fde:cc-billing-invoice"} <= got


def test_expand_unknown_curie_is_self_only() -> None:
    ex = _extractor()
    assert ex.expand("fde:nonexistent") == {"fde:nonexistent"}


def test_taxonomy_loads() -> None:
    assert _taxonomy().concept_schemes


# -- LLM 回退诚实性 -------------------------------------------------------------


def test_annotate_llm_failure_falls_back_to_rule() -> None:
    ex = _extractor()
    got, source = ex.annotate("麻烦帮我办理退款", llm=_FakeLLM())
    assert source == "rule"
    assert "fde:cc-billing-refund" in got


def test_annotate_llm_success_merges_and_labels_llm() -> None:
    ex = _extractor()
    got, source = ex.annotate("随便说点别的", llm=_FakeLLM(reply='["fde:cc-quality"]'))
    assert source == "llm"
    assert "fde:cc-quality" in got


def test_annotate_unavailable_llm_is_rule() -> None:
    ex = _extractor()
    got, source = ex.annotate("我想申请退款", llm=_FakeLLM(available=False))
    assert source == "rule"
    assert "fde:cc-billing-refund" in got

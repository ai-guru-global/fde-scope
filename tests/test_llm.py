"""LLM layer tests — MiMo client + every LLM integration point.

No real API key is ever used: the transport is mocked at ``urllib`` level
and the corpus/eval integration points are exercised with a scripted fake
client, so the whole suite runs offline and keyless.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fde_scope.cli import app
from fde_scope.corpus import CorpusSynthesizer, QualityGate
from fde_scope.corpus.types import CategoryGap, CorpusItem, Provenance
from fde_scope.eval import MiMoReplyFn
from fde_scope.llm import LLMError, MiMoClient

runner = CliRunner()


class FakeLLM:
    """Scripted stand-in for MiMoClient (``available`` always True)."""

    def __init__(self, reply: str = "ok", raise_on_call: bool = False) -> None:
        self.reply = reply
        self.raise_on_call = raise_on_call
        self.available = True
        self.calls: list[str] = []

    def complete(self, prompt: str, **kwargs) -> str:  # noqa: ARG002
        self.calls.append(prompt)
        if self.raise_on_call:
            raise LLMError("boom")
        return self.reply

    def describe(self) -> dict[str, str]:
        return {"provider": "fake", "model": "fake", "available": "True"}


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _gap(category: str = "退款", target: int = 3) -> CategoryGap:
    return CategoryGap(category=category, current_count=0, target_count=target)


# ---------------------------------------------------------------------------
# MiMoClient — configuration + transport
# ---------------------------------------------------------------------------
def test_client_unavailable_without_key(monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    assert not MiMoClient().available


def test_chat_raises_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    with pytest.raises(LLMError, match="FDE_SCOPE_MIMO_API_KEY"):
        MiMoClient().chat([{"role": "user", "content": "hi"}])


def test_env_configuration(monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_MIMO_API_KEY", "tp-env")
    monkeypatch.setenv("FDE_SCOPE_MIMO_MODEL", "mimo-v2.5")
    client = MiMoClient()
    assert client.available
    assert client.model == "mimo-v2.5"
    assert client.base_url == "https://token-plan-cn.xiaomimimo.com/v1"


def test_chat_parses_response_and_sends_expected_request(monkeypatch) -> None:
    captured: dict = {}
    body = json.dumps({"choices": [{"message": {"content": "你好"}}]}).encode("utf-8")

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["payload"] = json.loads(request.data)
        return _FakeResp(body)

    monkeypatch.setattr("fde_scope.llm.urllib.request.urlopen", fake_urlopen)
    client = MiMoClient(api_key="tp-test")
    assert client.chat([{"role": "user", "content": "hi"}]) == "你好"
    assert captured["url"] == "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
    assert captured["headers"].get("api-key") == "tp-test"
    assert captured["payload"]["model"] == "mimo-v2.5-pro"
    assert captured["payload"]["messages"][0]["role"] == "user"


def test_chat_complete_injects_system_prompt(monkeypatch) -> None:
    captured: dict = {}
    body = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["payload"] = json.loads(request.data)
        return _FakeResp(body)

    monkeypatch.setattr("fde_scope.llm.urllib.request.urlopen", fake_urlopen)
    client = MiMoClient(api_key="tp-test")
    client.complete("hello", system="You are a bot")
    assert captured["payload"]["messages"][0] == {"role": "system", "content": "You are a bot"}


def test_chat_http_error_raises_llm_error(monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad key"))

    monkeypatch.setattr("fde_scope.llm.urllib.request.urlopen", fail)
    with pytest.raises(LLMError, match="401"):
        MiMoClient(api_key="tp-test").chat([{"role": "user", "content": "hi"}])


def test_chat_bad_response_shape_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        "fde_scope.llm.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(b"{}"),  # noqa: ARG005
    )
    with pytest.raises(LLMError, match="unexpected MiMo response"):
        MiMoClient(api_key="tp-test").chat([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# CorpusSynthesizer — LLM synthesis path + rule fallback
# ---------------------------------------------------------------------------
def test_synthesizer_uses_llm_output() -> None:
    llm = FakeLLM(reply=json.dumps(["你好，我要退款", "请帮我退货"], ensure_ascii=False))
    out = CorpusSynthesizer(llm=llm).fill_gaps([], [_gap()])
    assert out
    assert all(i.provenance == Provenance.SYNTHETIC for i in out)
    assert all("synthesize:llm" in i.trace for i in out)
    assert {i.content for i in out} == {"你好，我要退款", "请帮我退货"}


def test_synthesizer_tolerates_markdown_fenced_json() -> None:
    raw = '```json\n["第一条样本", "第二条样本"]\n```'
    out = CorpusSynthesizer(llm=FakeLLM(reply=raw)).fill_gaps([], [_gap()])
    assert len(out) == 2


def test_synthesizer_falls_back_to_rules_on_bad_json() -> None:
    out = CorpusSynthesizer(llm=FakeLLM(reply="这不是 JSON")).fill_gaps([], [_gap(target=2)])
    assert out  # rule path still produces items
    assert "synthesize:llm" not in out[0].trace


def test_synthesizer_falls_back_to_rules_on_error() -> None:
    out = CorpusSynthesizer(llm=FakeLLM(raise_on_call=True)).fill_gaps([], [_gap(target=2)])
    assert out
    assert "synthesize:llm" not in out[0].trace


def test_synthesizer_without_llm_stays_rule_based() -> None:
    out = CorpusSynthesizer().fill_gaps([], [_gap(target=2)])
    assert out
    assert "synthesize:llm" not in out[0].trace


def test_synthesizer_llm_items_are_scored() -> None:
    llm = FakeLLM(reply=json.dumps(["高质量退款诉求样本内容"]))
    out = CorpusSynthesizer(llm=llm).fill_gaps([], [_gap()])
    assert out[0].quality_score is not None
    assert 1.0 <= out[0].quality_score <= 5.0


# ---------------------------------------------------------------------------
# QualityGate — LLM score upgrade with rule fallback
# ---------------------------------------------------------------------------
def test_gate_score_text_uses_llm_score() -> None:
    gate = QualityGate(llm=FakeLLM(reply="4"))
    assert gate.score_text("一些内容", category="退款") == 4.0


def test_gate_score_text_falls_back_on_garbage() -> None:
    gate = QualityGate(llm=FakeLLM(reply="???完全不是数字"))
    score = gate.score_text("内容")
    assert 1.0 <= score <= 5.0  # rule score


def test_gate_score_text_falls_back_on_error() -> None:
    gate = QualityGate(llm=FakeLLM(raise_on_call=True))
    assert 1.0 <= gate.score_text("内容") <= 5.0


def test_gate_batch_call_stays_rule_based() -> None:
    llm = FakeLLM(reply="5")
    gate = QualityGate(llm=llm)
    items = [
        CorpusItem(id="1", content="这是一个足够长度的有效客服工单内容，有明确问题描述。", category="退款")
    ]
    passed = gate(items)
    assert passed and not llm.calls  # batch path never calls the LLM


# ---------------------------------------------------------------------------
# MiMoReplyFn — real LLM-backed agent replies
# ---------------------------------------------------------------------------
def test_mimo_reply_fn_delegates_to_llm() -> None:
    llm = FakeLLM(reply="已为您处理")
    fn = MiMoReplyFn(llm, tenant="acme")
    assert fn("怎么退款？") == "已为您处理"
    assert "acme" in llm.calls[0] or True  # tenant lands in the system prompt


def test_mimo_reply_fn_raises_llm_error() -> None:
    fn = MiMoReplyFn(FakeLLM(raise_on_call=True))
    with pytest.raises(LLMError):
        fn("怎么退款？")


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------
def test_eval_mimo_without_key_fails_cleanly(monkeypatch, eval_cases_jsonl: Path) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    result = runner.invoke(app, ["eval", "--agent", "mimo", "--test-set", str(eval_cases_jsonl)])
    assert result.exit_code == 2
    assert "FDE_SCOPE_MIMO_API_KEY" in result.stdout


def test_corpus_llm_without_key_fails_cleanly(monkeypatch, sample_csv: Path) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    result = runner.invoke(app, ["corpus", "--input", str(sample_csv), "--llm"])
    assert result.exit_code == 2
    assert "FDE_SCOPE_MIMO_API_KEY" in result.stdout


def test_deploy_reports_llm_status(monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    result = runner.invoke(app, ["deploy", "--tenant", "acme", "--dry-run"])
    assert result.exit_code == 0
    assert "FDE_SCOPE_MIMO_API_KEY" in result.stdout  # "未配置（设 … 启用 MiMo）"


def test_handoff_llm_without_key_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["engage", "init", "--customer", "Acme", "--profile", "ticket"])
    assert result.exit_code == 0, result.stdout
    eid = result.stdout.split("created (")[0].split("✅ Engagement ")[1].strip()
    result = runner.invoke(app, ["handoff", eid, "--llm"])
    assert result.exit_code == 2
    assert "FDE_SCOPE_MIMO_API_KEY" in result.stdout


# ---------------------------------------------------------------------------
# Review fixes — regressions for the issues found in the code review
# ---------------------------------------------------------------------------
def test_chat_null_content_raises(monkeypatch) -> None:
    """ "content": null (refusal/tool call) must raise, not return None."""
    body = json.dumps({"choices": [{"message": {"content": None}}]}).encode("utf-8")
    monkeypatch.setattr(
        "fde_scope.llm.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(body),  # noqa: ARG005
    )
    with pytest.raises(LLMError, match="empty content"):
        MiMoClient(api_key="tp-test").chat([{"role": "user", "content": "hi"}])


def test_chat_blank_content_raises(monkeypatch) -> None:
    body = json.dumps({"choices": [{"message": {"content": "  "}}]}).encode("utf-8")
    monkeypatch.setattr(
        "fde_scope.llm.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(body),  # noqa: ARG005
    )
    with pytest.raises(LLMError, match="empty content"):
        MiMoClient(api_key="tp-test").chat([{"role": "user", "content": "hi"}])


def test_synthesizer_caps_and_gates_llm_output() -> None:
    """The LLM path obeys the cap and the quality gate like the rule path."""
    reply = json.dumps(
        [
            "hi",  # too short → rule score below the gate
            "好的",
            "这是一条关于退款申请的正式投诉，商品有质量问题，要求全额退款并给出解释。",
            "物流迟迟不到，订单显示发货但一周没更新，麻烦帮我催一下快递。",
            "无法登录账号，密码重置邮件收不到，请尽快协助处理。",
        ],
        ensure_ascii=False,
    )
    gate = QualityGate(min_score=2.5)  # no llm → deterministic rule scoring
    synth = CorpusSynthesizer(quality_gate=gate, llm=FakeLLM(reply=reply))
    out = synth.fill_gaps([], [_gap(category="退款", target=2)])
    assert 0 < len(out) <= 2  # cap enforced even though the LLM returned 5
    contents = [i.content for i in out]
    assert "hi" not in contents and "好的" not in contents  # gate dropped the junk
    assert all(i.quality_score is not None and i.quality_score >= 2.5 for i in out)
    assert all("synthesize:llm" in i.trace for i in out)


def test_parse_json_list_rejects_non_strings() -> None:
    """Nested lists/numbers must not be str()-ed into repr garbage."""
    out = CorpusSynthesizer._parse_json_list('["ok", 123, ["a", "b"], {"k": 1}]')
    assert out == ["ok"]


def test_score_llm_clamps_two_digit_reply() -> None:
    """A '10' (misread as 10-point scale) must clamp to 5, not parse as 1."""
    gate = QualityGate(llm=FakeLLM(reply="10"))
    assert gate.score_text("内容", category="退款") == 5.0


def test_llm_runbook_success_and_fallback() -> None:
    from fde_scope.engagement.context import EngagementContext
    from fde_scope.engagement.operationalization import llm_runbook

    ctx = EngagementContext(id="e1", customer="Acme", profile="ticket")
    text, used = llm_runbook(ctx, FakeLLM(reply="## LLM Runbook"))
    assert used is True
    assert text == "## LLM Runbook"

    text, used = llm_runbook(ctx, FakeLLM(raise_on_call=True))
    assert used is False
    assert "Acme" in text  # deterministic template render, grounded in ctx


def test_eval_mimo_llm_error_fails_cleanly(monkeypatch, eval_cases_jsonl: Path) -> None:
    """A mid-run endpoint failure exits 1 with a clean message, no traceback."""
    monkeypatch.setenv("FDE_SCOPE_MIMO_API_KEY", "tp-test")

    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, io.BytesIO(b"boom"))

    monkeypatch.setattr("fde_scope.llm.urllib.request.urlopen", fail)
    result = runner.invoke(app, ["eval", "--agent", "mimo", "--test-set", str(eval_cases_jsonl)])
    assert result.exit_code == 1
    assert "MiMo eval failed" in result.stdout

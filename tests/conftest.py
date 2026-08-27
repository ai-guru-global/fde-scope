"""Shared pytest fixtures for the FDE Scope test suite."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip ``@pytest.mark.agentscope`` tests when the optional extra is absent.

    The core matrix (CI) installs no agentscope, so those tests must skip rather
    than error; the agentscope matrix runs them for real against the library —
    that is where the actual 2.0 signatures get verified.
    """
    if importlib.util.find_spec("agentscope") is not None:
        return
    skip = pytest.mark.skip(reason="agentscope extra not installed")
    for item in items:
        if "agentscope" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _no_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the suite offline and deterministic.

    LLM env vars leaked from the developer's shell would make the web forge
    tests hit the real MiMo endpoint (paid, flaky, slow) and flip LLM-status
    assertions. Every LLM-aware test re-sets what it needs explicitly.
    """
    for var in ("FDE_SCOPE_MIMO_API_KEY", "FDE_SCOPE_MIMO_BASE_URL", "FDE_SCOPE_MIMO_MODEL"):
        monkeypatch.delenv(var, raising=False)


SAMPLE_ROWS = [
    {
        "id": "t-001",
        "content": "我的订单三天了还没发货，麻烦帮我查一下物流。我的手机是13800138000",
        "category": "物流查询",
        "channel": "chat",
    },
    {
        "id": "t-002",
        "content": "申请退款，商品质量有问题，已经拍照留存。希望尽快处理。",
        "category": "退款",
        "channel": "email",
    },
    {
        "id": "t-003",
        "content": "无法登录账号，提示密码错误但是我确定没改过。",
        "category": "账号问题",
        "channel": "chat",
    },
    {
        "id": "t-004",
        "content": "退款退款退款！已经等了一周还没到账！",  # near-dup of refund
        "category": "退款",
        "channel": "phone",
    },
    {
        "id": "t-005",
        "content": "hi",  # too short → quality gate drops
        "category": "uncategorized",
        "channel": "chat",
    },
    {
        "id": "t-006",
        "content": "请问怎么修改收货地址？订单还没发货。",
        "category": "订单修改",
        "channel": "chat",
    },
    {
        "id": "t-007",
        "content": "商品破损，要求换货，联系邮箱 customer@example.com",
        "category": "退换货",
        "channel": "email",
    },
    {"id": "t-008", "content": "优惠券无法使用，结算时报错。", "category": "支付问题", "channel": "chat"},
]


@pytest.fixture
def sample_rows() -> list[dict]:
    return [dict(r) for r in SAMPLE_ROWS]


@pytest.fixture
def sample_csv(tmp_path: Path, sample_rows: list[dict]) -> Path:
    """Write the sample rows to a CSV and return its path."""
    import csv

    path = tmp_path / "tickets.csv"
    fields = ["id", "content", "category", "channel"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in sample_rows:
            writer.writerow({k: row.get(k, "") for k in fields})
    return path


@pytest.fixture
def sample_csv_bytes(sample_csv: Path) -> bytes:
    """The sample CSV as bytes (for upload tests)."""
    return sample_csv.read_bytes()


@pytest.fixture
def eval_cases_jsonl(tmp_path: Path) -> Path:
    """A small JSONL of eval cases."""
    cases = [
        {
            "id": "e-1",
            "input": "怎么退款？",
            "category": "退款",
            "expected_category": "退款",
            "handle_time_seconds": 30,
            "baseline_handle_time_seconds": 480,
            "csat": 5.0,
        },
        {
            "id": "e-2",
            "input": "物流太慢了",
            "category": "物流查询",
            "expected_category": "物流查询",
            "handle_time_seconds": 45,
            "escalated": False,
            "csat": 4.0,
        },
        {
            "id": "e-3",
            "input": "无法登录",
            "category": "账号问题",
            "expected_category": "支付问题",  # mismatch
            "handle_time_seconds": 60,
            "escalated": True,
            "csat": 2.0,
        },
    ]
    path = tmp_path / "eval.jsonl"
    path.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cases), encoding="utf-8")
    return path

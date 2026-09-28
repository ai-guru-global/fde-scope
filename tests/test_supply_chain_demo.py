"""供应链示例的 CQ 黄金答案测试 —— 方法论步骤5（评估）的固化形态。

demo.py 的三个能力问题答案在这里逐条断言：改 TBox/ABox 或重构 plan() 时，
这个文件是回归网。数据变化 = 有意更新黄金答案并说明原因。

demo 模块按文件路径装载（examples/ 不是包）；fde_scope 经 pytest prepend
导入模式解析（tests/__init__.py 使仓库根进入 sys.path）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "supply_chain_ontology"


def _load_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"scm_demo_{name}", EXAMPLES / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def demo() -> ModuleType:
    return _load_module("demo")


@pytest.fixture(scope="module")
def scm(demo):
    schema, store = demo.load()
    return demo, schema, store, demo.make_isa(schema)


# -- 前置：本体自校验（黄金答案有效性的前提） -------------------------------
def test_tbox_and_abox_validate(scm) -> None:
    demo, schema, store, _ = scm
    loader = lambda sid: schema if sid == schema.id else None  # noqa: E731
    assert demo.validate_schema(schema, loader).ok
    assert demo.validate_store(store, loader).ok


# -- CQ1 状态查询：接单时能否履约（ATP 黄金答案） ---------------------------
def test_cq1_atp_golden(scm) -> None:
    demo, _, store, isa = scm
    rows = {r["so"].curie: r for r in demo.plan(store, isa=isa)}
    # 客户B 小单：200 台，交期 09-06，可履约
    assert rows["scm:SO-1002"]["ok"] is True
    assert rows["scm:SO-1002"]["ready"].isoformat() == "2026-09-06"
    # 客户A 大单：1000 台，交期 09-15，可履约（靠供应商C 的在途批次兜底）
    assert rows["scm:SO-1001"]["ok"] is True
    assert rows["scm:SO-1001"]["ready"].isoformat() == "2026-09-15"


# -- CQ2 逻辑推导：供应商B 延迟 3 天的影响面 --------------------------------
def test_cq2_delay_golden(scm) -> None:
    demo, _, store, isa = scm
    base = {r["so"].curie: r for r in demo.plan(store, isa=isa)}
    delayed = {r["so"].curie: r for r in demo.plan(store, {"scm:PO-3001": 3}, isa=isa)}
    # 大单不受影响：后续在途批次（供应商C）兜底
    assert base["scm:SO-1001"]["ok"] is True
    assert delayed["scm:SO-1001"]["ok"] is True
    assert base["scm:SO-1001"]["ready"] == delayed["scm:SO-1001"]["ready"]
    # 小单被咬到：PO-3001 的 50 件铜线 09-07 才到，晚于 09-06 交期
    assert base["scm:SO-1002"]["ok"] is True
    assert delayed["scm:SO-1002"]["ok"] is False
    assert any("PO-3001" in issue for issue in delayed["scm:SO-1002"]["issues"])


# -- CQ3 行动触发：规则1 库存水位 + 规则2 分类路由 ---------------------------
def test_cq3_routing_golden(scm) -> None:
    demo, _, store, isa = scm
    rows = {r["curie"]: r for r in demo.cq3_rows(store, isa=isa)}
    # 战略级：漆包铜线 150+1100=1250 < 1400 → 触发，建议 1400-1250+100=250
    copper = rows["scm:COPPER-WIRE"]
    assert copper["triggered"] is True
    assert copper["strategic"] is True
    assert copper["suggest"] == 250
    # 常规：绝缘纸 80 < 300 → 触发，建议 300-80+100=320，走自动下发
    insulation = rows["scm:INSULATION"]
    assert insulation["triggered"] is True
    assert insulation["strategic"] is False
    assert insulation["suggest"] == 320
    # 库存充足：轴承 1500 ≥ 1200 → 不触发
    assert rows["scm:BEARING"]["triggered"] is False

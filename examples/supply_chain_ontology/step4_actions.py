"""步骤4 实现与集成演示：本体驱动的动作权限（规则2 的真实管线落地）。

运行（仓库根目录，需 agentscope extra）：

    PYTHONPATH=. .venv/bin/python examples/supply_chain_ontology/step4_actions.py

把步骤2 的 规则2（战略级物料 → 供应链总监审批；常规物料 → 自动下发）
编码成 AgentScope 2.0 的 PermissionRule：

- 动作工具 ``trigger_urgent_purchase`` 覆写 ``match_rule``：规则内容是一个
  **类 CURIE**（如 ``scm:StrategicMaterial``），匹配 = 该物料的 rdf:type
  经 is-a 闭包命中该类——权限规则的语义由本体承担，业务上重新分类
  物料（改 ABox 类型断言）即改变审批路由，权限管线一行不改。
- 引擎判定顺序（deny → ask → 只读快路径 → 工具钩子 → allow → 兜底）保证
  战略级先落入 ASK，永远不会被 ``scm:RawMaterial`` 的 ALLOW 规则吞掉。
- ``is_read_only=False``（部署工具永不标只读——B5：显式规则是唯一授权通道）。
- 权限 ≠ 业务必要性：权限层放行后，规则1（库存水位）在工具执行前再校验一次。
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

import yaml
from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionMode
from agentscope.tool import FunctionTool, ToolChunk
from demo import HERE, make_isa, one, supply_lots

from fde_scope.deploy.permission_builder import PermissionBlueprint, build_engine
from fde_scope.ontology.models import InstanceStore, OntologySchema
from fde_scope.skills.models import SkillCategory, SkillRecord

ABOX = HERE / "supply_chain_store.json"
TBOX = HERE / "supply_chain_tbox.yaml"


def _chunk(payload: dict, ok: bool = True) -> ToolChunk:
    text = json.dumps(payload, ensure_ascii=False)
    state = ToolResultState.SUCCESS if ok else ToolResultState.ERROR
    return ToolChunk(content=[TextBlock(type="text", text=text)], state=state)


def make_tools(schema: OntologySchema, store: InstanceStore):
    isa = make_isa(schema)
    index = {i.curie: i for i in store.individuals}

    async def _read_inventory(material: str) -> ToolChunk:
        """查询单一物料的现货/在途/7天预测。"""
        ind = index.get(material)
        if ind is None:
            return _chunk({"error": f"unknown material {material!r}"}, ok=False)
        in_transit = sum(lot["qty"] for lot in supply_lots(store, {}).get(ind.curie, []))
        return _chunk(
            {
                "material": one(ind, "scm:name"),
                "on_hand": one(ind, "scm:qty_on_hand"),
                "in_transit": in_transit,
                "forecast_7d": one(ind, "scm:forecast_demand_7d"),
            }
        )

    read_tool = FunctionTool(
        _read_inventory,
        name="read_inventory",
        description="查询单一物料的现货/在途/7天预测（只读能力，但按 B5 不标 read-only，走显式 ALLOW 规则）",
        is_read_only=False,
    )

    async def _urgent_purchase(material: str, qty: int) -> ToolChunk:
        """生成紧急采购单草案（执行前重验规则1 库存水位）。"""
        ind = index.get(material)
        if ind is None:
            return _chunk({"error": f"unknown material {material!r}"}, ok=False)
        on_hand = one(ind, "scm:qty_on_hand")
        in_transit = sum(lot["qty"] for lot in supply_lots(store, {}).get(ind.curie, []))
        forecast = one(ind, "scm:forecast_demand_7d")
        if on_hand + in_transit >= forecast:
            return _chunk(
                {
                    "material": one(ind, "scm:name"),
                    "veto": "规则1 未触发：现货+在途 ≥ 7天预测，不下单",
                },
                ok=False,
            )
        eta = (date.today() + timedelta(days=one(ind, "scm:lead_time_days"))).isoformat()
        return _chunk(
            {
                "material": one(ind, "scm:name"),
                "po_draft": f"紧急采购 {qty} 件，ETA {eta}",
                "rule1": f"{on_hand}+{in_transit} < {forecast}",
            }
        )

    class UrgentPurchaseTool(FunctionTool):
        """动作工具：match_rule 用本体 is-a 闭包解释规则内容（类 CURIE）。"""

        async def match_rule(self, rule_content: str | None, tool_input: dict) -> bool:
            if rule_content is None:
                return True
            ind = index.get(str(tool_input.get("material", "")))
            if ind is None or not ind.types:
                return False  # 未声明个体 fail-closed：落不到 ALLOW，交给兜底
            return any(isa(t, rule_content) for t in ind.types)

    urgent_tool = UrgentPurchaseTool(
        _urgent_purchase,
        name="trigger_urgent_purchase",
        description="对指定物料生成紧急采购单草案（执行前重验规则1 库存水位）",
        is_read_only=False,
    )
    return read_tool, urgent_tool, _urgent_purchase


def blueprint() -> PermissionBlueprint:
    return PermissionBlueprint(
        tenant_id="scm-demo",
        allow=[
            ("read_inventory", None),
            # 常规原材料：物料类型经 is-a 命中 RawMaterial 即自动放行
            ("trigger_urgent_purchase", "scm:RawMaterial"),
        ],
        deny=[("delete_any", None), ("exec_shell", None)],
        # 战略级物料：先于 ALLOW 求值（引擎顺序 deny→ask→…→allow），必进 HITL
        ask=[("trigger_urgent_purchase", "scm:StrategicMaterial")],
    )


def describe(decision) -> str:
    name = decision.behavior.name
    return f"{name}（{decision.decision_reason or decision.message}）"


async def hitl(material_label: str) -> bool:
    """HITL 模拟：真实部署里这是审批 UI / 飞书卡片，这里是演示桩。"""
    print(f"      → HITL 弹出审批：供应链总监 审批『{material_label}』紧急采购 … 批准")
    return True


async def main() -> None:
    schema = OntologySchema.model_validate(yaml.safe_load(TBOX.read_text(encoding="utf-8")))
    store = InstanceStore.model_validate(json.loads(ABOX.read_text(encoding="utf-8")))
    read_tool, urgent_tool, urgent_purchase = make_tools(schema, store)
    bp = blueprint()
    engine = build_engine(bp, "conservative")
    print(f"引擎模式：{engine.context.mode.name}（conservative 租户）")
    print("规则蓝图：")
    for line in bp.describe().splitlines()[1:]:
        print(f"  {line}")

    print("\n-- 0) 只读查询（ALLOW 规则）--")
    d = await engine.check_permission(read_tool, {"material": "scm:COPPER-WIRE"})
    print(f"  read_inventory(漆包铜线) → {describe(d)}")

    print("\n-- 1) 战略级物料（漆包铜线）→ ASK → 总监批准 → 执行 --")
    d = await engine.check_permission(urgent_tool, {"material": "scm:COPPER-WIRE", "qty": 250})
    print(f"  trigger_urgent_purchase(漆包铜线) → {describe(d)}")
    if d.behavior is PermissionBehavior.ASK and await hitl("漆包铜线"):
        print(f"  执行 → {(await urgent_purchase('scm:COPPER-WIRE', 250)).content[0].text}")

    print("\n-- 2) 常规物料（绝缘纸）→ ALLOW → 自动下发采购员 --")
    d = await engine.check_permission(urgent_tool, {"material": "scm:INSULATION", "qty": 320})
    print(f"  trigger_urgent_purchase(绝缘纸) → {describe(d)}")
    if d.behavior is PermissionBehavior.ALLOW:
        print(f"  执行 → {(await urgent_purchase('scm:INSULATION', 320)).content[0].text}")

    print("\n-- 3) 权限 ≠ 业务必要性：轴承权限放行但规则1 否决 --")
    d = await engine.check_permission(urgent_tool, {"material": "scm:BEARING", "qty": 10})
    print(f"  trigger_urgent_purchase(轴承) → {describe(d)}")
    print(f"  执行 → {(await urgent_purchase('scm:BEARING', 10)).content[0].text}")

    print("\n-- 4) 无人值守租户（autonomous → DONT_ASK）：战略级采购被拒绝 --")
    engine_auto = build_engine(bp, "autonomous")
    d = await engine_auto.check_permission(urgent_tool, {"material": "scm:COPPER-WIRE", "qty": 250})
    print(f"  模式 {PermissionMode.DONT_ASK.name} → {describe(d)}")
    print("  （ASK 被转成 DENY：无人可批，绝不静默执行）")

    print("\n-- 5) 技能库桥接（P3）：动作沉淀为 SkillRecord --")
    skill = SkillRecord(
        title="触发紧急采购（供应链）",
        category=SkillCategory.IMPLEMENTATION,
        tags=["scm:RawMaterial", "scm:StrategicMaterial"],
        body_md="库存+在途<7天预测 时生成紧急采购草案；战略级物料需总监审批。",
    )
    print(f"  SkillRecord id={skill.id}（服务端生成）")
    from fde_scope.ontology.skills_bridge import skill_concepts
    from fde_scope.ontology.store import OntologyStore

    fde_core = OntologyStore().load_schema("fde-core")
    assert fde_core is not None
    print(
        f"  SKOS 概念：{skill_concepts(skill, fde_core)}"
        "（category→fde:cat-implementation；scm 前缀未在 fde-core 声明，tag 被忽略——幽灵节点纪律）"
    )


if __name__ == "__main__":
    asyncio.run(main())

"""步骤3 形式化编码演示：供应链本体 TBox/ABox -> 校验 -> JSON-LD -> CQ 问答。

运行（仓库根目录）：

    .venv/bin/python examples/supply_chain_ontology/demo.py

三个能力问题（步骤1 提炼）都在 ABox 图上以纯图遍历回答：
- CQ1 状态查询：两张销售订单按交期能否齐套（ATP 检查）。
- CQ2 逻辑推导：供应商B 交期 +3 天后，哪些销售订单受影响。
- CQ3 行动触发：库存+在途 < 未来7天预测 时生成采购建议，并按物料分级路由审批。

规则1/规则2 作为确定性函数写在本文件（仓库的本体层不带推理机，
TBox 只承载规则读取的分类，如 scm:StrategicMaterial）。
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import yaml

from fde_scope.fsutil import atomic_write_text
from fde_scope.ontology.jsonld import schema_to_jsonld, store_to_jsonld
from fde_scope.ontology.models import Individual, InstanceStore, OntologySchema
from fde_scope.ontology.validation import validate_schema, validate_store

HERE = Path(__file__).parent
OUT = HERE / "out"
TBOX = HERE / "supply_chain_tbox.yaml"
ABOX = HERE / "supply_chain_store.json"


def d(iso: str) -> date:
    return date.fromisoformat(iso[:10])


def one(ind: Individual, prop: str):
    return ind.data_assertions[prop][0]


def ref(ind: Individual, prop: str) -> str | None:
    targets = ind.object_assertions.get(prop)
    return targets[0] if targets else None


def index(store: InstanceStore) -> dict[str, Individual]:
    return {i.curie: i for i in store.individuals}


def make_isa(schema: OntologySchema):
    """is-a 闭包判定（与校验器同语义）：类型或其祖先命中即匹配。"""
    parents = {c.curie: list(c.sub_class_of) for c in schema.classes}

    def isa(t: str, expected: str) -> bool:
        stack, seen = [t], set()
        while stack:
            cur = stack.pop()
            if cur == expected:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(parents.get(cur, ()))
        return False

    return isa


def by_type(store: InstanceStore, t: str, isa=None) -> list[Individual]:
    match = isa or (lambda typ, want: typ == want)
    return sorted(
        (i for i in store.individuals if any(match(typ, t) for typ in i.types)),
        key=lambda i: i.curie,
    )


def supply_lots(store: InstanceStore, delays: dict[str, int]) -> dict[str, list[dict]]:
    """物料 -> 在途批次列表 [{arrival, qty, po}]，arrival 按 PO 交期(+延误)计。"""
    lots: dict[str, list[dict]] = {}
    for po in by_type(store, "scm:PurchaseOrder"):
        mat = ref(po, "scm:supplies")
        assert mat is not None
        arrival = d(one(po, "scm:due_date")) + timedelta(days=delays.get(po.curie, 0))
        lots.setdefault(mat, []).append({"arrival": arrival, "qty": one(po, "scm:order_qty"), "po": po.curie})
    for batch in lots.values():
        batch.sort(key=lambda lot: lot["arrival"])
    return lots


def plan(store: InstanceStore, delays: dict[str, int] | None = None, isa=None) -> list[dict]:
    """按交期顺序消化销售订单：成品现货 -> 工单 -> 物料现货 -> 在途批次。"""
    delays = delays or {}
    lots = supply_lots(store, delays)
    on_hand = {i.curie: one(i, "scm:qty_on_hand") for i in by_type(store, "scm:Material", isa)}
    lines = [
        (ref(bl, "scm:line_order"), ref(bl, "scm:line_material"), one(bl, "scm:line_qty"))
        for bl in by_type(store, "scm:BOMLine")
    ]
    orders = by_type(store, "scm:SalesOrder")
    orders.sort(key=lambda so: one(so, "scm:due_date"))

    results = []
    for so in orders:
        due = d(one(so, "scm:due_date"))
        product = ref(so, "scm:contains")
        assert product is not None
        need = one(so, "scm:order_qty")

        take = min(on_hand[product], need)
        on_hand[product] -= take
        remaining = need - take

        ready = due
        issues: list[str] = []
        work_orders = [
            ind
            for ind in by_type(store, "scm:ProductionOrder")
            if so.curie in ind.object_assertions.get("scm:fulfills", [])
        ]
        for wo in work_orders:
            make = min(one(wo, "scm:order_qty"), remaining)
            ratio = make / one(wo, "scm:order_qty") if one(wo, "scm:order_qty") else 0
            for line_po, mat, qty in lines:
                if line_po != wo.curie or ratio <= 0:
                    continue
                required = int(qty * ratio)
                got = min(on_hand[mat], required)
                on_hand[mat] -= got
                shortfall = required - got
                for lot in lots.get(mat, []):
                    if shortfall <= 0:
                        break
                    used = min(lot["qty"], shortfall)
                    lot["qty"] -= used
                    shortfall -= used
                    if lot["arrival"] > due:
                        issues.append(
                            f"{mat.split(':')[-1]} 需 {required} 件，其中 {used} 件在途"
                            f"（{lot['po'].split(':')[-1]}）{lot['arrival']} 才到，晚于交期 {due}"
                        )
                    ready = max(ready, lot["arrival"])
                if shortfall > 0:
                    issues.append(f"{mat.split(':')[-1]} 缺口 {shortfall} 件且无在途可排")
            remaining -= make
        if remaining > 0:
            issues.append(f"成品缺口 {remaining} 台且无工单覆盖")
        results.append({"so": so, "due": due, "ok": not issues, "ready": ready, "issues": issues})
    return results


def answer_cq1(store: InstanceStore, isa=None) -> None:
    print("\n== CQ1 状态查询：接单时能否履约？ ==")
    for row in plan(store, isa=isa):
        so, name = row["so"].curie, one(row["so"], "scm:name")
        if row["ok"]:
            print(
                f"  ✅ {so}（{name}）：可履约，齐套日 {row['ready']}"
                + ("" if row["ready"] == row["due"] else "（晚于原交期，需与客户确认）")
            )
        else:
            print(f"  ⚠️  {so}（{name}）：原交期 {row['due']} 无法齐套")
            for issue in row["issues"]:
                print(f"      - {issue}")


def answer_cq2(store: InstanceStore, isa=None) -> None:
    print("\n== CQ2 逻辑推导：供应商B 交期延迟 3 天影响谁？ ==")
    base = {row["so"].curie: row for row in plan(store, isa=isa)}
    delayed = {row["so"].curie: row for row in plan(store, {"scm:PO-3001": 3}, isa=isa)}
    for curie in sorted(base):
        before, after = base[curie], delayed[curie]
        if before["ok"] and after["ok"] and before["ready"] == after["ready"]:
            print(f"  ✅ {curie}：不受影响（齐套日仍为 {after['ready']}）")
        elif before["ok"] and after["ok"]:
            print(f"  ⚠️  {curie}：齐套日 {before['ready']} -> {after['ready']}，建议与客户改期")
        else:
            print(f"  ⚠️  {curie}：受延迟影响（原可按 {before['due']} 交付）")
            for issue in after["issues"]:
                print(f"      - {issue}")


def answer_cq3(store: InstanceStore, isa=None) -> None:
    print("\n== CQ3 行动触发：紧急采购建议（规则1 + 规则2） ==")
    lots = supply_lots(store, {})
    for mat in by_type(store, "scm:RawMaterial", isa):
        on_hand = one(mat, "scm:qty_on_hand")
        in_transit = sum(lot["qty"] for lot in lots.get(mat.curie, []))
        forecast = one(mat, "scm:forecast_demand_7d")
        name = one(mat, "scm:name")
        available = on_hand + in_transit
        if available >= forecast:
            print(f"  ✅ {name}：现有 {on_hand} + 在途 {in_transit} ≥ 7天预测 {forecast}，不触发")
            continue
        suggest = forecast - available + one(mat, "scm:safety_stock")
        strategic = "scm:StrategicMaterial" in mat.types
        route = "供应链总监审批（HITL ASK）" if strategic else "自动下发给采购员"
        level = "战略级" if strategic else "常规"
        print(f"  🔥 触发紧急采购：{name}（{level}物料）")
        print(f"      规则1：现有 {on_hand} + 在途 {in_transit} = {available} < 7天预测 {forecast}")
        print(f"      建议量：{suggest} 件（补足预测缺口 + 安全库存）")
        print(f"      规则2 路由：{route}")


def main() -> None:
    schema = OntologySchema.model_validate(yaml.safe_load(TBOX.read_text(encoding="utf-8")))
    loader = lambda sid: schema if sid == schema.id else None  # noqa: E731

    report = validate_schema(schema, loader)
    print(
        f"TBox 校验：{'通过' if report.ok else '失败'}（{schema.id}@{schema.version}，"
        f"{len(schema.classes)} 类 / {len(schema.object_properties)} 对象属性 / "
        f"{len(schema.data_properties)} 数据属性）"
    )
    for issue in report.errors:
        print(f"  [{issue.code}] {issue.subject}: {issue.message}")

    store = InstanceStore.model_validate(json.loads(ABOX.read_text(encoding="utf-8")))
    store_report = validate_store(store, loader)
    print(f"ABox 校验：{'通过' if store_report.ok else '失败'}（{store.id}，{len(store.individuals)} 个体）")
    for issue in store_report.errors:
        print(f"  [{issue.code}] {issue.subject}: {issue.message}")
    if not report.ok or not store_report.ok:
        raise SystemExit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    tbox_jsonld = json.dumps(schema_to_jsonld(schema), ensure_ascii=False, indent=2, sort_keys=True)
    abox_jsonld = json.dumps(store_to_jsonld(store, schema), ensure_ascii=False, indent=2, sort_keys=True)
    atomic_write_text(OUT / "supply_chain_tbox.jsonld", tbox_jsonld + "\n")
    atomic_write_text(OUT / "supply_chain_abox.jsonld", abox_jsonld + "\n")
    print(f"JSON-LD 导出：{OUT / 'supply_chain_tbox.jsonld'}（{len(tbox_jsonld)} 字节）")
    print(f"              {OUT / 'supply_chain_abox.jsonld'}（{len(abox_jsonld)} 字节）")

    answer_cq1(store, make_isa(schema))
    answer_cq2(store, make_isa(schema))
    answer_cq3(store, make_isa(schema))


if __name__ == "__main__":
    main()

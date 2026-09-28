"""步骤3 产物 × 标准 RDF 工具链：SPARQL 互操作演示。

运行（仓库根目录；rdflib 是示例级可选依赖，未进 pyproject）：

    uv pip install rdflib --python .venv/bin/python
    PYTHONPATH=. .venv/bin/python examples/supply_chain_ontology/sparql_interop.py

把 demo.py 导出的 JSON-LD（out/*.jsonld）灌进 rdflib Graph，用 SPARQL 复答
三个能力问题的**结构层**。诚实边界：

- SPARQL 擅长的是图模式/属性路径（谁连着谁）——CQ2 给出的是"结构暴露集合"
  （齐套路径上有该 PO 的全部销售订单，是超集）；
- 时序与数量裁决（哪 50 件晚于交期）需要规则层，见 demo.py 的 plan()。
  两层对照打印，正是"本体 + 规则"分工的现场教学。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out"
SCM = "https://ai-guru-global.github.io/fde-scope/ontology/supplychain#"

PREFIX = f"PREFIX scm: <{SCM}>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"

# CQ1 结构层：销售订单 → 产品/数量/交期（数字与日期是 JSON-LD 字面量）
CQ1 = PREFIX + """
SELECT ?so ?product ?qty ?due WHERE {
  ?so a scm:SalesOrder ; scm:contains ?product ;
      scm:order_qty ?qty ; scm:due_date ?due .
} ORDER BY ?due
"""

# CQ2 结构暴露集：从被延迟的 PO 沿"供应→消耗→履约"属性路径反推销售订单。
# 直接消耗（scm:consumes）与 BOM 行具体化（line_order/line_material）都算路。
CQ2 = PREFIX + """
SELECT DISTINCT ?so ?wo WHERE {
  ?so a scm:SalesOrder ; scm:fulfilled_by ?wo .
  { ?wo scm:consumes ?mat . }
  UNION
  { ?bl scm:line_order ?wo ; scm:line_material ?mat . }
  ?po scm:supplies ?mat .
  FILTER (?po = scm:PO-3001)
} ORDER BY ?so
"""

# CQ3 结构层：触发规则1 的战略级物料（现货 < 7天预测；路由读 rdf:type）
CQ3 = PREFIX + """
SELECT ?mat ?name ?onhand ?forecast WHERE {
  ?mat a scm:StrategicMaterial ; scm:name ?name ;
       scm:qty_on_hand ?onhand ; scm:forecast_demand_7d ?forecast .
  FILTER (?onhand < ?forecast)
} ORDER BY ?mat
"""


def build_graph():
    import rdflib

    g = rdflib.Graph()
    for name in ("supply_chain_tbox.jsonld", "supply_chain_abox.jsonld"):
        p = OUT / name
        if not p.exists():
            sys.exit(f"缺少 {p} —— 先运行 demo.py 生成导出")
        g.parse(p, format="json-ld")
    return g


def rows(graph, query: str) -> list[tuple]:
    return [tuple(str(v).split("#")[-1] for v in row) for row in graph.query(query)]


def main() -> None:
    try:
        import rdflib  # noqa: F401
    except ImportError:
        sys.exit("需要 rdflib（示例级可选依赖，未进 pyproject）：uv pip install rdflib")
    g = build_graph()
    print(f"rdflib 载入合并图：{len(g)} triples（TBox + ABox，默认图自包含）")

    print("\n== CQ1（SPARQL 结构层）：销售订单 → 产品/数量/交期 ==")
    for so, product, qty, due in rows(g, CQ1):
        print(f"  {so:12s} {product:10s} qty={qty:5s} due={due[:10]}")

    print("\n== CQ2（SPARQL 属性路径）：PO-3001 的结构暴露集合 ==")
    for so, wo in rows(g, CQ2):
        print(f"  {so} ← {wo}")
    print("  （超集：是否真晚于交期由规则层裁决——demo.py plan() 判定仅 SO-1002 受影响）")

    print("\n== CQ3（SPARQL 结构层）：触发规则1 的战略级物料 ==")
    for mat, name, onhand, forecast in rows(g, CQ3):
        print(f"  {mat:14s} {name}  现货 {onhand} < 预测 {forecast}（路由：总监审批）")


if __name__ == "__main__":
    main()

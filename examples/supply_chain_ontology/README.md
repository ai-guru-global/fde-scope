# 供应链本体示例 —— 本体构建步骤 3：形式化编码

> 以"大型制造企业供应链"为例，演示步骤1（需求分析/CQs）与步骤2（概念化）
> 的产出如何形式化为机器可读的 TBox + ABox，并验证、导出 JSON-LD、
> 在图上回答能力问题。全部使用本仓库自带的本体工具链（零新依赖）。

## 三步映射

| 步骤 | 产出 | 本目录的落点 |
|---|---|---|
| 1 需求分析 | CQ1 状态查询 / CQ2 逻辑推导 / CQ3 行动触发；边界 = 销售订单→生产计划→采购与库存 | `demo.py` 的三个 `answer_cq*` |
| 2 概念化 | 订单/物料/主体三类层级，四条核心关系，触发紧急采购动作 + 两条规则 | 下表 TBox 的类与属性 |
| 3 形式化编码 | 机器可读本体 + 可运行验证 | `supply_chain_tbox.yaml`（TBox）+ `supply_chain_store.json`（ABox）+ `demo.py` |

## 运行

```bash
# 仓库根目录
PYTHONPATH=. .venv/bin/python examples/supply_chain_ontology/demo.py
```

预期输出（数据已配平）：

- 两级校验通过（SHACL-lite，错误码 ONTO-xxx，见 `docs/ontology.md`）
- TBox/ABox 各导出一份 JSON-LD 1.1 到 `out/`
- **CQ1**：SO-1002（200台，09-06 交）与 SO-1001（1000台，09-15 交）均可履约
- **CQ2**：供应商B 交期 +3 天 → 只有 SO-1002 受影响（50 件铜线 09-07 才到，
  晚于 09-06 交期）；SO-1001 不受影响
- **CQ3**：漆包铜线 150+1100=1250 < 7天预测 1400 → 触发紧急采购 250 件；
  战略级物料 → 路由"供应链总监审批"（对应部署侧 HITL ASK），常规物料则自动下发

## TBox 设计要点（步骤3 的关键动作）

1. **TBox/ABox 分离**：模式（类、属性）与实例（这批订单/物料）分文件，
   `ontology_ref = "supply-chain-demo@1.0.0"` 锁版本（ONTO-040）。
2. **CURIE 纪律**：全部跨元素引用写 `scm:Xxx`，前缀在 `namespaces` 声明
   （ONTO-030），导出时自动展开为绝对 IRI。
3. **is-a 闭包承担语义**：`成品 ⊑ 物料`，所以成品个体的库存断言满足
   `qty_on_hand` 的 domain——校验器按祖先闭包判定（ONTO-020），无需推理机。
4. **BOM 行具体化（reification）**：步骤2 的箭头 `工单--[消耗]-->原材料`
   是二元关系，带不上"消耗多少"。步骤3 把它升格为 `scm:BOMLine` 个体
   （`line_order` + `line_material` + `line_qty`）——凡是"关系自身带属性"的地方
   都这样处理。
5. **多类型分类驱动规则**：`COPPER-WIRE` 同时 `rdf:type` `RawMaterial` 和
   `StrategicMaterial`；CQ3 规则2 读这个分类做审批路由，而不是把
   "战略级"写死在流程代码里。
6. **inverse 属性**：`fulfills` / `fulfilled_by` 双向声明，售后追溯
   （订单→工单）与排产追溯（工单→订单）都不用扫全图。
7. **规则的位置（诚实声明）**：规则1/规则2 是 `demo.py` 里的确定性函数；
   本仓库本体层不带 SWRL/OWL 推理机，TBox 承载的是规则读取的
   **分类与结构**。这与其余 18 阶段 SOP 的哲学一致：行动能力走
   deploy 权限管线（规则授权 + HITL），不走黑盒推理。

## 与内置本体的关系

内置 `mfg-overlay`（ISA-95）建模的是**FDE 交付侧**的工厂层级与验收工件
（FAT/SAT/功能安全/KPI）；本示例建模的是**客户业务侧**的供应链闭环，
两者可在同一 workspace 共存（工作区 schemas 优先级高于内置，见
`docs/ontology.md` 存储布局）。

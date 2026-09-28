# 供应链本体示例 —— 本体构建步骤 3-6

> 以"大型制造企业供应链"为例，走完本体工程六步方法论的核心四步：
> 步骤1（需求分析/CQs）与步骤2（概念化）的产出形式化为 TBox + ABox
> （步骤3），动作接上真实权限管线（步骤4），CQ 黄金答案固化为回归测试
> （步骤5），schema diff + 概念模型图支撑长期演进（步骤6）。
> 全部使用本仓库自带的本体工具链；步骤4 需要 agentscope extra，
> SPARQL 互操作需要 rdflib（示例级可选依赖，未进 pyproject）。

## 方法论步骤映射

| 步骤 | 产出 | 本目录的落点 |
|---|---|---|
| 1 需求分析 | CQ1 状态查询 / CQ2 逻辑推导 / CQ3 行动触发；边界 = 销售订单→生产计划→采购与库存 | `demo.py` 的三个 `answer_cq*` |
| 2 概念化 | 订单/物料/主体三类层级，四条核心关系，触发紧急采购动作 + 两条规则 | 下表 TBox 的类与属性；Mermaid 图 `out/supply_chain_tbox.mmd` |
| 3 形式化编码 | 机器可读本体 + 可运行验证 | `supply_chain_tbox.yaml`（TBox）+ `supply_chain_store.json`（ABox）+ `demo.py` |
| 4 实现/集成 | 本体驱动权限：战略级→HITL 审批，常规→自动放行 | `step4_actions.py`（真实 AgentScope `PermissionEngine`） |
| 5 评估 | CQ 黄金答案 = 回归测试 | `tests/test_supply_chain_demo.py`（`make test` 即跑） |
| 6 维护演进 | 破坏性变更诊断 + 影响面 | `fde-scope ontology diff`（D1-D4）+ `--format mermaid` |

## 运行

```bash
# 仓库根目录
PYTHONPATH=. .venv/bin/python examples/supply_chain_ontology/demo.py           # 步骤3
PYTHONPATH=. .venv/bin/python examples/supply_chain_ontology/step4_actions.py  # 步骤4（agentscope extra）
PYTHONPATH=. .venv/bin/python examples/supply_chain_ontology/sparql_interop.py # 步骤3 产物 × rdflib（可选依赖）
.venv/bin/python -m pytest tests/test_supply_chain_demo.py -q                  # 步骤5 黄金答案
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

## 步骤4：动作接上权限管线（step4_actions.py）

把步骤2 的 规则2 编码成 AgentScope 2.0 的 `PermissionRule`，四个场景全部跑
**真实** `PermissionEngine`（agentscope 2.0.8 实测）：

| 场景 | 引擎判定 | 结果 |
|---|---|---|
| 战略级物料（漆包铜线）紧急采购 | **ASK**（规则 `scm:StrategicMaterial` 先于 ALLOW 求值） | HITL：供应链总监批准后执行 |
| 常规物料（绝缘纸）紧急采购 | **ALLOW**（is-a 命中 `scm:RawMaterial`） | 自动下发采购员 |
| 轴承（权限放行但库存充足） | ALLOW | 工具执行前规则1 否决——权限 ≠ 业务必要性 |
| 无人值守租户（DONT_ASK）+ 战略级 | **DENY**（ASK 被转换） | 没人可批，绝不静默执行 |

关键机制：动作工具 `trigger_urgent_purchase` 覆写 `match_rule`，规则内容是一个
**类 CURIE**，匹配 = 物料个体的 `rdf:type` 经 is-a 闭包命中该类。于是：

- **审批路由由本体分类驱动**——业务上把某物料升级为战略级 = 改一条 ABox
  类型断言，权限管线一行不改；
- 未声明个体 fail-closed（两条规则都不匹配 → 兜底：DEFAULT→ASK 人审，
  DONT_ASK→DENY）；
- `is_read_only=False`（B5：显式规则是唯一授权通道，部署工具永不标只读）。

演示同时沉淀 `SkillRecord`（id 服务端生成）并经 `skills_bridge` 输出 SKOS
概念——未在 fde-core 声明的 `scm:` tag 被忽略（幽灵节点纪律）。

## 步骤5：CQ 黄金答案测试（tests/test_supply_chain_demo.py）

demo.py 的三个 CQ 答案逐条断言为 pytest 黄金答案：TBox/ABox 校验通过 +
CQ1 两单齐套日期 + CQ2 只有 SO-1002 被延迟咬到 + CQ3 触发/路由/建议量。
重构 `plan()` 或改数据时这是回归网；**数据变化 = 有意更新黄金答案并说明
原因**——测试文件本身就是 CQ 的可执行规格（方法论第 5 步的固化形态）。

## SPARQL 互操作（sparql_interop.py）

把 `out/*.jsonld` 灌进 rdflib（241 triples），用标准 SPARQL 复答三个 CQ 的
**结构层**：CQ1 取订单→产品/数量/交期；CQ2 用属性路径（`fulfilled_by` →
`consumes` ∪ BOM 行）反推 PO-3001 的暴露集合；CQ3 用 `FILTER(?onhand <
?forecast)` 复现规则1 的判定条件并读 `StrategicMaterial` 分类。诚实边界：
SPARQL 给出的是结构超集，时序与数量裁决仍在规则层（`demo.py plan()`）——
两层对照打印，正是"本体 + 规则"分工的现场教学。

JSON-LD 形状契约：导出顶层只有 `@context` + `@graph`（owl:Ontology 元数据
是 graph 首元素）。不要改回"顶层 @id + @graph"的 graph-object 形式——rdflib
7.6 实测会把 @graph 内容送进 named graph，单图工具（Graph.parse、多数
Protégé 载入路径）读不到那些三元组（`tests/test_ontology_jsonld.py` 锁定）。

## 步骤6：schema diff 与概念模型图（CLI）

```bash
export FDE_SCOPE_HOME=<workspace>   # 把 TBox/ABox 放进 <workspace>/.fde_scope/ontology/
fde-scope ontology diff supply-chain-demo supply-chain-demo-next --store supply-chain-demo-store
fde-scope ontology export supply-chain-demo --format mermaid -o concept_model.mmd
```

- **diff**：D1 元素移除 / D2 属性 domain·range 改指 / D3 字面量范围变化 /
  D4 sub_class_of 收紧（失去父类 → is-a 闭包变窄）= 破坏性（exit 1，CI 可拦）；
  新增元素、放宽父类、inverse 变化 = INFO。`--store` 附带 ABox 影响面：
  引用了变更元素的个体证据清单（迁移工作量，不推断）。
- **mermaid**：TBox → classDiagram（双语显示名 + 继承树 + 关联边 + 数据属性
  成员），步骤2 那张"业务概念模型图"从此机器生成、随版本演进。
  本示例的图已导出在 `out/supply_chain_tbox.mmd`。

## 与内置本体的关系

内置 `mfg-overlay`（ISA-95）建模的是**FDE 交付侧**的工厂层级与验收工件
（FAT/SAT/功能安全/KPI）；本示例建模的是**客户业务侧**的供应链闭环，
两者可在同一 workspace 共存（工作区 schemas 优先级高于内置，见
`docs/ontology.md` 存储布局）。

## 整体评估

六步方法论覆盖矩阵、模块强项、诚实缺口与下一步 ROI 排序见
[EVALUATION.md](EVALUATION.md)。

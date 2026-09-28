# 整体评估 — fde-scope 本体工程能力 × 供应链示例

> 评估日期：2026-09-28（首轮）；同日完成首轮评估列出的全部 P0/P1 工程项，
> 状态已刷新。评估对象：`fde_scope/ontology/` 全模块、deploy 权限管线
> 与本体/权限的接线点、`examples/supply_chain_ontology/` 步骤3-6 演示。
> 方法：对照本体工程标准六步（需求分析 → 概念化 → 形式化 → 实现/集成 →
> 评估 → 维护演进）逐项覆盖，结论全部以代码与测试为证。

## 一、六步覆盖矩阵（首轮评估后刷新）

| 方法论步骤 | 状态 | 证据 | 主要缺口 |
|---|---|---|---|
| 1 需求分析（CQ） | ✅ | `demo.py` 三个 `answer_cq*`；CQ 锚定价值、边界写进 README | CQ 没有固化成可执行测试工件 → **已解决（见步骤5）** |
| 2 概念化 | ✅ | TBox YAML 即概念模型 | 概念模型图无可视化导出 → **已解决（`diagram.py`，Mermaid）** |
| 3 形式化编码 | ✅ | TBox/ABox 分离、CURIE 纪律、ONTO-xxx 校验、JSON-LD 1.1 确定性导出 | 导出形状曾不可被单图工具消费 → **已修复（默认图自包含 + 互操作测试锁定）** |
| 4 实现/集成 | ✅ | `step4_actions.py`：本体驱动 `match_rule` + 真实 AgentScope `PermissionEngine` + SKOS 技能桥 | connector→ABox 同步路径不存在（ERP 真源刷新靠手工） |
| 5 评估 | ✅ | `tests/test_supply_chain_demo.py`：CQ1-3 黄金答案 pytest 化，`make test` 即回归 | SHACL-lite 仍为子集（表达力上限，见 P1） |
| 6 维护演进 | ✅（诊断闭环） | `fde_scope/ontology/diff.py`：D1-D4 破坏性判据 + ABox 影响面 + CLI exit 1 | diff 只诊断不迁移；ABox 迁移执行仍手工 |

**结论：六步全部闭环**（第 6 步是"诊断"意义上的闭环——迁移执行器仍是
真实的后续工程项）。"痛点 → CQ → 本体 → 权限化行动 → 回归网 → 演进护栏"
端到端可复现。

## 二、模块强项（按证据）

1. **零新依赖**：`pydantic + pyyaml + 标准库`，ontology 模块不 import
   agentscope（`docs/ontology.md` 头注），私有化部署场景的硬要求。
2. **确定性**：`jsonld.py` 固定键序 + `sort_keys=True`；语料定向合成 seed 固定——
   同输入必同输出，这是"可审计交付物"的地基。
3. **错误码契约**：9 个 ONTO-xxx（`validation.py` 文档头 + 243 行专项测试），
   校验不抛异常、返回 report，由调用方决定 fail——记录与谓词分离。
4. **存储纪律**：全部写路径走 `fsutil.atomic_write_text`（temp + `os.replace`）；
   加载宽容（损坏条目跳过不炸 CLI）；工作区 > 内置，用户可覆盖内置本体。
5. **LLM 诚实原则**：`extract.py` 的 LLM 注解失败一律回退规则路径且 trace 如实标
   `rule`，绝不声称 LLM 参与过——与仓库其余部分的"诚实"哲学一致。
6. **桥接纯函数**：`skills_bridge.py` 检索时动态推导、不持久化、不改
   SkillRecord；未声明 tag 直接忽略，不给检索引入幽灵节点。
7. **狗粮锁定**：内置本体必须通过自己的校验器（架构守卫测试），内置与产品互证。
8. **权限管线与本体天然契合**（本次步骤4验证）：AgentScope `PermissionEngine`
   把规则匹配委托给工具的 `match_rule` 钩子——用 is-a 闭包实现"规则内容 = 类
   CURIE"后，**审批路由由物料分类驱动**：重新分类改 ABox 类型断言，权限管线
   一行不改。引擎求值顺序（deny→ask→…→allow）保证战略级先落 ASK，不会被
   `RawMaterial` 的 ALLOW 规则吞掉；`DONT_ASK` 把 ASK 转 DENY，无人值守绝不
   静默执行。

## 三、诚实缺口（首轮列出，2026-09-28 刷新）

### P0 — 影响"语义层"主张本身

- ~~**没有查询层。**~~ **已打通互操作**：`sparql_interop.py` 把导出的
  JSON-LD 灌进 rdflib（241 triples），SPARQL 复答三个 CQ 的结构层，并以
  `tests/test_ontology_jsonld.py::test_schema_export_parses_as_plain_graph`
  锁定"默认图自包含"的导出形状。边界保持诚实：rdflib 是**示例级可选依赖**
  （未进 pyproject），仓库核心仍零依赖；内置 SPARQL 端点仍不做。
- ~~**CQ 无测试载体。**~~ **已解决**：`tests/test_supply_chain_demo.py`
  四个测试固化 CQ1-3 黄金答案（齐套日期、影响面、触发/路由/建议量），
  进入 `make test` 主回归。

### P1 — 影响长期演进

- **表达力上限。** 无 cardinality、无传递/对称/函数性公理、无 SWRL/SHACL-full
  规则引擎；业务规则只能写成代码函数。步骤3 README 已诚实声明，但这意味着
  "本体承载逻辑"的深度有天花板。（未变，接受）
- ~~**无 schema diff/迁移。**~~ **诊断已解决**：`ontology diff`（D1-D4 +
  ABox 影响面 + exit 1）。**迁移执行器仍无**：diff 告诉你哪些个体受影响，
  改写它们仍要手工——这是下一档的真实工程项。

### P2 — 体验与鲁棒

- ~~概念模型无可视化导出~~ → **已解决**：`ontology export --format mermaid`
  （`diagram.py`，确定性，双语显示名）。
- `extract.py` 的 `match_keywords` 是子串匹配，对中文构词变化会漏（"铜线"命中
  "漆包铜线"可以，"漆包线"就漏了）；LLM 路径可补但依赖 MiMoClient。（未变）
- Web 侧只有只读 JSON API，无图谱 UI。（未变；Mermaid 导出已可作为轻量替代）

## 四、风险

| 风险 | 现状 | 建议 |
|---|---|---|
| 范围蔓延 | 本体边界靠文档纪律（步骤1 README），无 gate 强制 | 把"本体覆盖边界"写进 engagement 的 `success_criteria` gate 字段，变更走正式流程 |
| 本体腐烂 | ~~无评审/回归机制~~ → CQ 黄金测试已进主回归 | 保持纪律：数据变化 = 有意更新黄金答案并说明原因 |
| 双源真值 | ERP 是真源，ABox 是投影；无 connector→ABox 同步 | 明确 ABox 的"快照"语义，接 ERP 时补一条 connector→ABox 刷新路径 |

## 五、下一步（按 ROI 排序，2026-09-28 刷新）

1. **ABox 迁移执行器（1-2 天）**：消费 `ontology diff` 的影响面清单，
   生成"旧断言 → 新断言"改写方案供人工确认——把第 6 步从诊断推到执行。
2. **connector→ABox 同步**：与真实 ERP 对接时一并做，不提前设计。
3. **SPARQL 进 CLI（可选 extra）**：若互操作演示被客户频繁引用，再考虑
   `fde-scope ontology query`（rdflib 可选依赖），否则维持示例级。

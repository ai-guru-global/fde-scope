# Ontology 模块设计（fde-scope）

> 日期：2026-08-31 · 状态：已批准（用户确认）
> 目标：为 fde-scope 增加本体论（ontology）模块，按本体工程最佳实践设计，
> 作为横切语义层被 engagement/corpus/skills/deploy 消费，并为 LLM 提供领域 grounding。

## 1. 背景与动机

fde-scope 已有稳定的领域概念：18 阶段 SOP 状态机、10 个 gate、10 个连接器、
corpus 引擎、AgentScope deploy 装配、skills 沉淀库。但这些概念只存在于
pydantic 模型与文档中，机器不可查询、不可互操作：

- corpus 的 category 是自由字符串，覆盖度分析无法做"概念级"聚合（含祖先概念）；
- skills 的四类分类 + tags 是扁平标签，检索无语义扩展（broader/narrower）；
- engagement/deploy 的领域概念（Phase/Gate/Connector/AgentSpec…）没有标准
  序列化，无法被外部工具（图谱、SPARQL、其他仓库的本体）消费；
- 部署出去的 Agent 缺少一份机器可读的领域词汇表做 grounding。

本体模块把上述概念形式化为 TBox（模式）+ ABox（实例），零新依赖实现，
JSON-LD 标准导出保证互操作。

## 2. 非目标（v0 明确不做）

- 不引入 rdflib / pySHACL / OWL 推理机（方案 B 被否决，理由见 §3）；
- 不做 SPARQL/Turtle（留给未来 optional extra，方向不冲突）；
- 不触碰 engagement 状态机、gate 注册表、权限管线（AGENTS.md 危险区零接触）；
- 不改变现有 corpus/skills 行为——P2/P3 一律默认关闭，flag 开启才生效；
- 不做任意 annotation property 机制（label/comment/deprecated 为固定一等字段）。

## 3. 方案选择记录

| 方案 | 结论 |
|---|---|
| A. 原生轻量本体核心（零新依赖，pydantic + YAML 数据文件 + JSON-LD 导出） | **采纳** |
| B. rdflib 全栈 RDF/OWL/SPARQL（optional extra） | 否决：依赖重、与 pydantic 风格冲突、P1 即付集成成本；且 JSON-LD 已是 W3C 标准 RDF 序列化，互操作不打折。B 可作为 A 之上的未来演进。 |
| C. SKOS-lite 最小分类法 | 否决：无属性体系/ABox/互操作导出，不满足"按本体最佳实践"的完整预期。 |

## 4. 最佳实践对照（本设计如何落实）

| 实践 | 落实 |
|---|---|
| TBox/ABox 分离 | `OntologySchema`（模式工件）与 `InstanceStore`（实例工件）两类模型、两类文件，store 记录 `ontology_ref`（TBox id+version）并在加载时校验匹配 |
| IRI/命名空间纪律 | 所有元素用 CURIE（`fde:Phase`），prefix→IRI 表进 TBox；base IRI 用仓库自有命名空间 `https://ai-guru-global.github.io/fde-scope/ontology/`；校验器拒绝未声明前缀 |
| 分类法用 SKOS | skills 四类分类、corpus 类目表达为 `skos:ConceptScheme` / `skos:Concept`（`skos:broader`），不自造分类词汇 |
| 复用标准词表 | rdfs（label/comment/subClassOf）、owl（deprecated/versionInfo）、dcterms（created）、skos、xsd（数据类型映射） |
| 领域复用 | manufacturing overlay 采用 ISA-95 企业层级（Enterprise→Site→Area→WorkCenter→WorkUnit→Equipment） |
| 校验先行 | SHACL-lite 规则校验器（错误码 ONTO-xxx），内置 TBox 本身必须通过校验（吃自己的狗粮） |
| 标准序列化 | JSON-LD 1.1 导出（确定性输出 + golden-file 测试） |
| 版本化 | TBox 带 `version`；store 与 TBox 版本不匹配报 ONTO-040 |
| 数据文件化 | 内置本体为包内只读 YAML（与 profiles 数据驱动风格一致），用户本体/实例在 `.fde_scope/ontology/` 工作区 |

## 5. 模块结构

```
fde_scope/ontology/
├── models.py        # TBox + ABox pydantic 模型
├── validation.py    # SHACL-lite 校验器（错误码 ONTO-xxx）
├── jsonld.py        # JSON-LD 1.1 导出（schema 与 store）
├── store.py         # 文件存储：内置只读 schema + 工作区实例库
├── extract.py       # (P2) 语料概念抽取（规则为底 + llm=None 可选增强）
├── skills_bridge.py # (P3) 技能 ↔ SKOS 概念桥接与检索扩展
└── data/
    ├── fde_core.yaml        # FDE 基础本体（TBox）
    ├── mfg_overlay.yaml     # ISA-95 工业 overlay（imports fde_core）
    └── corpus_taxonomy.yaml # (P2) 语料类目概念体系（SKOS）
```

存储布局：

- 包内（只读，随 wheel 分发）：`fde_scope/ontology/data/*.yaml`
- 工作区（用户可写）：`.fde_scope/ontology/schemas/<id>.yaml`（用户自定义 TBox）、
  `.fde_scope/ontology/stores/<id>.json`（ABox 实例库）
- 全部写入走 `fde_scope/fsutil.atomic_write_text`（AGENTS.md 不变量 4）。

## 6. 数据模型

### TBox `OntologySchema`

```python
class Namespace(BaseModel):
    prefix: str          # "fde"
    iri: str             # "https://ai-guru-global.github.io/fde-scope/ontology/core#"

class OntClass(BaseModel):
    curie: str                       # "fde:Phase"
    label: str
    label_zh: str | None = None
    comment: str | None = None
    sub_class_of: list[str] = []     # 父类 CURIE（允许多继承，校验无环）
    deprecated: bool = False

class ObjectProperty(BaseModel):
    curie: str                       # "fde:has_phase"
    label: str
    domain: str                      # 类 CURIE
    range: str                       # 类 CURIE
    inverse: str | None = None
    sub_property_of: str | None = None

class DataProperty(BaseModel):
    curie: str
    label: str
    domain: str
    range: Literal["string", "integer", "number", "boolean", "datetime", "iri"]

class OntologySchema(BaseModel):
    id: str                          # "fde-core"
    version: str                     # "1.0.0"
    base_iri: str
    imports: list[str] = []          # 依赖的 TBox id（overlay 机制）
    namespaces: list[Namespace]
    classes: list[OntClass]
    object_properties: list[ObjectProperty]
    data_properties: list[DataProperty]
```

### ABox `InstanceStore`

```python
class Individual(BaseModel):
    curie: str                                   # "ex:guming-engagement"
    types: list[str]                             # 类 CURIE（多类型合法）
    object_assertions: dict[str, list[str]] = {} # 属性 CURIE → 个体 CURIE 列表
    data_assertions: dict[str, list[Any]] = {}   # 属性 CURIE → 字面量列表

class InstanceStore(BaseModel):
    id: str
    ontology_ref: str                # "<schema-id>@<version>"，加载时校验
    namespace: str | None = None
    individuals: list[Individual] = []
```

数据类型封闭枚举映射 xsd：string→`xsd:string`、integer→`xsd:integer`、
number→`xsd:double`、boolean→`xsd:boolean`、datetime→`xsd:dateTime`、iri→`@id`。

## 7. 内置本体内容（P1 交付物）

### fde_core.yaml（FDE 基础 TBox）

建模项目现有领域，不发明新概念：

- 顶层类：`fde:Engagement`（FDE 交付项目本身，对象属性 `fde:has_phase` 的 domain）、
  `fde:Skill`、`fde:DataSource`
- 超类：`fde:Artifact`（子类 CorpusReport/EvalReport/Runbook/HandoffPackage）、
  `fde:Component`（子类 Connector/AgentSpec/Workspace/Tenant）、
  `fde:ControlFlow`（子类 Zone/Phase/Gate/GateResult）、
  `fde:Evaluable`（子类 Metric）
- 对象属性（~12 条）：`fde:has_phase`（Engagement→Phase）、`fde:guarded_by`
  （Phase→Gate）、`fde:produces`（Phase→Artifact）、`fde:connects_source`
  （Connector→DataSource）、`fde:bound_to`（AgentSpec→Connector）、
  `fde:evaluates`（EvalReport→Metric）、`fde:captures_experience`（Skill→Phase）、
  `fde:part_of`（递归组装，工业层级复用）等
- 数据属性：`fde:slug`、`fde:status`、`dcterms:created` 等
- SKOS：`fde:SkillCategoryScheme`（research/implementation/optimization/
  methodology 四概念，对齐 `skills/models.py` 枚举值）

### mfg_overlay.yaml（ISA-95 工业 overlay，imports fde_core）

- 层级类：`mfg:Enterprise`、`mfg:Site`、`mfg:Area`、`mfg:WorkCenter`、
  `mfg:WorkUnit`、`mfg:Equipment`（经 `fde:part_of` 组装）
- 工件类：`mfg:FATReport`、`mfg:SATReport`、`mfg:SafetyAssessment`、
  `mfg:ConformityDeclaration`（Artifact 子类）
- KPI 类：`mfg:OEE`、`mfg:MTBF`、`mfg:FPY`、`mfg:DPMO`（Metric 子类，
  对齐 `eval/manufacturing_metrics.py`）
- 传感器：`mfg:Sensor`（Equipment 子类）、`mfg:monitored_by`

### corpus_taxonomy.yaml（P2 交付）

- `fde:CorpusCategoryScheme`：SKOS 概念树（首层对齐 ticket/manufacturing
  场景常用类目：billing/outage/onboarding/quality/logistics/safety…），
  每概念带 `match_keywords`（中英）供规则抽取
- 概念树随客户现场扩展，用户可放工作区同名 schema 覆盖

## 8. 校验（SHACL-lite）

`validate_schema(schema) -> ValidationReport` / `validate_store(store, schema)`
→ `ValidationReport { ok: bool, errors: list[ValidationIssue] }`，错误码稳定：

| 码 | 规则 |
|---|---|
| ONTO-001 | `sub_class_of` 层级含环 |
| ONTO-002 | `sub_property_of` / `inverse` 引用含环或不存在 |
| ONTO-010 | 类型引用了未声明的类（封闭词表） |
| ONTO-011 | 断言使用了未声明的属性（封闭词表） |
| ONTO-020 | 对象/数据断言违反属性 domain/range |
| ONTO-021 | 对象断言指向不存在的个体（引用完整性） |
| ONTO-030 | CURIE 前缀未在 namespaces 声明 |
| ONTO-040 | store 的 `ontology_ref` 与 TBox id/version 不匹配 |

原则：**校验不阻断写入**（存储层宽容），由调用方（CLI/流水线）决定是否
fail——记录与谓词分离，与 gate 哲学一致。overlay 的校验在 import 合并视图上做。

## 9. JSON-LD 导出

- `schema_to_jsonld(schema)`：`@context` 展开全部前缀；类→`@type: rdfs:Class`
  + `rdfs:subClassOf`；对象/数据属性→`@type: rdf:Property` + `rdfs:domain/range`；
  SKOS 概念→`@type: skos:Concept` + `skos:broader`；`deprecated`→`owl:deprecated`。
- `store_to_jsonld(store)`：`@graph` 个体展开，CURIE 全部解析为绝对 IRI。
- 输出确定性（键排序稳定），golden-file 测试锁定格式。

## 10. CLI 与 Web

CLI 新增 `ontology` 子应用（typer，挂在 `fde-scope` 主 app）：

- `fde-scope ontology list` — 内置 + 工作区 schema/store 清单
- `fde-scope ontology validate <schema-id>` — 校验 TBox，exit 1 + 错误码表
- `fde-scope ontology check <store-id>` — 校验 ABox（对 `ontology_ref` 的 TBox）
- `fde-scope ontology export <schema-id|store-id> --format jsonld -o FILE`

P2/P3 追加：`corpus --ontology`（可选注解阶段）、`skills search --concept <CURIE>`。

Web 控制台（P1）只读 GET：`/api/ontology/schemas`、`/api/ontology/schema/{id}`、
`/api/ontology/store/{id}`；前端视图留待后续。

## 11. 分期集成

| 期 | 内容 | 接触面 | 回归保障 |
|---|---|---|---|
| P1 核心 | ontology 包 + fde_core/mfg_overlay + 校验 + JSON-LD + CLI/Web 路由 + docs/ontology.md + architecture.md 增补 | 全新代码 + 文档 | 不动现有行为 |
| P2 语料 | `corpus --ontology`：规则概念注解（写 `CorpusItem.metadata["ontology_concepts"]`）、`CoverageReport.concept_counts`（祖先计数合并的概念级覆盖）、synthesizer 按概念缺口定向合成、可选 LLM 分类（llm.py 注入，失败回退规则，回退后不声称 LLM） | corpus/pipeline.py、coverage_analyzer.py、synthesizer.py | flag 关闭 = 与旧行为逐字段一致（守卫测试） |
| P3 技能 | SkillRecord → SKOS 个体注解；`skills search --concept` 经 skos:broader/narrower 扩展；导出 frontmatter 增加可选 `concepts:` 行 | skills/service.py、exporters.py | 不带参数 = 旧行为 |

## 12. 错误处理

- 校验器从不抛异常中断主流程，返回报告；CLI 失败时 exit 1 + 错误码表
  （与 eval 干净退出风格一致）。
- LLM 注入沿用项目约定：`llm=None` 可选参数、失败回退规则、溯源诚实
  （不声称 LLM 生成）。
- 无凭据、无网络调用（除显式 LLM 注入路径）；凭据只走环境变量（不变量 3）。

## 13. 不变量合规（AGENTS.md）

1. gate 重评估——不触碰 `evaluate_phase_gates`；
2. 服务端生成 ID——本模块不引入服务记录 ID（individual curie 是内容寻址的
   数据工件标识，非 SkillRecord.id 同类）；
3. 凭据仅环境变量——本模块无凭据；
4. 原子写——所有工作区写入走 `fsutil.atomic_write_text`；
5. 规则授权唯一通道——不触碰 deploy/permission；
6. agentscope 窗口——本模块零 agentscope 依赖，不触碰 pyproject extra 窗口。

## 14. 测试策略

- 单测：模型 round-trip、每个错误码至少一条正/反用例、JSON-LD golden 文件、
  内置 TBox 加载即通过校验、overlay import 合并解析、store 原子写（tmp_path）。
- CLI：typer CliRunner 覆盖全部 ontology 命令（含失败 exit 1）。
- P2 守卫：`--ontology` 关闭时 pipeline 输出与旧版逐字段一致；开启时注解/概念
  覆盖/定向合成的确定性规则测试 + LLM 回退测试（mock）。
- P3：概念扩展检索（broader/narrower）与 frontmatter 导出单测。
- 全量 `make test` + `ruff check fde_scope tests && ruff format --check fde_scope tests`。

## 15. 验收标准

1. `fde-scope ontology list / validate fde-core / validate mfg-overlay` 全绿；
2. `fde-scope ontology export fde-core --format jsonld` 产出合法 JSON-LD
   （golden 文件一致），外部 RDF 工具可解析（结构层面验证）；
3. 内置两个 TBox 通过 `validate`（吃狗粮）；故意破坏样例触发对应错误码；
4. P2：`corpus --ontology` 开启后 CorpusReport 出现 concept_counts，关闭后
   与旧行为一致；P3：`skills search --concept` 命中 broader/narrower 扩展；
5. 全量测试 + ruff 干净；docs/ontology.md 与 architecture.md 已更新。

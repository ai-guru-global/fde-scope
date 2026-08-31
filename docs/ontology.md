# Ontology 语义层

> 把 FDE 领域概念（Phase/Gate/Connector/CorpusItem/Skill/KPI…）形式化为
> 机器可读本体：TBox（模式）+ ABox（实例），SKOS 分类法，JSON-LD 1.1 导出。
> 零新依赖：pydantic + pyyaml + 标准库；不导入 agentscope。

## 模块地图

| 文件 | 职责 |
|---|---|
| `fde_scope/ontology/models.py` | TBox/ABox 模型 + CURIE 工具 + xsd 类型映射 |
| `fde_scope/ontology/validation.py` | SHACL-lite 校验器（错误码 ONTO-xxx）+ overlay import 合并 |
| `fde_scope/ontology/jsonld.py` | 确定性 JSON-LD 1.1 导出（双语 label 走 language map） |
| `fde_scope/ontology/store.py` | 内置只读 schema + 工作区 schemas/stores（原子写） |
| `fde_scope/ontology/extract.py` | ConceptExtractor：match_keywords 规则抽取 + 祖先链并入 + LLM 可选（失败回退 rule） |
| `fde_scope/ontology/skills_bridge.py` | SkillRecord ↔ SKOS 桥接（category 概念 + tag CURIE + narrower 闭包，纯函数） |
| `fde_scope/ontology/data/*.yaml` | 内置本体：`fde-core`（FDE 基础+技能四类）+ `fde-corpus-taxonomy`（语料概念体系）+ `mfg-overlay`（ISA-95） |

## 存储布局

- 包内（只读）：`fde_scope/ontology/data/*.yaml`
- 工作区：`<data-root>/.fde_scope/ontology/schemas/<id>.yaml`、`stores/<id>.json`
- 查找优先级：工作区 > 内置（用户可覆盖内置 schema）

## 校验错误码

| 码 | 含义 |
|---|---|
| ONTO-001 | sub_class_of 层级含环 |
| ONTO-002 | sub_property_of / inverse 引用含环或不存在 |
| ONTO-010 | 引用未声明的类（sub_class_of / domain / range / rdf:type） |
| ONTO-011 | 引用未声明的属性或概念（断言 / sub_property_of / inverse / skos:broader） |
| ONTO-020 | 断言违反 domain/range（is-a 闭包判定）或字面量类型不符 |
| ONTO-021 | 对象断言指向不存在的个体 |
| ONTO-030 | CURIE 非法或前缀未声明 |
| ONTO-040 | store 的 ontology_ref 与 TBox id/version 不匹配 |

校验不阻断写入（存储层宽容），由 CLI/调用方决定是否 fail——记录与谓词分离。

## CLI

    fde-scope ontology list                      # 内置 + 工作区清单
    fde-scope ontology validate fde-core         # 校验 TBox（exit 1 = 失败）
    fde-scope ontology check <store-id>          # 校验 ABox（exit 1 = 失败）
    fde-scope ontology export fde-core -o out.jsonld   # JSON-LD 导出

## Web（只读）

    GET /api/ontology/schemas
    GET /api/ontology/schema/{id}
    GET /api/ontology/store/{id}

## 分期路线

- **P1（已完成）**：核心 + 内置本体 + CLI/Web + 文档。
- **P2（已完成）**：corpus --ontology——概念注解、概念级覆盖度（祖先合并）、定向合成（见下）。
- **P3（已完成）**：skills SKOS 桥接——`skill list --concept` 经 broader/narrower 扩展（见下）。

## P2 — 语料引擎语义增强（corpus --ontology）

开启后 forge 管线多出一道注解与一个覆盖维度，全程可关（零行为变化）：

    fde-scope corpus -i tickets.csv --ontology

数据流（`CorpusForge.forge_rows`）：

1. **清洗后的 real items** 逐条经 `ConceptExtractor.annotate` 打上
   `metadata["ontology_concepts"]`（命中概念 + 祖先链，来源 `rule`/`llm`
   记入 trace `annotate:{source}`；LLM 缺失/失败诚实回退规则）。
2. **CoverageAnalyzer** 在类目计数之外计算 `concept_counts`，低于
   `min_samples_per_category` 的概念进入 `concept_gaps`（写入 JSON 报告）。
3. **定向合成**：每个概念缺口由「注解了该概念的真实样本」做种子突变
   （纯规则、seed 固定，确定性）；无真实锚点的概念缺口诚实跳过——
   不凭空捏造。产物带独立 id 命名空间（`syn-fde:cc-*`）与
   `synthesize:concept` trace。

CLI 输出在类目缺口下追加概念覆盖行；HTML/JSON 报告同源。

## P3 — 技能库 SKOS 桥接（skill --concept / export --ontology）

桥接是检索时的纯函数推导（`skills_bridge.py`），**不持久化**、不改
SkillRecord 模型：

- `skill_concepts(record, schema)`：category 映射到 `fde:cat-*` 概念
  （需 schema 声明 SkillCategoryScheme）+ tags 中已声明的 CURIE；
  未声明 tag 忽略，不给检索引入幽灵节点。
- `expand_concept(curie, schema)`：自身 + narrower 递归闭包
  （独立实现，技能检索不依赖 corpus）。

用法：

    fde-scope skill list --concept fde:cat-implementation   # 类目概念检索（含 narrower 扩展）
    fde-scope skill export <id> --format agentscope --ontology
    # → SKILL.md frontmatter 追加可选行: concepts: fde:cat-implementation

`--concept` 查询未声明概念 → exit 2；不带 flag 时行为与旧版逐字节一致。

## 作者指南（YAML）

schema 顶层字段：`id / version / base_iri / imports / namespaces / classes /
object_properties / data_properties / concept_schemes`。所有引用写 CURIE
（`fde:Phase`），前缀必须在 `namespaces` 声明。改内置本体 = 复制到工作区
schemas/ 同名覆盖，或在 `data/` 中以版本号演进（内置本体由狗粮测试锁定：
必须通过自己的校验器）。

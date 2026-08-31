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
| `fde_scope/ontology/data/*.yaml` | 内置本体：`fde-core`（FDE 基础）+ `mfg-overlay`（ISA-95） |

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

- **P1（本期）**：核心 + 内置本体 + CLI/Web + 文档。
- **P2**：`corpus --ontology`——概念注解、概念级覆盖度（祖先合并）、定向合成。
- **P3**：skills SKOS 桥接——`skills search --concept` 经 broader/narrower 扩展。

## 作者指南（YAML）

schema 顶层字段：`id / version / base_iri / imports / namespaces / classes /
object_properties / data_properties / concept_schemes`。所有引用写 CURIE
（`fde:Phase`），前缀必须在 `namespaces` 声明。改内置本体 = 复制到工作区
schemas/ 同名覆盖，或在 `data/` 中以版本号演进（内置本体由狗粮测试锁定：
必须通过自己的校验器）。

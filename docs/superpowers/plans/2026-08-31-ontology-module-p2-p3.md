# Ontology 模块 P2+P3 实施计划（corpus 语料增强 / skills 技能桥接）

> 日期：2026-08-31 · 状态：执行中
> 依据：docs/superpowers/specs/2026-08-31-ontology-module-design.md（已批准，§7/§11/§14）
> P1 已落地 master（commit a1f8d94 + 049a5ca）。本计划覆盖 P2 与 P3 全部剩余工作。
> 执行方式：TDD、每任务一提交（master 直接提交为仓库惯例）。

## 总原则（来自规格，执行时不可违背）

1. **flag 关闭 = 旧行为**：P2 `ontology=None` 时 pipeline 走完全相同代码路径；
   P3 不带 `--concept`/`--ontology` 时输出逐字节一致。守卫测试锁定。
2. **LLM 诚实**：LLM 分类失败回退规则后，trace 不声称 LLM（`annotate:rule`）。
3. **零新依赖、零 AGENTS.md 危险区**：不触碰 engagement/gate/deploy 权限管线。
4. 写入走 `fsutil.atomic_write_text`（本计划实际不新增写入路径，OntologyStore 既有）。
5. 验证门：`.venv/bin/python -m pytest <相关文件> -q`、
   `.venv/bin/python -m mypy fde_scope/ontology fde_scope/corpus fde_scope/skills`、
   `ruff check fde_scope tests && ruff format --check fde_scope tests`、全量 pytest。

## P2 语料增强

### P2.1 corpus_taxonomy.yaml 内置语料概念体系

文件：`fde_scope/ontology/data/corpus_taxonomy.yaml`（新建）

- `id: fde-corpus-taxonomy`、`version: 1.0.0`、`imports: []`
- namespaces：`fde`（同 fde-core 的 core IRI）+ `skos`
- `concept_schemes`: `fde:CorpusCategoryScheme`，首层概念对齐规格 §7：
  billing / outage / onboarding / quality / logistics / safety；
  billing 与 outage 各带 2 个 narrower 子概念（演示树结构，供 P3 narrower 扩展测试复用）；
  每概念 `match_keywords` 中英混合（规则抽取依据）
- 狗粮：`tests/test_ontology_store.py::test_builtin_schemas_self_validate` 自动覆盖（遍历全部内置 schema）

测试（追加到 `tests/test_ontology_models.py` 或新建 `tests/test_ontology_extract.py` 的 P2.1 段）：
- 加载 `fde-corpus-taxonomy` 存在且 validate 通过
- 每个首层概念 `match_keywords` 非空
- billing 的 narrower 子概念存在且子概念 broader 指回父概念

### P2.2 extract.py ConceptExtractor

文件：`fde_scope/ontology/extract.py`（新建）

```python
class ConceptExtractor:
    def __init__(self, schema: OntologySchema, llm: MiMoClient | None = None): ...
    def extract(self, text: str) -> list[str]          # 规则命中（含去重，按概念序稳定）
    def ancestors(self, curie: str) -> list[str]        # 沿 skos:broader 向上（不含自身，环安全）
    def expand(self, curie: str) -> set[str]            # 自身 + 全部 narrower 递归闭包
    def annotate(self, item: CorpusItem) -> CorpusItem  # metadata["ontology_concepts"] = 命中+祖先；trace 追加 annotate:llm / annotate:rule
```

- keyword 索引：遍历 `concept_schemes[].concepts[].match_keywords`，ASCII 关键词大小写不敏感，
  中文子串匹配；命中判定 = `keyword.lower() in text.lower()`
- 返回概念含 **命中概念的祖先链**（概念级覆盖需祖先合并）
- LLM 路径：`llm.available` 时可尝试 LLM 分类（`_classify_llm`），任何异常/解析失败
  回退规则结果；trace 由 annotate 写（成功 `annotate:llm`，回退 `annotate:rule`）。
  v0 中 LLM 失败即回退，不允许半途混合
- 不 import corpus 侧以外的东西；对 CorpusItem 的依赖放 TYPE_CHECKING（实际 annotate 需要运行时导入——
  放在方法内局部导入避免循环：corpus → ontology（extract），ontology 不得顶层 import corpus）
- **循环依赖红线**：`fde_scope/ontology/extract.py` 顶层禁止 `from ..corpus import ...`；
  annotate 的 CorpusItem 参数类型用 TYPE_CHECKING + 方法内局部导入

测试（`tests/test_ontology_extract.py` 新建）：
- 中文/英文关键词命中；大小写不敏感
- 命中子概念返回祖先链（如命中 billing-refund → [fde:cc-billing-refund, fde:cc-billing]）
- 无命中返回 []；纯规则（llm=None）
- LLM mock 可用 → annotate:llm；LLM 抛异常 → 回退规则 annotate:rule
- expand 的 narrower 闭包正确

### P2.3 CoverageReport 概念覆盖

文件：`fde_scope/corpus/types.py`、`fde_scope/corpus/coverage_analyzer.py`

- `types.py`：新增 `ConceptGap(BaseModel)`：`concept: str, current_count: int, target_count: int` +
  `shortfall` property（镜像 CategoryGap）；
  `CoverageReport` 增加两个字段：
  `concept_counts: dict[str, int] | None = None`、`concept_gaps: list[ConceptGap] | None = None`
  （None = 本体未启用；`save_report_json` 改用 `model_dump_json(indent=2, exclude_none=True)`，
  CorpusReport 现有字段无 None 值，旧行为 JSON 逐字节不变）
- `coverage_analyzer.analyze` 增加可选参数 `concept_counts: dict[str, int] | None = None`
  （祖先合并计数由调用方算好传入——analyzer 保持纯函数性）；
  concept_counts 非 None 时填充字段并按 `min_samples_per_category` 算 concept_gaps

测试（`tests/test_coverage.py` 追加）：
- 传入 concept_counts 时 report 字段正确、gaps 按阈值
- None 时两字段为 None；`model_dump_json` 不含 concept_counts 键

### P2.4 pipeline --ontology 注解接入 + 关闭守卫

文件：`fde_scope/corpus/pipeline.py`

- `CorpusForge.__init__(config, llm=None, ontology: OntologySchema | None = None)`
- `ontology` 非 None 时构建 `ConceptExtractor(ontology, llm=llm)`；
  `_forge` 在清洗后（real_items 就绪）对每个 item `extractor.annotate`；
  coverage 分析时传入祖先合并 concept_counts；
  合成产物（P2.5）同样注解
- 关闭时（ontology=None）：不构建 extractor、不进注解分支、coverage 不传 concept_counts
- 概念计数实现：对注解后的 items，`Counter` 展开 metadata["ontology_concepts"]（祖先已在注解时并入）

测试（`tests/test_corpus_pipeline.py` 追加）：
- **守卫**：ontology=None 的 CorpusReport.model_dump_json(exclude_none=True) 与改造前基线逐字段一致
  （构造旧行为参照：直接调用同一 forge 的非注解路径——由实现保证走同一分支，测试用
  `json.loads` 比较除 coverage.concept_* 外的所有键）
- 开启时：real/synthetic items 的 metadata["ontology_concepts"] 含祖先、trace 有 annotate:*
- 开启时 coverage.concept_counts 祖先合并正确、concept_gaps 出现

### P2.5 synthesizer 概念缺口定向合成

文件：`fde_scope/corpus/synthesizer.py`

- `fill_gaps(real_items, gaps, per_gap_cap=None, concept_gaps=None, extractor=None)`
- 概念缺口处理：shortfall>0 的 concept gap，seeds = metadata["ontology_concepts"] 含该概念的 real items；
  seeds 为空则跳过（诚实：无真实锚点不硬凑）；合成 `min(per_gap_cap or shortfall, shortfall)` 条；
  产物 `category` = seeds 众数 category、`metadata["ontology_concepts"]` = 该概念 + 祖先、
  `trace` 含 `synthesize:concept`
- LLM 路径不扩展（概念合成走规则模板，保证确定性）

测试（`tests/test_corpus_pipeline.py` 或 `tests/test_coverage.py` 追加）：
- 定向合成数量 = min(cap, shortfall)；metadata 注入正确；trace 含 synthesize:concept
- 无 seeds 跳过；gap shortfall=0 不合成

### P2.6 CLI corpus --ontology

文件：`fde_scope/cli.py`（corpus 命令）

- `ontology: bool = typer.Option(False, "--ontology", help="启用本体概念注解与概念级覆盖")`
- 开启时：`OntologyStore().load_schema("fde-corpus-taxonomy")`；缺失/损坏 → `exit 2`
- 传入 `CorpusForge(cfg, llm=client, ontology=schema)`
- 报告打印：concept_counts 存在时展示概念覆盖缺口（与 category gaps 同风格）

测试（`tests/test_cli.py` 追加，CliRunner）：
- `--ontology` 关闭：输出不含概念行
- 开启 + 输入命中关键词：报告 JSON concept_counts 出现
- 开启但 schema 缺失（monkeypatch OntologyStore.load_schema → None）：exit 2

## P3 技能桥接

### P3.1 skills_bridge.py

文件：`fde_scope/ontology/skills_bridge.py`（新建）

```python
CATEGORY_CONCEPT = {"research": "fde:cat-research", ...}  # 对齐 SkillCategory 四枚举值
def skill_concepts(record: SkillRecord, schema: OntologySchema) -> list[str]
    # category 概念（查 CATEGORY_CONCEPT）+ tags 中可解析为 CURIE 且已在 schema 概念表声明的
    # （去重、稳定序）；schema 无 SkillCategoryScheme 时仅 tag CURIE
def expand_concept(curie: str, schema: OntologySchema) -> set[str]
    # 自身 + narrower 递归闭包（复用 ConceptExtractor.expand 或独立实现——独立实现，
    # 避免为检索引入 corpus 依赖）
```

- **不持久化**：SkillRecord 不加字段；概念注解检索时动态推导（规格 P3 接触面不含 models.py）

测试（`tests/test_ontology_skills_bridge.py` 新建）：
- category → 概念；tags 带 `fde:cc-billing` 类 CURIE 且已声明 → 并入；未声明 tag 忽略
- expand_concept：broader 查询扩展出全部 narrower

### P3.2 service.search 概念扩展检索 + exporters frontmatter

文件：`fde_scope/skills/service.py`、`fde_scope/skills/exporters.py`

- `service.search(..., concept: str | None = None, ontology_schema: OntologySchema | None = None)`：
  concept=None → 与旧签名行为完全一致（零 ontology 调用）；
  concept 非 None 时要求 ontology_schema 非 None（否则 ValueError），
  过滤 = `skill_concepts(rec, schema) ∩ expand_concept(concept, schema) ≠ ∅`
- `export_skill(record, fmt, ontology=None)` / `export_many(records, fmt, ontology=None)`：
  ontology 提供时 frontmatter 增加一行 `concepts: <逗号分隔 CURIE>`（在 description 之后、`---` 之前）；
  ontology=None → 逐字节旧输出

测试（`tests/test_skills.py` 追加）：
- search concept 命中（含 narrower 扩展：查父概念命中子概念技能）
- concept 无 schema → ValueError
- export 带 ontology → frontmatter 含 concepts 行；不带 → 与旧输出逐字节相等

### P3.3 CLI + 文档 + 全量回归

文件：`fde_scope/cli.py`、`docs/ontology.md`、`docs/architecture.md`

- `skill list` 增加 `--concept`：开启时从 OntologyStore 加载 `fde-core`（技能四类在此 schema），
  缺失/概念不存在 → exit 2
- `skill export` 增加 `--ontology` flag：加载 fde-core 传入 export_skill
- docs/ontology.md 增加 P2/P3 章节（用法 + 数据流）；architecture.md 增补一句桥接说明
- 回归门：全量 pytest、ruff check + format --check、mypy（ontology/corpus/skills 三包）

测试（`tests/test_cli.py` 追加）：skill list --concept 命中/未知概念 exit 2；skill export --ontology frontmatter。

## 验收（对照规格 §15.4–5）

1. `--ontology` 开启后 CorpusReport 出现 concept_counts（祖先合并），关闭后与旧行为一致（守卫测试）；
2. `skill list --concept` 命中 broader/narrower 扩展；
3. 导出 frontmatter 可选 concepts 行；
4. 全量测试 + ruff + mypy 干净；文档已更新。

# FDE Scope 全面加强计划（Enhancement Plan）

> 本文是「加强每一个页面的每一个功能」的完整执行计划与进度台账。
> 每一条都带证据（`file:line`），做完一条勾一条。
> 约束前提见 [AGENTS.md](../AGENTS.md) 的七条不变式与 §15「明确不做」。
>
> 状态图例：`[ ]` 待办 · `[~]` 进行中 · `[x]` 已完成 · `[-]` 本轮不做（见 §15）

---

## §0 体检基线（动手前实测，非估计）

| 维度 | 实测值 | 判定 |
| --- | --- | --- |
| 测试 | 867 passed / 4 skipped / 0 failed，20.6s | ✅ 绿 |
| 覆盖率 | 92%（6973 stmts / 556 missed） | ✅ 高，但**无 fail_under 门禁** |
| `ruff check .` | 0 error（ruff 0.16.8） | ✅ |
| `ruff format --check .` | **6 files would be reformatted** | ❌ CI 阻塞步骤红 |
| `mypy fde_scope` | **12 errors in 9 files**（101 文件） | ❌ CI 阻塞步骤红 |
| Web 路由 | **57**（app.py 54 + guided_api.py 3） | ⚠️ 文档写 56，守卫漏 `patch` |
| 最大文件 | `web/app.py` 2901 行 / 165 KB | ⚠️ 单文件巨石 |
| 次大文件 | `cli.py` 1400 行 · `web/i18n.py` 1277 行（≈460 对替换） | ⚠️ |
| 覆盖率最差模块 | `cli.py` **71%** | ⚠️ |
| 面向用户的界面 | 9 个 Web 页面 ×2 语言 + catalog SPA + GTM 站 + CLI + PawApp UI + macOS/Android 壳 | — |

### P0 收口复测（同一组命令，动手后实测）

| 维度 | 动手前 | 动手后 | 判定 |
| --- | --- | --- | --- |
| `ruff check .` | 0 error | `All checks passed!` | ✅ |
| `ruff format --check .` | 6 files would be reformatted | `174 files already formatted` | ✅ 转绿 |
| `.venv/bin/python -m mypy fde_scope` | 12 errors in 9 files | `Success: no issues found in 101 source files` | ✅ 转绿 |
| `pytest -o addopts="" -q -p no:randomly` | 867 passed / 4 skipped | **876 passed / 4 skipped**，23.15s，exit 0 | ✅ +9 条新守卫 |
| Web 路由宣称 | 文档 56 / 磁贴 43 / 守卫漏 `patch` | **11 处全部 57**，且装饰器扫描对齐 `app.openapi()` | ✅ 单一事实来源 |
| 发行版 `/course` | wheel 装完全页空 | 干净 venv 渲染 zh 770,509 / en 772,456 字符 | ✅ |

> 注：仓库 `addopts="-ra -q"` 会吞掉 pytest 的「N passed」汇总行，取计数需 `-o addopts=""`；
> `mypy` 不在 PATH 上，必须走 `.venv/bin/python -m mypy`（裸 `mypy` 会 `command not found`，exit 127）。

**本轮最高价值发现**：`evidence` / `handoff` / `audit` / `archive` / `delete` 五项能力
**后端已实现、测试已覆盖，但控制台 JS 从不调用**；`rollback` 更是
**领域层与 CLI 都有、Web 层完全没有端点**。也就是说 P1 几乎全是
「给已测后端接前端」，不引入新领域逻辑——风险最低、收益最高。

---

## P0 止血（0.5–1 天）：先把 CI 变绿、把坏链修好

| # | 状态 | 问题 | 证据 | 动作 |
| --- | --- | --- | --- | --- |
| P0-1 | [x] | `ruff format --check .` 失败 6 文件，CI 阻塞步骤红 | `GTM/i18n_split.py`、`GTM/mac_window.py`、`GTM/sync_log.py`、`examples/seed_mock_engagements.py`、`examples/supply_chain_ontology/sparql_interop.py`、`scripts/build_catalog_site.py` | 对这 6 文件跑 `ruff format` ✅ 173 文件全部 already formatted |
| P0-2 | [x] | `mypy` 12 错 9 文件，CI 阻塞步骤红 | 见下方明细 | 逐个修，不加 `# type: ignore` 兜底 ✅ `Success: no issues found in 101 source files`；**偏差**：markdown 那 6 处未用 `cast`（`RendererHTML.rules` 的值是 bound method，赋普通函数仍是 `[assignment]` 错），改为子类化 `RendererHTML` + `MarkdownIt(..., renderer_cls=)`，是 markdown-it-py 的官方覆写路径 |
| P0-3 | [x] | GTM 站点图片在开鉴权时 401 | `web/auth.py:59-73` 只放行 8 个 woff2；`GTM/index.html:742,746` 与 `GTM/en/index.html:756,760` 引用 `images/*.png` | `_gtm_assets` 增加两张 png（只放行确切路径，不开目录前缀）✅ `console.png`/`overview.png`，其余仍 401 |
| P0-4 | [x] | GTM「GitHub」链接指向 `/`（应用首页），中英双页皆错 | `GTM/index.html:533,845,909`、`GTM/en/index.html` 同位置；**实测为 4 处**（计划漏了头部导航 `:497` 的 `GITHUB`） | 改为真实仓库地址，或去掉该入口 ✅ **偏差**：走「改标签 + 指向应用内读者」而非外链——`tests/test_web.py:1506` 明确禁止产物出现 `href="https?://"` 与 `target="_blank"`，不为此削弱既定不变量。导航 `控制台`/`CONSOLE`、CTA `打开控制台`/`Open the console`、社区档 CTA → `/docs/readme` 的 `阅读 README`/`Read the README`、页脚 `Console`，并移除误导性的 star 图标 |
| P0-5 | [x] | `course-level-1/`（26 篇 ≈960 KB）在包外，wheel/sdist 装完 `/course` 直接空 | `web/course.py:368` 用 `parents[2]/course-level-1`；`course.py:6` 自认「A wheel install has no course-level-1/」；`pyproject.toml:94-98` 只打包 `fde_scope` | 纳入包数据并随发行版分发；缺目录时的降级提示保持 ✅ `pyproject.toml:100` `force-include = { "course-level-1" = "fde_scope/_data/course-level-1" }`、`:103` sdist `include` 加 `course-level-1`；`course.py:384 _choose_root` / `:399 _default_root` 改为「checkout 优先、包数据兜底」，降级提示保留。**实测**（干净 venv）：`uv build` 走 sdist→wheel 链，wheel 765,757 B 含 26 个课程文件、sdist 705,746 B；装完在 `/tmp` 下渲染 `_default_root()` 落在 `site-packages/fde_scope/_data/course-level-1`，zh 770,509 字符 / en 772,456 字符 / 227 个 `<h3`、无缺目录提示。守卫 `tests/test_architecture_guard.py:79 test_wheel_ships_the_course_the_reader_depends_on` + `tests/test_web.py:386,398,415` |
| P0-6 | [x] | 路由数守卫漏 `patch`，断言 56 而真实 57——**测试通过但是错的** | `tests/test_architecture_guard.py:109` 正则无 `patch` | 正则补 `patch`，同步 4 处文档数字 ✅ **实测声明路由 57**（`app.py` 54 + `guided_api.py` 3；get 37 / post 18 / patch 1 / delete 1）。**偏差（超出原计划的「4 处」）**：漏改点扫描发现共 **11 处**宣称路由数，且 `web/i18n.py:618` 的配对字面量仍是 43——`to_en` 按 zh 串**精确匹配**替换，只改 `app.py:1453` 会让英文首页整块退回中文。守卫因此从 4 处扩到 11 处并**按 pattern 断言出现次数**（宣称消失也算失败，不只是数字变了才算）；另加**元守卫** `test_route_decorator_scan_matches_the_served_route_table`，把装饰器扫描结果对齐 `app.openapi()["paths"]`，差集恰为 `{("get","/catalog/{rest:path}"), ("get","/GTM/{rest:path}")}` 两个条件回退（仅在安装态注册；checkout 用 StaticFiles 挂载答同样路径）。**刻意保留**：`#arch` 磁贴仍写死 57 而非运行时插值——服务态计数随环境变化（checkout 里是 55），会低报接口面；由守卫把装饰器当唯一事实来源 |
| P0-7 | [x] | `/certification` 是唯一没有 favicon `<link>` 的页面 | `web/certification.py:333-341` head；四个兄弟页面都有（如 `glossary.py:288`） | 补 favicon link ✅ `certification.py` `<title>` 之后插入 `<link rel="icon" href="/static/favicon.svg">`，与四个兄弟页面同源同路径 |
| P0-8 | [x] | SVG sprite 嵌套进已有 `<svg>`——**原判定「非法」有误**（见下） | `glossary.py:293`、`course.py:540`、`sop.py:189`、`docs_reader.py:353` | 统一为 `certification.py:343` 的裸 sprite 写法 ✅ 四页的 `<svg width="0" height="0" …>__ICON_SPRITE__</svg>` 改为裸 `__ICON_SPRITE__`，9 个页面写法一致（`_ICON_SPRITE` 自带外层 `<svg …><defs>`）。**事实更正**：动手前用真实 `_ICON_SPRITE`（38 个 symbol）造了裸/嵌套两个页面对比，headless Chrome 截图 **md5 完全相同**（`80633e2d190503d1fcc07ae4141de272`）且图标正常渲染——`<svg><svg>` 在 HTML 里是合法嵌套，原计划的「非法」结论不成立。本条因此是**标记卫生/一致性**修复，不是渲染缺陷修复 |
| P0-9 | [x] | `android/fde-scope-console.apk.idsig` 被提交进版本库，而 `*.apk` 是 gitignore 的 | `git ls-files android/` | 取消跟踪并加 gitignore ✅ `git rm --cached android/fde-scope-console.apk.idsig`（**磁盘文件保留**，5492 B，仅退出版本控制）+ `android/.gitignore` 增 `*.apk.idsig`（apksigner 的签名产物，与 `*.apk` 同类） |

### P0-2 mypy 12 错明细

| 文件:行 | 错误 | 根因与修法 |
| --- | --- | --- |
| `web/sop.py:66,67`、`web/course.py:363,364`、`web/docs_reader.py:141,142` | `"RendererProtocol" has no attribute "rules"`（6 处同根因） | ~~用窄化断言/`cast` 到具体 Renderer 类型~~ → **实际做法**：`RendererHTML` 子类（`_SopRenderer` / `_DemotingRenderer` / `_DocsRenderer`）覆写 `heading_open`/`heading_close`，再用 `MarkdownIt("commonmark", {"html": False}, renderer_cls=…)` 注入。`rules` 表存的是实例的 bound method，赋普通函数仍报 `[assignment]`，`cast` 治不了根 |
| `license.py:146` | Unused `type: ignore` | 直接删 |
| `ontology/diff.py:97`、`ontology/diagram.py:26` | `DataProperty` 赋给 `ObjectProperty` 变量 | 变量注解放宽为两者的联合类型 |
| `web/auth.py:117` | `compare_digest` 的 `AnyStr` 不能是 `str \| None` | `_matches` 内在 `bool(candidate)` 之后窄化为 `str` |
| `engagement/guided.py:428` | 列表推导 `List[str]` vs `List[dict[str, Any]]` | 元素类型统一 |
| `web/app.py:612` | `CorpusForge(llm=...)` 收到 `LLMClient`，期望 `MiMoClient \| None` | 签名对齐到 `LLMClient` 协议（不要反向收窄调用方） |

### P0-4 的连带发现：GTM 产物不可复现（已修，超出原计划）

`GTM/index.html` 与 `GTM/en/index.html` 是 `python GTM/i18n_split.py` 从
`GTM/index.bilingual.html` 生成的，但两者已经漂移：中文导航标签（`SOP 文档`、
`技能手册库`）是手改产物的，从未回流到源文件；而生成器自己的 `nav_links()`
替换仍在匹配改造前的 `github.com` 外链 href（带 `target="_blank"`），因此重跑
split 会静默把它们改回去。修 P0-4 时先重写了这 3 条替换、再重新生成，并新增
`tests/test_gtm_site_guard.py`：产物必须与生成器输出逐字节相等、全链路无外链、
不得把 `href="/"` 标成 GitHub。**今后改 GTM 页面只能改 bilingual 源文件后重跑
split**，手改产物会被测试判红。

---

## §1 `/console` 工作台（`web/app.py`，最重的页面）

### 1.1 已实现但 UI 缺失的六项能力（P1 主体）

| 能力 | 后端 | 测试 | 控制台 UI | 动作 |
| --- | --- | --- | --- | --- |
| 证据留存 evidence | `app.py:380` `_file_evidence` / `_evidence_index_path:351` | `test_web.py`、`test_audit_chain.py` | ❌ 零调用 | 详情页第 9 个 tab「证据」：列表 + 上传 + sha256 展示 |
| 交接 handoff | `app.py:435`、CLI `cli.py:644` | `test_web.py` | ❌ | 详情页「交接」：生成 runbook / 打包下载 |
| 审计 audit | `app.py:303` `_export_audit_md`、`app.py:276` | `test_audit_chain.py` | ❌ | 详情页「审计」：~~链式校验状态~~ **（前提有误：无哈希链/签名，UI 按实情陈述）**+ 导出 md |
| 归档 archive | `app.py:443` `_archive` | `test_storage.py` | ❌ | 列表行操作 + 二次确认 |
| 删除 delete | `app.py:456` `_delete` | `test_storage.py` | ❌ | 列表行操作 + 输入 slug 确认（破坏性，必须双确认） |
| 回滚 rollback | **领域层 `engagement.py:117`、CLI `cli.py:521` 都有；Web 层无端点** | 领域/CLI 有测 | ❌ | 新增 `POST /api/engagements/{eid}/rollback`（走 `Engagement.rollback`，**不得**直接赋值 phase，见 §15）+ UI 选择目标阶段 |

> `docs/features.md:133` / `features-en.md:142` 已经宣称看板支持「推进/**回滚**/阻塞检查」——
> 这是文档先于实现。P1 做完这句话才成立；否则必须在 P3 改文档。

#### 1.1 落地记录（P1 已完成 ✅）

六项能力全部接线，实测全绿（`891 passed / 4 skipped`，ruff / mypy / 路由守卫均过）：

- **回滚端点**：新增 `POST /api/engagements/{eid}/rollback`（`app.py:228`），只走
  `Engagement.rollback`（未通过门禁→400、未知阶段→404、向前回滚→400），原因/操作人入审计；
  UI 为「回滚阶段」对话框，目标阶段下拉**只列当前阶段之前的**（`detailPhases.slice(0, curIdx)`）。
  两处错误映射都有测试钉住（`test_rollback_unknown_phase_is_404` / `test_rollback_forward_is_400`）。
- **详情页 8 → 11 个 tab**（+证据/交接/审计），三个懒加载面板只在打开时 fetch，
  `selectEng` 保持 3 个阻塞请求；tab 状态写入 `#t:<name>`（`history.replaceState`，
  刷新与直链恢复已实测）。**`#t:` 恢复依赖「页面加载时 hash 未被路由清洗」——boot 走
  `loadWorkbench()` 不经过 `go()`，所以直链 `/console#t:audit` 存活；但运行中给
  `location.hash` 赋值会触发 hashchange → `go('workbench')` 清 hash，因此 tab 切换必须
  继续用 replaceState**（有注释钉住）。
- **四个危险操作统一走一个确认对话框**（`dlg-action` + `openActionDialog`）：
  force 推进（原因必填，前后端双重校验）、回滚、归档、删除（**客户名原样输入**，防误删）。
  列表行按钮改为 `data-eid`/`data-customer` + `event.stopPropagation()`，客户名不再拼进
  `onclick` 属性（注入面收口）。
- **审计诚实化**：计划原文「链式校验状态」**前提有误——审计日志是单文件 append-only
  JSONL，没有哈希链也没有数字签名**（sha256 是证据文件完整性摘要，不构成防篡改）。
  UI 文案按实情陈述（zh/en），`test_console_states_audit_is_not_tamper_evident` 钉死；
  `engagement_audit` 的 `?format=md` 许可绕过已修（JSON 自由、md 导出走 `audit_export` 门）。
- **`engagement_audit` 许可修复**：`test_audit_json_is_free_but_md_export_is_licensed`。
- **i18n**：63 对新 `I18N_PAIRS` 覆盖三个新 tab、四个对话框、三个面板与全部 toast；
  `/en/console` 静态 HTML 现在除语言切换器外**零 CJK**（`test_en_console_translates_new_engagement_tabs`
  以 `leftovers == [切换器]` 收口）。CJK 检测正则定为
  `[\u3400-\u4dbf\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]`（宽版本会把 `…`/`—`/`·` 误报）。
- **鉴权枚举守卫**：`test_every_mutating_route_is_token_gated` 遍历 `app.routes` 全部
  POST/PATCH/PUT/DELETE（19 条路径 × 4 动词），任何新路由漏进白名单都会红
  （不变式 7 从「抽查一条」升级为「全量枚举」）；`test_public_paths_hold_no_mutating_route`
  兜底校验白名单本身。
- **连带修复（P0 遗留）**：四个 shell 引用的 `/static/favicon.svg` 是**死链**——资产从未存在，
  浏览器退回请求 `/favicon.ico` 也 404。新增内联 SVG 路由（入 schema、入 PUBLIC_PATHS——
  浏览器取图标不带认证头），`_OVERVIEW_HTML`/`_DASHBOARD_HTML` 补 `<link rel="icon">`；
  `test_favicon_is_served_and_public` 覆盖。路由计数 11 处宣称同步 58→59。
- **真实浏览器冒烟**（headless Chrome + CDP，隔离 profile，已随测毕关闭）：11 tab 全部渲染、
  直链 hash 恢复、force 推进（空原因被拦）、回滚 e2e（stakeholder_map→qualification）、
  证据上传（pro 许可下成功并出 `evidence.attached` 审计）、交接包 3 链接、归档取消、
  删除名不匹配被拦——控制台 0 错误。
- **遗留（记录为 P2）**：EN 控制台运行时 DOM 仍出现中文阶段名/引导内容——engagement API
  的内容层（`phases.py` / guided 文案）只有中文，无 locale 参数；属内容层双语项目，非前端缺口。

### 1.2 已有视图的逐项加强

- **workbench**：~~`advance(false)` / `advance(true)` 两个按钮不收集 reason/operator~~ **P1 已修**：force 推进改为弹窗收集原因（必填）与操作人；归档/删除行操作已补；搜索与阶段/分区筛选已补（见落地记录）。
- **详情页 8 个 tab**（`renderDetail` @ `app.py:2210`：概览/引导/SOP 阶段/Gates/Context/Corpus Forge/KPI/现场记录）→ ~~扩展为 11 个（+证据/交接/审计）；tab 状态写入 `location.hash`~~ **P1 已完成**（含懒加载与直链恢复，见 §1.1）。
- **Gates tab**：~~`recheck(slug)` 已有；补门禁失败时的「为什么没过 + 下一步做什么」结构化提示~~ **前提有误**：Gates tab 本来就渲染 guided 端点的 per-gate `next_steps`（见落地记录），无需改动。
- **Context tab**：~~六张卡片全只读 → 允许在 UI 直接编辑并走 `gdPostContext` 的既有落盘路径；补字段级校验提示~~ **P1 已完成**（JSON 编辑器 + 字段路径错误渲染，见落地记录）。
- **skills**：~~后端支持 `q`/`concept` 查询参数，前端没有搜索框~~ **前提有误（P1 核实）**：
  `loadSkills` 一直渲染 `<input id="sk-q">` 搜索框与 `sk-cat`/`sk-status` 两个下拉，
  `api_skills`（`app.py:726`）签名是 `(q, category, tag, status, profile, gate, phase)`——
  **没有 `concept` 参数**。真实缺口是后端已实现而前端未暴露的四个筛选：
  `tag` / `profile` / `gate` / `phase`。
- **deploy**：~~前端解析裸 textarea 行 → 改为后端解析并返回结构化错误~~ **P1 已完成**（见落地记录）。
- **ontology**：~~diagram / diff / validation 都有实现和 CLI 入口，Web 完全没接 → 补三个子视图~~ **P1 已完成**（见落地记录）。

#### 1.2 落地记录（P1 已完成 ✅）

- **workbench 列表搜索 + 阶段/分区筛选**：客户端过滤（矩阵就在页面里，不值得加 API 面），
  重渲染读回上次选择不重置；`test_workbench_list_has_search_and_filters`。
- ~~Gates tab 结构化提示~~ **前提有误**：Gates tab 本来就渲染 guided 端点的 per-gate
  `next_steps`（issue + advice，`app.py` renderDetail 内，注释写明「一个事实来源」）——
  无需改动。
- **Context tab JSON 编辑器**：六张卡片之上加 `<details>` 编辑器，只放行端点真正支持的六个键
  （site/safety/success_criteria/stakeholders/slos/assets），走既有 `POST …/context`；
  422 的 pydantic errors 按字段路径逐条渲染（`loc.join('.') + msg`）；
  `test_console_context_tab_has_json_editor`。
- **skills 四筛选**（tag/profile/gate/phase）：新增 `GET /api/skills/facets`
  （distinct tags / phases / gates / applies_to），`loadSkills` 渲染四个下拉并随请求发送；
  `test_skills_facets_power_the_console_filters`（含每个筛选的双向断言）。
- **deploy 服务端解析**：新增 `POST /api/deploy/parse`（`_parse_agent_lines` /
  `_parse_source_lines`），每个被丢弃的行带行号 + 原因返回，前端删掉自己的解析器、
  有错即渲染表格并拒绝生成 plan；`test_deploy_parse_reports_line_numbers` +
  `test_console_deploy_parses_on_the_server`。
- **ontology 三子视图**：`GET /api/ontology/schema/{id}/diagram`（Mermaid 源码，诚实标注
  「控制台不打包渲染器」）、`GET /api/ontology/validate/{id}`（TBox/ABox 双层，与 CLI
  validate/check 同语义）、`POST /api/ontology/diff`（D1-D4 + 全部引用工作区实例库的
  ABox 影响面）；卡片按钮 + diff 表单 + 三个渲染器；
  `test_ontology_diagram_api_*` / `test_ontology_validate_api_*` / `test_ontology_diff_api_*` /
  `test_console_ontology_view_has_three_subviews`。
- 顺带修一个真实类型问题：`MiMoReplyFn.__init__` 标注 `MiMoClient`，但 CLI 从
  `get_llm_client()` 传入的可能是 `OpenAICompatClient`——两者同继承
  `_ChatCompletionsClient`，实现只调 `complete`；标注放宽为共享基类，
  `get_llm_client()` 返回标注同步收窄。

### 1.3 控制台级缺失能力

| 缺失 | 现状 | 动作 |
| --- | --- | --- |
| 连接器面板 | 首页 10 个连接器只是**静态营销磁贴**，无可交互入口 | 新增 `/api/connectors` + 面板：列出注册表、状态（真实可用/JSONL/stub/需 `[agentscope]`）、env 是否已配（**只报布尔，绝不回显值**，见 §15 不变式 3） |
| eval 面板 | `cli.py:325` 有，Web 无 | 新增端点 + 面板 |
| flywheel 面板 | `cli.py:384` 有，但 **`cli.py:412` 硬编码打印 `"weekly_retrain scheduled: next Mon 02:00"`，且 `--agent` 除横幅外从未使用** | **先修真 CLI**（不得把假信息搬上 UI），再做面板 |
| license 面板 | `cli.py:1331/1353`（HMAC 签发）有，Web 只有审计导出的 pro+ 门控 | 新增只读面板：当前 tier、开关矩阵、到期 |
| 多进程安全 | `web/deps.py:31-43` 每 engagement 一把 `threading.Lock`，**进程内有效，多 worker 不安全** | 文档明示单 worker 约束；或改为文件锁 |

#### 1.3 落地记录（P1 已完成 ✅）

- **先修真 CLI**：`flywheel` 删除硬编码的 `"weekly_retrain scheduled: next Mon 02:00"`
  ——本进程没有调度器在跑，改为列出 `RetrainScheduler` 的**描述符**并注明
  「descriptors only — no scheduler runs inside this CLI」；`--agent` 说明改为如实
  （banner/summary 记录；挂实时流需要 runtime）；`test_flywheel_replay` 钉死不再输出假计划。
- **`/console#ops` 运维视图**（第五个视图）：四张面板——
  - **连接器** `GET /api/connectors`：导入级真值（注册表=依赖齐；模块表有而注册表无=缺
    可选依赖），凭据 env **只报布尔**（invariant 3，测试断言值不出现在响应里）；
  - **eval** `GET /api/eval/info` + `POST /api/eval/run`：指标目录 + LLM 可用性；
    mock 零配置可跑；mimo 无 LLM → 502 + 指引（不假装在跑）；test_set 路径缺失 → 404；
  - **flywheel** `GET /api/flywheel`：快照标注 `process_local: true`（引擎在内存，是本
    进程计数器）+ 任务描述符；UI 文案重复「本进程没有任何调度器在跑」；
  - **license** `GET /api/license`：tier/席位/到期/feature 开关矩阵 + `key_source`
    （env/文件/无）——**key 与签名永不出现**；`test_ops_license_api_reports_tier_without_the_key`。
- **单 worker 约束成文**：`web/deps.py::engagement_lock` docstring 写明 `threading.Lock`
  只在单进程内有效、必须 `--workers 1`、多 worker 下是 last-writer-wins 而非损坏、
  真多进程需要文件锁或数据库。
- 测试：`test_ops_connectors_api_*` / `test_ops_eval_info_and_mock_run` /
  `test_ops_flywheel_api_is_honestly_process_local` / `test_ops_license_api_*` /
  `test_console_has_ops_view`；headless Chrome 冒烟走完五视图（diff 实例、eval 真跑、
  404 友好报错、筛选、编辑器保存与坏 JSON）零意外。

---

## §2 `/` 首页概览（`_OVERVIEW_HTML` @ `app.py:1171`，10 个小节）

现状：`#sop`(18 阶段/4 分区)、`#gates`(10 门禁)、`#connectors`(10 磁贴)、`#ontology`、`#modules`(6)、`#arch`、`#practices`(七条不变式)、`#kpi`（已标注「虚构演示数据」）、`#quickstart`、`#scenarios`。全部为**导入期求值并缓存进模块全局**的 f-string（`app.py:2861-2900`）。

1. [ ] **磁贴状态与现实漂移**：`#connectors` 写「ROS2 Bag → stub」，而 git log 显示 rosbag2 真实回放已交付（`5d2dee4`、`db49e55`、`8096482`、`f5fb4cb`、`d5f340c`、`9db7bcf`）；`docs/manufacturing_scenario.md:28` 仍写「连接器 stub 已就位」→ 状态改为**由连接器注册表运行时生成**，不再手写。
2. [x] `#arch` 硬编码「Web 控制台（43 路由）」（`app.py:1453`）与真实 57 不符 → 与 P0-6 同源，改为单一事实来源。✅ 见 P0-6：11 处宣称全部对齐 57，含本页磁贴及其 `i18n.py:618` 配对字面量（漏改会让英文首页整块退回中文）；由 `test_web_route_count_claim_is_honest` 按 pattern 计数钉死。**刻意保留写死值**而非运行时插值：服务态计数随环境变化（checkout 55 / 安装态 57），插值会低报接口面，守卫已让装饰器成为唯一事实来源
3. [ ] `#kpi` 明确标注虚构（已有）→ 补「如何换成真实数据」的一行指引。
4. [ ] 首页无搜索、无暗色跟随以外的一致性检查 → 与 §10.1 i18n 守卫一并覆盖。

## §3 `/certification`（`web/certification.py`，1223 行，**本仓库页面质量标杆**）

现状：8 个锚点小节（`#landscape`…`#sources`）；`_SOURCES` 17 条来源表（`:40-157`），URL **刻意渲染为不可点纯文本**（`:1212-1223`，「provenance without an off-site jump」）；5 条实践用原生 `<details class="qa">`（`:1141-1197`，「no JS needed」`:1201`）；i18n 走**真正的配对字面量 `p(zh,en)`**（`:321`）——这是全仓最佳实践；权重条内联 `width:%`（`:300-307`）；媒体查询 960/640（`:277-285`）。

1. [x] P0-7 favicon；P0-8 sprite（本页 `:343` 已正确，作为其余页面的参照）。✅ 本页补上 `<link rel="icon" href="/static/favicon.svg">`；sprite 写法保持为其余 8 页的对齐基准
2. [ ] 语言徽标文案不一致：本页「切换到中文」vs 其他页「中文」（`:326`）→ 统一。
3. [ ] **硬编码价格与日期**：¥330/¥600/¥1200/¥198/¥298 与 `2026-09-30`（`:963,:1121`）、`2025-10-17`（`:666`）→ 抽到单一常量表并加「数据截至」标注，避免过期即误导。
4. [ ] 无自测/进度：补一个纯前端、无后端的样题自测（`<details>` 已证明可零 JS，自测需少量 JS，走既有内联模式）。
5. [ ] 把 `p(zh,en)` 模式提炼为 §10.1 i18n 迁移的范式样板（文档化，不改行为）。

## §4 `/glossary`（`web/glossary.py`，386 行）

现状：静态 `dl/dt/dd` 卡片，7 个主题组 `_GROUPS`（`:24-174`）；i18n 来自 `i18n.GLOSSARY_ZH/EN`（`:20,:266-267`，**真正的平行列表**）；`_EN_TERM` 17 条 CJK→EN 标签（`:179-197`），其完整性由测试钉住（`:10-14` docstring）；`tips[term]` **未转义插入**（仅因数据是常量才安全）。

1. [ ] **≈80 个术语却没有搜索框** → 补纯前端即时过滤（输入框 + `aria-label` + 命中高亮 + 「无结果」态）。
2. [x] P0-8 嵌套 sprite（`:293`）。✅ 改为裸 `__ICON_SPRITE__`（占位符自带外层 `<svg>`）；**注**：原「嵌套非法」判定经截图对比证伪，本条为一致性修复
3. [ ] `tips[term]` 未转义：即使当前安全，也改为经 `html.escape` 后插入，消除「以后有人加动态数据就变 XSS」的地雷。
4. [ ] `docs/features.md:133` 宣称「术语释义独立成页」，实际是**同页卡片** → P3 改文档（或真做独立页，成本更高、收益更低，选改文档）。
5. [ ] 补锚点深链与「回到顶部」，与 certification 一致。

## §5 `/course`（`web/course.py`，708 行）

现状：**实时渲染仓库根 `course-level-1/` 下 25 篇 Markdown**（`_CHAPTERS :49-250`）；wheel 安装缺失提示（`:667-685`）；单篇不可读提示（`:649-662`）；5 组导航栏（`:256-270`）；Markdown 管道转义安全（`html:False`，`:283`），并在 `<pre>` 外刻意把 `&lt;br&gt;` 还原成 `<br>`（`:431-435`）；外部 http/mailto 链接**降级为纯文本标签**（`:387-397`）。i18n 部分双语：外壳 + 25 个标题双语，**正文在两种语言下都是中文**，EN 下给出提示（`:617-628`）并用 `lang="zh-Hans"` 包裹（`:664`）——这是诚实做法，保留。

1. [x] P0-5 打包（最高优先，否则发行版整页空）。✅ 见 P0-5：课程随 wheel/sdist 分发，干净 venv 实测 zh 770,509 / en 772,456 字符、227 个 `<h3`、无缺目录提示
2. [ ] **统计靠数字符串**：`count("<h3")`、`count("<pre")`、`count("☐")`（`:514-519`）→ 改为在 Markdown 渲染阶段用 token 流统计（结构化，不再被正文里的字面量污染）。
3. [x] `heading_close` 绑到 `_heading_open`（`:363-364`，mypy 报错源）→ 随 P0-2 一并修。✅ **偏差**：未用 `cast`——`RendererHTML.rules` 存的是实例 bound method，赋普通函数仍报 `[assignment]`；改为 `class _DemotingRenderer(RendererHTML)`（`course.py:289`）覆写 `heading_open`/`heading_close`，经 `MarkdownIt(..., renderer_cls=)`（`:309`）注入，是 markdown-it-py 官方覆写路径
4. [ ] **无阅读进度** → 纯前端 `localStorage` 记录每篇已读（与主题偏好 `localStorage['fde-theme']` 同一模式，零后端）。
5. [ ] **无页内搜索** → 25 篇同页，补前端过滤（标题 + 正文）。
6. [ ] `☐` 练习项是纯文本、不可勾选 → 变为可勾选并计入进度（仍纯前端）。

## §6 `/sop`（`web/sop.py`，300 行）

现状：渲染单一文档 `docs/fde_sop_full.md`（`:37-38`）；`##` → id `s01…`（`:50-63`）；文件缺失提示（`:260-277`）；英雄标题与文档 H1 逐字节一致由漂移测试钉住（`:160-161`）。

1. [ ] **导航栏标签是从自己渲染出的 HTML 里用正则 `_H3`（`:45`）刮出来的，并在全角 `（` 处截断（`:74-76`）→ EN 页面的导航栏还是中文**（`:14-17` docstring 自认）→ 改为从 token 流拿标题结构，EN 下走配对字面量或术语表。
2. [x] P0-2 mypy（`:66-67`）、P0-8 sprite（`:189`）。✅ `class _SopRenderer(RendererHTML)`（`sop.py:49`）+ `renderer_cls=`（`:72`）；sprite 改裸占位符
3. [ ] 补 18 阶段与 `/console` SOP tab 的双向深链（页面间目前互不相通）。
4. [ ] 补当前阶段高亮（有 engagement 上下文时），无上下文时保持纯文档态。

## §7 `/docs/{slug}`（`web/docs_reader.py`，446 行）

现状：20 个 slug → 仓库文件（`_DOCS :59-100`）；未知 slug → 404（`app.py:1155-1161`）；图片白名单**只有** `("overview.png","console.png")`（`:55,:149-159`）；GitHub 风格标题锚点（`:114-120`）；`<a id>` 标记上提到下一个标题（`:199-246`）；`_repo_target`（`:162-180`）把文档交叉引用改写为站内路由（`/sop`、`/course#doc-*`、`/catalog/`、`/GTM/`）。EN 外壳双语，正文「served as authored」并给提示（`:402-409`）。

1. [ ] **无每篇文档的目录/子导航** → 从标题 token 生成右侧/顶部 TOC（长文档如 `architecture.md` 尤其需要）。
2. [ ] **「Repo docs」链接恒为 `{base}/docs/readme` 且硬编码 `class="active"`（`:369`）**，看别的 slug 时也高亮 readme → 按当前 slug 计算 active。
3. [ ] `_resolve_href` 对任何以 `/` 开头的 href **原样透传不校验**（`:187-188`）→ 收敛到站内已知路由白名单，未知则降级纯文本（与 course 的外链策略一致）。
4. [ ] 从 `course.py` 导入私有 helper（`:44-52`，已承认耦合）→ 提到 `layout.py` 或新 `mdrender.py` 共享模块。
5. [x] P0-2 mypy（`:141-142`）、P0-8 sprite（`:353`）。✅ `class _DocsRenderer(_DemotingRenderer)`（`docs_reader.py:113`）+ `renderer_cls=`（`:135`）；sprite 改裸占位符。**连带**：本页复用 `course.py` 的私有 `_DemotingRenderer`，即下面第 4 条要拆的耦合——P2 抽 `mdrender.py` 时一并收口
6. [ ] 图片白名单随 `docs/images/` 实际内容自动推导，避免新增图即 404。

## §8 `/catalog/`（`scripts/build_catalog_site.py` 917 行生成，`make build-site`）

现状：单文件 SPA；JSON 载荷放在 `<script type="application/json">` 且 `<`→`<`（`:884`）；hash 路由；实时搜索 `oninput="onSearch(this.value)"`（`:763`）；状态筛选 chip：全部/✅/📦（`:802-804`）。渲染器**先 `html.escape` 再做变换**（`:421-433`）→ XSS 安全（历史上有 2 个存储型 XSS，已修并有回归测试）。自带 i18n（`L10N :326-381`、完整 EN blurb 表 `:193-323`，**EN 构建缺 blurb 直接硬失败** `:578-581`）。

1. [ ] `onSearch` 查询**不存在的 `getElementById('hero')`**，且有一段死分支 `id!=='all-sec'`（`:834-840`）→ 清理。
2. [ ] 品牌区是 `<div onclick>`，**键盘不可达**（`:759`）→ 改为 `<button>`/`<a>`。
3. [ ] 搜索框无 `aria-label` → 补。
4. [ ] **无暗色主题**（只有 `color-scheme: light`）→ 与 §10 统一主题令牌对齐。
5. [ ] 缺 ⚰️（stub/已弃用）筛选 chip → 补，并让 chip 集合由数据推导而非手写。
6. [ ] GTM 链接写成 `../../../GTM/index.html`（`:332,:359`）**解析到根以上**，只因浏览器夹取才没坏 → 改为正确的相对路径。
7. [ ] 该文件是 P0-1 的 6 个格式失败文件之一。

## §9 `/GTM/`（16 个跟踪文件，手写营销单页 `index.html` 981 行 + 独立手写 `en/`）

现状：自有导航（PRICING/CONTACT/SOP DOCS/SKILLS/**GITHUB**）；无暗色主题（"dark" 命中 0）；不共享 shell。

1. [ ] P0-3 图片 401、P0-4 GitHub 链接。
2. [ ] **开发期脚本被提交进对外服务目录并公开挂载**：`GTM/i18n_split.py`、`GTM/sync_log.py`、`GTM/mac_window.py`、`GTM/index.bilingual.html` → 移出 `GTM/`（如 `scripts/gtm/`）或从挂载路径排除。
3. [ ] 中英双页手写、易漂移 → 至少加一个双语一致性守卫测试（小节数/价格/链接集合对比）。
4. [ ] Pro 档 ¥4,800 是占位（「以商务洽谈为准」）→ 文案明示为待议价，避免被当作报价。
5. [ ] 无暗色主题、无转化埋点 → 主题统一（§10）；埋点列为可选项，不引入第三方脚本（隐私）。

---

## §10 横切

### 10.1 i18n（`web/i18n.py` 1277 行，最大技术债之一）

现状：`I18N_PAIRS`（`:411-1266`）≈460 对**中文→英文精确子串替换**，按键长降序（`_PAIRS_SORTED :1268`），`to_en()`（`:1271-1277`）就是一个 `str.replace` 循环；**只作用于 app.py 的首页/控制台**。二级页面改用真正的配对字面量 `p(zh,en)`（`certification.py:321`）。`:1-18` docstring 自认「API-returned domain data … stays Chinese on both locales」。

**核心风险：改任何一个中文字符串，都会静默破坏它对应的 EN 替换对——目前没有任何键校验。**

三步走（顺序不可颠倒）：

1. [ ] **先加守卫测试**：断言 `I18N_PAIRS` 每个 zh 键**确实出现**在其目标渲染产物中；不出现即失败。这样漂移立刻可见。（不改行为，只加网）
2. [ ] **再抽键**：按 `certification.py` 的 `p(zh,en)` 范式，把 app.py 首页/控制台的成对字面量就地配对，逐步替换掉 `I18N_PAIRS` 条目；每替换一批就跑守卫。
3. [ ] **最后处理领域数据**：阶段名/门禁名/连接器名等 API 返回的领域标签，在领域层提供双语标签（而不是在渲染层做字符串替换）。

### 10.2 鉴权与多用户（`web/auth.py` 133 行）

现状：token **每请求**从 env 读，用 `hmac.compare_digest` 比较；`PUBLIC_PATHS` 精确路径白名单（`:101-106`）；401 返回**裸 JSON**（`:120-133`）——**没有 HTML 登录页，浏览器直接导航时无法完成鉴权**。

1. [ ] 补 HTML 登录页 + 会话 cookie（token 仍只从 `FDE_SCOPE_API_TOKEN` env 读，**绝不落文件/日志/响应**，不变式 7）。
2. [ ] 引入会话 cookie 后必须同时补 CSRF 防护（当前纯 Bearer 无此问题，加了 cookie 就有了）。
3. [ ] 操作者身份目前**自报**（advance 的 operator 字段）→ 登录后改为取自会话，消除伪造。
4. [ ] 新增任何 `fde_scope/web/` 路由时，必须确认没有被 `PUBLIC_PATHS` 误放（不变式 7）；补一条守卫测试断言「所有 mutating 路由都不在白名单里」。
5. [ ] 401 对 HTML 导航应重定向到登录页，对 API 才返回 JSON（按 `Accept`/路径前缀区分）。
6. [ ] `web/auth.py:117` mypy（P0-2）。
7. [ ] **不做**：RBAC/SSO/LDAP/多租户 → §15。

### 10.3 持久化与数据治理

现状：零数据库，`.fde_scope/`（engagements、skills、uploads）+ `reports/`，全部经 `fsutil.atomic_write_text`（不变式 4）；`storage-migrate --to sqlite` 已有（`cli.py:711`）。

1. [ ] **PII 明文存在 engagement JSON 里**（GDPR/EU AI Act 风险）→ 本轮**不新增任何 PII 落点**；字段级加密与保留期列 §15（独立立项）。
2. [ ] 补 backup / restore CLI 与 Web 入口（当前无备份路径）。
3. [ ] 补 schema 版本号，为将来迁移铺路（当前记录无版本字段）。
4. [ ] 损坏文件当前是**静默跳过**→ 在 UI/CLI 显式暴露「N 条记录无法解析」。
5. [ ] forge 上传落在 `paths.uploads_dir()` 且**从不清理**（`pawapp/backend/main.py:237` 同）→ 补保留期清理。
6. [ ] `cli.py:106` `connect` 把 `samples/preview.json` 写到**当前工作目录**，绕过 `paths.py` → 改为走统一 data_root。

### 10.4 可观测性

1. [ ] `/api/health`（`app.py:95`）已有真实探针语义（data_root 可写、reports_dir、`llm.configured` 经 `get_llm_client().available` **不发请求**、engagements_count），降级时仍返回 200 → **补一个 UI 面板**把它显示出来（现在只能 curl）。
2. [ ] 请求日志带 engagement id（当前无法把一次请求关联到一个项目）。
3. [ ] 慢操作计时（forge / deploy plan / ontology 校验）。
4. [ ] 前端错误码结构化（现在多为 `toast('保存失败：' + e)`）。

### 10.5 打包与分发（`pyproject.toml`、`appbuild/`、`android/`）

现状：`pyproject.toml:94-95` wheel 只装 `fde_scope`；`:98` sdist 只有 `fde_scope, README.md, pyproject.toml` → **`course-level-1/`、`pawapp/`、`GTM/`、`appbuild/`、`android/` 全在发行版之外**。
（P0-5 后已部分改写：`:100` wheel `force-include` 加 `course-level-1` → `fde_scope/_data/course-level-1`，`:103` sdist `include` 加 `course-level-1`；`pawapp/`、`GTM/`、`appbuild/`、`android/` 仍在发行版之外。）

1. [x] P0-5：`course-level-1/` 纳入包数据（`/course` 依赖它）。✅ 见 P0-5，干净 venv 实测通过
2. [ ] `pawapp/` 纳入发行版（否则 pip 装完无法 `qwenpaw export` 出可用宿主）。
3. [ ] `GTM/`、`appbuild/` 明确定位：GTM 是站内挂载资产（应随包），appbuild 是构建脚本（可不随包，但要在文档说明从仓库运行）。
4. [ ] **`appbuild/build_release.sh`（278 行）本身是生产级的，无需改造**：build_info.json 溯源、分架构 uv venv + PyInstaller、`merge_universal.py` 合 universal2、hardened runtime + entitlements 签名、公证（API key 或 keychain profile，ad-hoc 兜底）、DMG（含朴素兜底）、zip + SHA256SUMS + manifest。缺的只是 **CI 冒烟**（P3）。
5. [ ] `appbuild/launcher.py`（202 行）：`FDE_SCOPE_HOME` 导出、单实例守卫、滚动日志、健康等待后开浏览器到 `/console` —— 保持。
6. [~] **Android 应明确降级为 demo**：`android/build.sh`（49 行）要求**手工从腾讯镜像下载工具链**（`:12-17`），并用自动生成的 **debug keystore（`storepass android`）签名**（`:41-47`），**没有 release 签名路径** → 文档明示「demo 壳，不可上架」；P0-9 清掉误提交的 `.apk.idsig`。
   **进度**：`.apk.idsig` 已清（P0-9 ✅：`git rm --cached` + `android/.gitignore` 加 `*.apk.idsig`）；**文档定性未做**（留 P3 文档漂移批次）

---

## §11 CLI（`fde_scope/cli.py`，1400 行 / 56 KB，覆盖率 71% 最差）

命令与行号：`connect`(65)、`corpus`(115)、`deploy`(201，`--serve` 硬编码 `127.0.0.1:8000` @ 319)、`eval`(325)、`flywheel`(384)、`engage init/status/advance/rollback/list/journal`(443-597，rollback @ 521)、`gate list/check`(603/619)、`handoff`(644)、`kpi`(686)、`storage-migrate`(711，仅 sqlite)、`profiles`(732)、`web`(765，回环安全门 + `FDE_SCOPE_ALLOW_REMOTE` 显式开 @ 781)、`qwenpaw export/validate`(824/879)、`skill add/list/show/edit/publish/archive/review/export`(924-1153)、`ontology list/validate/check/export/diff`(1187-1325)、`license`/`license-issue`(1331/1353，HMAC)。

| # | 缺陷 | 证据 | 动作 |
| --- | --- | --- | --- |
| C1 | docstring 谎称「Every command supports `--dry-run`」 | `cli.py:4`；实际 eval/kpi/handoff/skill/ontology/gate/license 都没有 | 改 docstring 为真，或给缺的命令补 `--dry-run` |
| C2 | **全仓没有一个 `--json`** | `deploy` 把 manifest JSON 混在 rich markup 里输出（`:279`），带样式**无法被脚本解析** | 统一加 `--json`（输出纯 JSON、禁用 rich 样式） |
| C3 | 无 `--version` | 只在 `_banner` 里出现 | 加 Typer version 回调 |
| C4 | 无 shell 补全 | — | 补 completion 安装说明（Typer 自带能力） |
| C5 | 无 spinner / 进度 | 长操作（forge、deploy plan、ontology 校验）静默 | 用 `rich.progress` |
| C6 | `main()` 里的 `configure_logging()`（`:800-805`）**永远不会跑** | `pyproject.toml:89` 入口是 `fde_scope.cli:app`，只有 `python -m fde_scope.cli` 才经过 `main()` | 日志配置移到 app 回调 |
| C7 | 裸 traceback 泄给用户 | `_load_rows`(`:179-195`)、`_load_eval_cases`(`:369`)、flywheel `--events`(`:402`) | 转为友好错误 + 非零退出 |
| C8 | `connect` 把 `samples/preview.json` 写到 CWD | `:106`，绕过 `paths.py` | 走 data_root（同 §10.3.6） |
| C9 | `eval` 遮蔽内建名 | `:325` | 保留命令名，内部函数改名 |
| C10 | agent-spec 解析在 `deploy`(`:229-238`) 与 `qwenpaw export`(`:842-851`) **逐字重复** | — | 抽公共函数 |
| C11 | `gate list` 导入私有 `_default_gate_registry` | `:608`（`pawapp/backend/main.py:171` 同病） | 提供公开访问器 |
| C12 | **flywheel 打印硬编码假信息** `"weekly_retrain scheduled: next Mon 02:00"`；`--agent` 除横幅外从未使用 | `:412` | 删除假输出（或如实标注为未实现）；让 `--agent` 真正生效或移除该选项 |
| C13 | help 文案中英混杂 | 全文件 | 统一（与 §10.1 同策略） |
| C14 | 覆盖率 71%，全仓最低 | — | P3 补测 |

---

## §12 PawApp（`pawapp/backend/main.py` 522 行 · `pawapp/ui/index.js` 1215 行）

现状：**恰好 18 条路由**（`/health`、`/profiles`、`/phases`、`/engagements` GET+POST、`/engagements/{eid}` GET、`.../gates`、`/advance`、`/gate/{slug}`、`/forge`、`/kpi`、`/skills`、`/skills/drafts`、`/skills/{sid}/publish`、`/skills/{sid}/export`、`/handoff/{eid}/runbook`、`/handoff/{eid}`、`/deploy/plan`）+ **3 个 agent 工具**（`fde_sop_status`、`fde_sop_advance`、`fde_deploy_plan` @ `:443-511`）+ `skill_provider()` 优雅降级（`:434-440`）。UI 是无打包器 React，经 `window.QwenPaw.host`，单路由 `/apps/fde-scope`。

1. [ ] **HTTP 层整块重复**：`_slugify/_eng_path/_load_engagement/_save_engagement/_all_engagements/_skill_service`（`:50-96`）明写「mirror fde_scope.web.app」（`:48`）→ 抽到 `fde_scope` 内的共享模块，两边都导入（否则不变式 4 的原子写要在两处各维护一遍）。
2. [ ] `/health` 硬编码 `"version": "0.1.0"`（`:114`）→ 改用 `fde_scope.__version__`。
3. [ ] **文档说「2 个 agent 工具」，实际注册 3 个**（`README.md:246`、`docs/features-en.md:143` vs `:443/454/475`）→ 改文档为 3（P3 文档漂移项）。
4. [ ] forge 上传落 `paths.uploads_dir()` 且**从不清理**（`:237`）→ 同 §10.3.5。
5. [ ] skill export **把写文件当 POST 副作用**（`:334-339`）→ 改为返回内容或明确文档化。
6. [ ] 导入私有 `_default_gate_registry`（`:171`）→ 同 C11。
7. [ ] CI 对 1215 行 UI 只跑 `node --check`（语法检查，**不验证任何行为**）→ P3 补前端测试。

---

## §13 质量门与测试

| # | 项 | 现状 | 动作 |
| --- | --- | --- | --- |
| Q1 | 覆盖率门禁 | **`pyproject.toml` 里根本没有 `[tool.coverage]` 段** | 加 `fail_under`（从当前 92% 起步，留 1-2 点余量防抖） |
| Q2 | 4 个 env 门控集成测试**永远跳过** | MQTT(`FDE_SCOPE_MQTT_URL`)、MySQL(`FDE_SCOPE_MYSQL_DSN`)、OPC UA(`FDE_SCOPE_OPCUA_URL`)、ROS2(`FDE_SCOPE_ROS2_BAG`)；CI 未提供服务 | CI 加 service container（MQTT/MySQL 可行）；OPC UA/ROS2 至少提供 fixture 资产或明示为本地手工 |
| Q3 | 未测路由/分支 | `/api/ontology/store/{id}` 成功路径、catalog/GTM 回退路由（`app.py:963-971`、`:1050-1055`；整块回退 `:978-1054` ≈77 行是**最大未测块**）、skills/handoff/context 的错误分支 | 补测 |
| Q4 | 前端零测试 | 所有 JS 都内联在 Python 字符串里（`app.py:1566-2816`），无构建步骤，唯一客户端状态是 `localStorage['fde-theme']` | 抽出 JS 到静态文件 + 加最小 DOM 测试，或用 Playwright 打关键路径 |
| Q5 | `app.py` 2901 行单文件巨石 | 54 路由 + 两大 HTML 常量 | 按 remediation C1 拆 router（console / catalog / gtm / docs） |
| Q6 | 无 macOS 打包 CI 冒烟 | `release.yml` 做 universal2 + DMG + 公证 + Release，但**没有 PR 级冒烟** | 加 remediation C2 的冒烟 job（不签名，只验证能构建） |
| Q7 | 守卫测试本身有 bug | `test_architecture_guard.py:109` 漏 `patch`（P0-6） | 修 + 加「守卫自身正确性」的元测试 |

---

## P2 落地记录（已完成 ✅）

全绿基线：**920 passed / 4 skipped**，ruff format --check / ruff check / mypy / 路由守卫全过；
交互项（搜索、进度、勾选、TOC）经 headless Chrome 实测。

- **§10.1 i18n 守卫（第一步，先行落地）**：新 `tests/test_i18n_guard.py` 四条守卫——
  每个 zh 键必须存在于其渲染目标（**当场揪出 1 个死键并连带删除 5 个旧磁贴死对**）、
  键唯一、EN 控制台/首页零 CJK（语言切换器除外）。593 对全部过检。
- **§7 docs_reader**：抽共享模块 `web/mdrender.py`（DemotingRenderer / fence walker /
  链接正则 / 路径归一，course.py 与 docs_reader.py 共用，私有互 import 收口）；每篇文档
  TOC（heading token 生成，锚点逐个验证存在）；`class="active"` 只在 readme 亮；
  `_resolve_href` 绝对路径收敛到站内路由白名单（未知 → 降级纯文本）；图片白名单改为
  **目录推导**（加图即服务，无死元组）。course 对外暴露 `COURSE_FILES` 公共映射。
- **§4 glossary**：即时搜索（输入框 + aria-label + 计数 + 空态 + 分组隐藏，卡片 haystack
  同时覆盖术语/别名/释义）；`tips[term]` 与别名全部 `html.escape`（拆掉将来动态数据的
  XSS 地雷）；回到顶部锚点。
- **§5 course**：统计改 **token 流**（fence 里的字面量不再污染数字——测试同步改为
  排除 fence 行后对账，234 个练习项与渲染出的复选框数**逐个相等**）；`- [ ]` 变真复选框
  （localStorage 持久化，按 章+序号 键）；每章「标记已读」+ 顶部进度条（实测刷新后保持）；
  25 篇内即时过滤。旧测试「源文件 `- [ ]` 总数 = 渲染 ☐ 数」的断言本身就是被 fence 污染的
  例子（244 vs 234），已随结构化修正。
- **§6 sop**：rail 从 **token 流**取节标题（不再从渲染产物正则刮回）；EN rail 用配对字面量
  （7 节全译，未知标题回退 zh 不硬译）；`/sop` ↔ `/console` 双向深链（zh/en 双语）。
- **§8 catalog**：品牌区 `<div onclick>` → `<a href="#/">`（键盘可达 + focus-visible）；
  搜索框补 aria-label（L10N 两键）；`onSearch` 死分支与不存在的 `getElementById('hero')`
  清除；GTM 链接相对深度改为按服务挂载点（`/catalog/`→`../GTM/`、`/catalog/en/`→`../../GTM/`，
  不再靠浏览器夹取）；`make build-site` 重建 + `make check-catalog` 全过。
  **遗留**：暗色主题（§8.4）、⚰️ chip（§8.5）→ P3。
- **§2 首页**：连接器磁贴状态**由注册表导入期生成**（"ROS2 Bag → stub" 一类手写状态
  不再可能漂移；场景磁贴「工业IO部分 stub」陈旧宣称一并修正为「工业 IO 已接入」）；
  #kpi 增加一行「如何换成真实数据」指引。
- **§8.4/§8.5 补齐**：catalog 站点暗色主题（`prefers-color-scheme` 变量覆盖，生成式静态站
  不引 JS 状态）；⚰️ 筛选 chip 改为**由数据推导**（无 ⚰️ 项则不渲染）。
  `make build-site` 重建 + `make check-catalog` 过。

#### CLI C1–C13 落地（C12 已随 P1 完成）

- **C1** 模块 docstring 改为真话（不再宣称全命令 `--dry-run`），改为宣传 `--json`/`--version`。
- **C2 `--json`**：`deploy`（manifest 纯 JSON）、`eval`（报告）、`kpi`、`engage status`/`list`、
  `skill list`、`ontology list`/`validate`/`check`/`diff` 共 9 个命令；banner 与 LLM 降级提示在
  `--json` 下静默（stdout 保证可解析）。
- **C3 `--version`**：根回调 `--version/-V`（eager）；`--install-completion` 是 Typer 内建
  （C4 已记录进 README quickstart）。
- **C6** 日志配置从 `main()` 移到根回调——`python -m fde_scope.cli` 与 `fde-scope` 两个入口行为一致。
- **C7** `_read_input_text` 统一把 OSError/UnicodeDecodeError/JSONDecodeError 转为一行红字 +
  exit 2；CSVConnector 的 FileNotFoundError 同样收口（corpus 坏路径不再裸 traceback）。
- **C8** `connect` 的 `samples/preview.json` 落 `paths.data_root()/samples` 且走
  `atomic_write_text`（不再写 CWD、不再裸 write_text）。
- **C9** `eval` 命令函数改名 `eval_command`（`@app.command("eval")`），不再遮蔽内建名。
- **C10** `_parse_agent_specs` 抽出，`deploy` 与 `qwenpaw export` 共用。
- **C11** 公共访问器 `engagement.default_gate_registry()`；CLI `gate list` 与 **PawApp**
  （§12.6）都改走公共名。
- **C5 spinner**：`console.status()` 包住 deploy 装配、eval 基准跑、ontology validate/check。
- **C13（help 中英混杂）未做**：全文件 sweep 留待独立批次（本轮触达的 help 均已双语）。
- 测试：8 条新 CLI 测试（version / deploy+eval+kpi+status+list+ontology validate 的 `--json`
  可解析性 / 坏路径友好报错 / preview 落 data root 不落 CWD）。
- **顺带修一个测试污染**：`test_catalog_links_survive_an_install_without_docs` reload app 模块
  后从不还原，把「无 docs」变体泄漏给其后所有检查挂载的测试（顺序依赖失败）——finally 中补 reload。

## P3 落地记录（Q1/Q3/Q6/Q7 + 文档零漂移完成；Q2/Q4/Q5/§12 部分待立项）

全绿基线：**931 passed / 4 skipped**，覆盖率门禁生效（92.08% ≥ 90），ruff/mypy/守卫全过。

- **Q1 覆盖率门禁**：`pyproject.toml` 新增 `[tool.coverage]`（source=fde_scope，
  `fail_under = 90`，当前 92.08%，留 2 点余量防抖）。
- **Q3 未测路由/分支**：`/api/ontology/store/{id}` 成功+404、skills ghost 404（publish/export/
  archive）、journal 未知 engagement 404、context 校验分支——**连带发现并修复一个真缺陷**：
  `update_context` 的 `success_criteria` 等**裸 `validate_python` 错误 `loc` 为空**，控制台
  Context 编辑器承诺的「错误带字段路径」对这些键不成立 → 加 `_checked()` 包装，把字段名
  前置进每条错误（测试断言 `loc` 含字段名）。fallback notice 模板（wheel 安装态的
  catalog/GTM else 分支）按挂载态断言其良构性。
- **Q6 macOS CI 冒烟**：`ci.yml` 新 `macos-smoke` job——`build_release.sh --arch arm64
  --no-dmg` + bundle 内 CLI `--help`（不签名、不发布）。
- **Q7 守卫元测试**：**前提已过时**——P0-6 已把装饰器扫描锚定到 `app.openapi()` 逐条对账
  （漏 verb 即红），本轮补了 fallback-notice 侧的对应校验。
- **文档零漂移（本批 5 处）**：`manufacturing_scenario.md:28`「连接器 stub 已就位」→ 真实
  实现表述；`features.md`「术语释义独立成页」→「同页卡片+即时搜索」（`features-en.md` 同步）；
  PawApp「2 agent tools」→「3」（README + features.md + features-en.md 三处）；
  `android/README.md` 新增「demo 壳，不可上架」定性（debug keystore / 手工工具链 / 无
  release 签名路径三条理由）；首页场景磁贴「工业IO部分 stub」已随 P2 注册表化修正。
- **顺带**：PawApp `/health` 版本改 `fde_scope.__version__`（§12.2）。

### 仍未做（P3 尾款，需独立批次/立项）

- **Q2**：CI service containers（MQTT/MySQL 可行；OPC UA/ROS2 明示本地手工）。
- **Q4**：前端 JS 抽出静态文件 + DOM 测试（当前以 headless Chrome 冒烟覆盖金路径）。
- **Q5**：`app.py`（~3200 行）按 router 拆分。
- **§12.1/12.4/12.5**：PawApp 与 Web 的共享 HTTP 层抽取、uploads 清理、skill export 的
  POST 副作用语义。
- **C13**：CLI help 全文双语统一。

## §14 分期路线图

| 期 | 工作量 | 内容 | 出口标准 |
| --- | --- | --- | --- |
| **P0 止血** | 0.5–1 天 | 上表 9 项 | `ruff format --check .`、`mypy fde_scope`、`pytest -q`、`pytest tests/test_architecture_guard.py` 全绿 |
| **P1 补齐已实现能力** | 3–5 天 | §1.1 六项 + §1.2 ontology 三视图 + skills 搜索 + §1.3 连接器面板 | 每项都有 UI **和**测试；`features.md` 的「回滚」宣称变成真的 |
| **P2 页面质量** | 5–8 天 | §2–§9 各页加强 + §10.1 i18n 守卫与抽键 + §11 CLI C1–C13 | 每页有搜索/TOC/进度中至少一项；主题统一；CLI 可脚本化 |
| **P3 工程化** | 8–12 天 | §13 Q1–Q7 + §10.2–§10.5 + §12 | 覆盖率门禁生效；巨石拆分；文档零漂移 |
| **P4 独立立项** | — | 见 §15 | 不在本轮 |

---

## §15 明确不做（本轮范围外，且部分永久不做）

### 受 AGENTS.md 七条不变式约束——任何加强都不得违反

| 不变式 | 它约束了本计划里的哪条加强 |
| --- | --- |
| 1 · Gate 重评估是实时的（`Engagement.advance()` 每次推进都重评当前阶段门禁；陈旧 `passed` 永不放行；强制推进也要评估并留痕。**不得**在 `evaluate_phase_gates` 周围加缓存或短路） | §1.1 rollback 端点、§1.2 advance 弹窗、P1 一切门禁相关 UI：**只能走 `advance`/`rollback`，绝不能直接赋值 `phase`/`zone`/journal/gate 结果** |
| 2 · ID 由服务端生成（`SkillRecord.id`、`EngagementContext.id` 由拥有它的 service/store 分配，外部输入永不能设置） | §1.2 skills 编辑、Context tab 可编辑化：**不得引入带 id 的批量赋值** |
| 3 · 凭据只活在 env（API key 经 `llm.py` `_ENV_KEY`/`_env()`；**绝不**落 manifest/report/engagement JSON/日志） | §1.3 连接器面板：**只报「是否已配置」布尔，绝不回显值**；§10.4 日志：不得打印 token |
| 4 · 落盘记录必须原子写（一律经 `fsutil.atomic_write_text`，临时文件 + `os.replace`；**绝不**用裸 `Path.write_text` 写用户状态） | §1.1 evidence/handoff/archive/delete、§10.3 备份、§12 PawApp 共享层抽取 |
| 5 · 规则授权是唯一权限通道（`build_toolkit` 永不给已部署工具打 `is_read_only`；未匹配工具的回退由模式决定：DEFAULT→ASK(HITL)、DONT_ASK→DENY） | §1.2 deploy 面板、§1.3 面板：**不得新增旁路授权** |
| 6 · AgentScope 窗口是实测出来的（`pyproject.toml` 的 `agentscope` extra 与 `docs/agentscope_api_mapping.md` 必须逐字引用同一 specifier `>=2.0.4.post1,<3`，由 `tests/test_architecture_guard.py` 强制；放宽前必须重测） | §1.3 连接器面板状态、P3 CI：**不得顺手放宽窗口** |
| 7 · Web 变更路由必须过鉴权依赖（新增 `fde_scope/web/` 路由时确认未被 `PUBLIC_PATHS` 误放；token 只从 `FDE_SCOPE_API_TOKEN` env 读，绝不进文件/日志/响应） | §1.1 新增的 rollback/evidence/handoff/archive/delete 端点、§10.2 登录页 |

### 危险操作（先问 / 必须带测试）

- 直接赋值 engagement 状态机字段（`phase`、`zone`、journal 条目、gate 结果）而不走 `Engagement.advance` / `rollback` —— 绕过门禁强制。
- 编辑 `fde_scope/engagement/phases.py`（18 阶段）或默认门禁注册表（10 门禁）—— 契约测试会**故意**失败；要改就得连 `docs/` 一起改。
- 改权限管道（`deploy/permission_builder.py`、`deploy/toolkit.py`）而不跑真实库测试（`pytest -m agentscope`）。
- 没有在隔离环境逐版本跑过就放宽 `agentscope` 窗口。

### 本轮不做（需独立立项）

1. [ ] 多租户 / RBAC / SSO / LDAP —— 架构级改动，与「零数据库单用户工作台」定位冲突，需先定产品形态。
2. [ ] PII 字段级加密 + 保留期策略 —— 涉及密钥管理与合规审计，独立立项。**本轮只保证不新增 PII 落点。**
3. [ ] 数字签名 —— 当前审计证据是 **sha256 文件哈希，不是数字签名**；不得在文档里把它说成签名。真要签名需引入密钥基础设施。
4. [ ] 真实训练管道 —— `TrainingBackend` 是 Protocol + HTTP webhook + 显式 noop 兜底；接真实训练系统是另一个产品。
5. [ ] 用真实连接器 POC 替换 mock 用例 —— 需要真实客户环境与凭据，非代码任务。
6. [ ] `storage-migrate` 支持 sqlite 以外的后端 —— 现仅 sqlite（`cli.py:711`），无需求驱动。

---

## 回归锚（每批改动后必跑）

```bash
make test                                              # 或 .venv/bin/python -m pytest -q
.venv/bin/python -m pytest -m agentscope               # 真实库运行时测试（需 agentscope extra，否则跳过）
.venv/bin/python -m pytest tests/test_architecture_guard.py   # 契约守卫
.venv/bin/ruff check fde_scope tests && .venv/bin/ruff format --check fde_scope tests
.venv/bin/mypy fde_scope
```

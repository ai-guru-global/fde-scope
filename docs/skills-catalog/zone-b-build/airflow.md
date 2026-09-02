# airflow

> 状态：📦 可安装（registry 真名 `astronomer/agents@airflow`）· 类型：工具/数据 · FDE 位点：Zone B · 数据管线编排与部署
> 安装：`npx skills add astronomer/agents@airflow --directory ~/.qoder/skills -y` · 装机量：1.3K（skills.sh，2026-08-31）· 详情：https://skills.sh/astronomer/agents/airflow

## 能做什么
Astronomer 官方 Airflow 运维 skill：用 `af` CLI 查询、管理、排障 Airflow——列/触发 DAG（`af dags list`、`af runs trigger <dag_id>`）、读任务日志（`af tasks logs <dag_id> <run_id> <task_id>`）、健康检查（`af health`）、多实例配置（`af instance add/use/discover`）。套件内真实兄弟条目：`authoring-dags`、`testing-dags`、`debugging-dags`、`deploying-airflow`、`migrating-airflow-2-to-3`、`checking-freshness`、`tracing-upstream-lineage`、`tracing-downstream-lineage`、`managing-astro-local-env`、`setting-up-astro-project`、`airflow-state-store`、`airflow-hitl`；repo 另有 `cosmos-dbt-core` 把 dbt 模型编排进 DAG。

## 何时使用
- 客户数据管线跑在 Airflow 上：日常运维（触发/重跑/查日志）或排障（import error、broken DAG）
- 客户要从 Airflow 2 升到 Airflow 3（→ 套件内 `migrating-airflow-2-to-3`）
- 本地起 Airflow 环境、部署到 Astro/生产（`astro dev start` / `astro deploy`）

**不用于**：在 Airflow 元数据表上做 warehouse/SQL 分析（→ 套件内 `analyzing-data`）；深度根因报告（→ `debugging-dags`）。

## 新人上手
- **触发**：对 agent 说「看下客户 Airflow 里哪些 DAG 挂了」「触发一次这条管线」「把日志拉出来看看」
- **第一步**：`npx skills add astronomer/agents@airflow --directory ~/.qoder/skills -y` 装完后确认 `af` 在 PATH（没有就 `uv tool install astro-airflow-mcp` 或经 `astro otto` 获得），再 `af instance add prod --url https://airflow.example.com --token "$AIRFLOW_API_TOKEN"` 绑定客户实例，`af instance list` 核对
- **常见坑**：`af instance discover` 不带 `--dry-run` 会在 Astro Cloud **创建 API token**——SKILL.md 原话标注这是敏感操作需显式批准；永远先 `af instance discover --dry-run` 预览
- **常见坑**：凭据别写进共享配置——token 支持 `${VAR}` 引用环境变量，项目内 `.astro/config.local.yaml` 才不入库；老配置 `~/.af/config.yaml` 用 `af migrate` 迁移（幂等，旧文件改名 `.bak`）

## 最佳实践
- Do：排障走固定动线 `af health` → `af dags explore <dag_id>` → `af tasks logs`，别一上来就翻 web UI
- Do：本地迭代用 `astro dev parse`（不启动 Airflow 就能抓 DAG 解析错误）+ `astro dev pytest`
- Don't：生产部署别整包 `astro deploy`，只改了 DAG 时用 `astro deploy --dags`（跳过镜像构建，快得多）
- Don't：token 硬编码进配置文件或 engagement 交付物——走环境变量，遵守本仓凭据规约

## 项目应用位点
- Zone B `deploy`：客户数据管线（抽取→变换→回写）的编排交付与升级
- Zone B 管线 2→3 迁移评估：`migrating-airflow-2-to-3` 的差异清单可直接当交付 checklist
- 客户内网/私有化场景：Astronomer 栈容器化，与 [docker-build-deploy](docker-build-deploy.md)、[kubernetes-specialist](kubernetes-specialist.md) 的部署路径衔接

## 相关
[docker-build-deploy](docker-build-deploy.md) · [using-dbt-for-analytics-engineering](using-dbt-for-analytics-engineering.md) · [kubernetes-specialist](kubernetes-specialist.md)

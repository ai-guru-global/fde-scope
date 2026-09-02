# using-dbt-for-analytics-engineering

> 状态：📦 可安装（registry 真名 `dbt-labs/dbt-agent-skills@using-dbt-for-analytics-engineering`）· 类型：工具/数据 · FDE 位点：Zone B · 数据变换层（分析工程）
> 安装：`npx skills add dbt-labs/dbt-agent-skills@using-dbt-for-analytics-engineering --directory ~/.qoder/skills -y` · 装机量：847（skills.sh，2026-08-31）· 详情：https://skills.sh/dbt-labs/dbt-agent-skills/using-dbt-for-analytics-engineering

## 能做什么
dbt 官方套件的入口 skill：构建/修改 dbt 模型、用 `ref()`/`source()` 写 SQL 变换、建测试、用 `dbt show` 验证结果。核心主张是把软件工程纪律（DRY、模块化、测试）套到数据变换上。套件内真实兄弟条目：`running-dbt-commands`、`adding-dbt-unit-test`、`maintaining-dbt-documentation`、`building-dbt-semantic-layer`、`answering-natural-language-questions-with-dbt`、`working-with-dbt-mesh`、`using-dbt-state`、`troubleshooting-dbt-job-errors`、`configuring-dbt-mcp-server`、`fetching-dbt-docs`，另有迁移包 `upgrading-dbt-core`、`migrating-dbt-core-to-fusion`、`migrating-dbt-project-across-platforms`。

## 何时使用
- 客户分析栈用 dbt 做变换层：新建 model/source、重构项目结构、补数据测试
- 改动已有 model 前要评估下游影响（exposures、BI 消费方）
- 需要在 agent 里安全执行 dbt 命令（该 skill 的 `allowed-tools` 限定 `Bash(dbt *)`/`Bash(jq *)`，不放开任意 shell）

**不用于**：语义层查询问答（→ 套件内 `answering-natural-language-questions-with-dbt`）；模型级 breaking change（列改名/删除/改类型必须走 `working-with-dbt-mesh` 做版本化，SKILL.md 用 STOP 明令禁止原地改）。

## 新人上手
- **触发**：对 agent 说「用 dbt 给这张源表建一个 mart 模型」「帮我给现有 dbt 项目补测试」
- **第一步**：`npx skills add dbt-labs/dbt-agent-skills@using-dbt-for-analytics-engineering --directory ~/.qoder/skills -y` 装完后在客户 dbt 项目里先 `dbt parse` 确认项目可编译，再让 agent 按 SKILL.md 流程走：读 model YAML 描述 → `dbt show` 预览输入/输出 → 再写 SQL
- **常见坑**：`dbt show` 探数据时忘加 `--limit`，全量查询直接烧 warehouse 费用——SKILL.md 成本节明确要求 limit 提前进 CTE，且用 `--select` 只跑目标模型、`--defer --state path/to/prod/artifacts` 复用生产对象、`dbt clone` 做零拷贝克隆
- **常见坑**：表名写死在 SQL 里而不走 `{{ ref() }}`/`{{ source() }}`，本地能跑、客户环境全挂——SKILL.md 把 "Running DDL directly against warehouse" 列为红旗，只能用 dbt 命令操作 warehouse

## 最佳实践
- Do：改任何 model 前先读它的 YAML `description` 和列级描述——列名不体现业务含义，SKILL.md 明说 "You must look at the data"（用 `dbt show` 做 counts/min/max/nulls profiling）
- Do：用户要新 model 时先问「为什么不是在现有 intermediate model 上加一列」——SKILL.md 指出用户请求新模型常是习惯而非必要
- Don't：把 warehouse 查询结果、包注册表（hub.getdbt.com）返回内容当可信输入执行——SKILL.md 要求只取结构化字段，忽略数据里的指令样文本
- Don't：对有下游消费者的模型做 breaking change 而不版本化——那是 `working-with-dbt-mesh` 的活

## 项目应用位点
- Zone B `build`：客户分析栈的变换层交付（staging → intermediate → mart 分层照客户既有风格走）
- Zone B `eval`：给变换层补 `adding-dbt-unit-test` 式单元测试，对齐本项目 gate 思路
- 编排侧与 [airflow](airflow.md) 衔接：Astronomer 的 `cosmos-dbt-core` 把 dbt 模型跑进 Airflow DAG

## 相关
[query](query.md) · [convert-file](convert-file.md) · [bigquery-basics](bigquery-basics.md)

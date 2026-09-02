# grafana-dashboarding

> 状态：📦 可安装（registry 真名 `grafana/skills@dashboarding`，本目录建档名统一加 `grafana-` 前缀）· 类型：工具 · FDE 位点：Zone C · 监控交付（看板/告警交付物）
> 安装：`npx skills add grafana/skills@dashboarding --directory ~/.qoder/skills -y` · 装机量：4.1K（skills.sh，2026-08-31）· 详情：https://skills.sh/grafana/skills/dashboarding

## 能做什么
Grafana 官方出品的**看板即代码**套件：把 Grafana dashboard 当 JSON 写、经 HTTP API 推送、按 `uid` 分发。覆盖面板类型（timeseries / stat / gauge / table / heatmap / logs / traces / node-graph）、`gridPos` 24 列布局、单位与阈值、template + datasource + 链式变量、transformations（`organize` / `calculateField` / `filterByValue`）、面板与看板链接（`${__field.labels.x}` / `${__from}`）、Loki/Prometheus 注释（部署事件叠加）。同 repo 兄弟 skills：`promql`、`loki`、`tempo`、`alerting-irm`、`alloy`，可组合覆盖"看板 + 查询 + 告警 + 采集"整条自建监控链。

## 何时使用
- 客户现场是**自建 Prometheus/Grafana**（制造业/工业 air-gap 内网最常见），要交付新服务的看板
- 客户要求看板进 git 版本管理、或要在内网离线重放（JSON 文件可直接搬）
- 给已有看板加 `$job` 下拉变量、加 "Error %" 派生列、把部署事件叠成注释
- SLO gate 材料需要可复查的看板证据面（查询语句 + 时间窗都在 JSON 里）

**不用于**：客户监控栈是 Datadog 的 SaaS 场景（→ [datadog](datadog.md)，那边走 MCP 工具面，这边管自建开源栈）；告警通知流程/值班编排本身（→ [sre-runbooks](sre-runbooks.md)）。

## 新人上手
- **触发**：对 agent 说"给这个服务写一个 Grafana 看板 JSON"、"加一个服务下拉框"、"把每次发版叠加成注释"——不说 API 细节也会命中
- **第一步**：装好后让 agent 按套件工作流走一遍推送闭环：先 `jq empty /tmp/dash.json` 校验，再 `POST /api/dashboards/db`（payload 要包一层 `{dashboard, folderUid, overwrite, message}`），最后用返回的 `version` 加 `GET /api/dashboards/uid/<uid>` 回读验证
- **常见坑**：API token 必须带 `dashboards:write` 权限（`Authorization: Bearer <token>`），只读 token 会在推送时 403；把 dashboard JSON 裸 POST 会失败——外层必须有 `dashboard` 包装字段
- **常见坑**：`overwrite: true` 会静默覆盖远端同 `uid` 的现有版本；改别人维护的看板前先 GET 确认当前 `version`，别一把覆盖掉客户的手工改动

## 最佳实践
- 看板 JSON 进客户 git 仓库（导出即交付物），现场内网可离线重放——这是 air-gap 交付最稳的形态
- 推送后**必回读验证**（套件自身的主张）：`GET /api/dashboards/uid/<uid>` 核对 title / panels 数 / version 递增，别只看 POST 返回 success
- 变量用 `templating.list` 的 query 型（如 `label_values(up, job)` 配 `refresh: 2` + `includeAll`），别把环境名写死进 PromQL
- 派生指标优先用 transformation（如 `calculateField` 的 `reduceRow` 模式算 Error %），改面板 Inspector 确认字段出现再交付
- 凭证走环境变量，token 不写进看板 JSON 或交付文档（对齐仓库 AGENTS.md 的凭证不变量）

## 项目应用位点
- Zone C 监控交付 phase：客户自建 Grafana 栈的看板/告警交付物（与自建 Prometheus 配套）
- SLO gate（10 gate 之一）：SLO 看板作为证据面之一，查询语句可进 gate 材料
- 飞轮重训（flywheel）效果对照：上线前后指标在同一看板做 A/B 证据
- 变更管理：部署事件用 annotations 叠加，复盘时直接在时间轴上对齐

## 相关
[datadog](datadog.md) · [sre-runbooks](sre-runbooks.md) · [gke-observability](gke-observability.md)

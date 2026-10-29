# 评估报告（示例）· 西岸家电 · 工单分诊

> **lab 自带示例数据**，用于 `handoff … --eval-report` 的那个路径参数。
> 它不是你的产出：D7 要交的是你自己那一份（D5 跑出来的 `--json` 抄进你的文档）。
>
> 来源与可信度：
> - **来源**：`fde-scope eval --agent mock --test-set labs/D5/fixtures/test_set.jsonl --json`
>   （5 条样例，mock agent，固定随机种子）。
> - **可信度：工具实测 / 仅作格式示例**——`mock` 回复是"把输入原样回显 + 已为您处理"
>   的桩实现，指标**只证明链路通，不证明效果好**；把这份报告当作客户交付物就是造假。
> - **口径提醒**：`intent_accuracy=1.0` 是 mock 桩命中子串的产物，不是模型能力
>   （见 `12` §2.4 关于 `expected_category` 子串判分的说明）。

## 1. 主指标

| 指标 | 值 | 字段 |
|---|---|---|
| 意图识别准确率 | 1.000 | `metrics.intent_accuracy` |
| 回复采纳率 | 1.000 | `metrics.reply_adoption_rate` |
| 人工升级率 | 0.200 | `metrics.escalation_rate` |
| 首次接触解决率 | 1.000 | `metrics.first_contact_resolve` |
| 单工单成本 | 1.000 | `metrics.cost_per_ticket` |
| 样本数 | 5 | `case_count` |

> 语料三指标（覆盖率 / 平均质量分 / 语义多样性）本次为 `0.0`：`eval` 读的是
> 测试集，不读 `corpus_report.json`——离线评估与语料体检是两套口径，别混着讲。

## 2. 失败样本（`bad_cases`）

| # | case_id | 类别 | 原因 | 输入 |
|---|---|---|---|---|
| 1 | `c-003` | 门店投诉 | escalated | 这家店的服务太差了！我要投诉 |

- 失败总数 `total_failures` = 1；最差类别 `top_category` = 门店投诉。
- 工具建议（`bad_cases.recommendation`，原文照抄）：
  「建议补充「门店投诉」类语料 ~50 条，重点覆盖失败模式。」

## 3. 一句话结论

链路通、口径能复现（同命令两遍结果一字不差），但 mock 的 1.000 不代表可用；
上线前要用真实模型 + ≥200 条人工标注测试集重跑（见 `07` D5 剧本）。

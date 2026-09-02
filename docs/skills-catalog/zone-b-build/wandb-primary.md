# wandb-primary

> 状态：📦 可安装（registry 真名 `wandb/skills@wandb-primary`，建档名与真名一致）· 类型：工具/数据 · FDE 位点：Zone B validate + Zone C · 客户训练实验跟踪（W&B）
> 安装：`npx skills add wandb/skills@wandb-primary --directory ~/.qoder/skills -y` · 装机量：1.4K（skills.sh，2026-08-31）· 详情：https://skills.sh/wandb/skills/wandb-primary

## 能做什么
Weights & Biases 官方（wandb org）的"主技能"：面向宽口径 W&B 工作的速查手册——run 盘点（`wandb.Api()`、`api.runs(path, per_page=1, include_sweeps=False, lazy=True)` 精确计数）、artifact 类型→集合→版本清点、Weave trace/eval 分析（`weave.init()`、`client.get_calls()`、`CallsQueryStatsReq` 服务端统计）、sweep 清单、训练历史诊断（曲线毛刺 / NaN / 稳定性）、run 与变体队列对比、系统指标（GPU/CPU/内存）、`wandb_workspaces.reports.v2`（`wr.Report` / `wr.LinePlot`）产出客户报告、Launch 队列工作流；附 12 个 references（WANDB_SDK、WEAVE_SDK、RUN_OPS、RUNS_TABLE、ARTIFACTS_AND_REGISTRY、REPORTS、WORKSPACES 等）。

## 何时使用
- 客户训练/微调流程已在 W&B 上（entity/project 现成），要做 run 盘点、指标对比、artifact 清点或交付期数据汇总
- 分析训练历史：loss 曲线毛刺、NaN、稳定性，或按 config 维度对比两个 run / 两个变体
- 要把实验结论写成 W&B Report 交给客户，或用 Weave trace 复盘 agent 评测结果

**不用于**：发起新训练任务（训练执行归 Zone C 的 [trl-training](../zone-c-operationalization/trl-training.md) / [huggingface-llm-trainer](../zone-c-operationalization/huggingface-llm-trainer.md) 页）；fde-scope 自身实验跟踪（本项目无 W&B 依赖，评估走 `fde_scope.eval`）。

## 新人上手
- **触发**：对 agent 说"盘点客户 W&B 项目最近的训练 run"或"对比两次微调的曲线"
- **第一步**：`npx skills add wandb/skills@wandb-primary --directory ~/.qoder/skills -y` 装完后，设好 `WANDB_API_KEY` / `WANDB_ENTITY` / `WANDB_PROJECT` 三个环境变量（凭据只走 env，与本项目 invariant 一致），再让 agent 用 `wandb.Api(timeout=120)` 拉 run 清单
- **常见坑**：不传 timeout 会踩 SDK 默认 19 秒超时直接失败——skill 要求一律 `wandb.Api(timeout=120)`；大 run 裸调 `history()` 会全量拉爆，必须 `keys=[...]` 限定列；系统指标（GPU/CPU/内存）必须 `run.history(stream="system")`，默认 stream 只返回训练指标

## 最佳实践
- 大项目性能规则（skill 的 CRITICAL 一节）：数 run 用 `per_page=1, include_sweeps=False, lazy=True`，trace 统计走服务端 `CallsQueryStatsReq`，不要把数据全量拉回本地
- Weave API 高频错（skill 原文点名）：父调用过滤用 `parent_ids`（复数列表）不是 `parent_id`；状态读 `summary["weave"]["status"]` 不是 `summary["status"]`
- 红线：绝不删除客户 W&B project（不可逆）；Report 用 skill 的 `save_report_verified` 流程保存；Workspace 视图保存即生效、没有草稿态
- 气隙客户：W&B 默认是 SaaS，air-gap 内网需客户自托管实例（Self-managed）或换内网方案，对接前先确认实例可达；官方 org、1.4K 装机，装前照例过 [skill-criticagent](../cross-cutting/skill-criticagent.md) 并回填本页

## 项目应用位点
- Zone C operationalization：客户 W&B 栈时的 run 管理与指标上报对接（训练执行见 trl-training / huggingface-llm-trainer 页）
- Zone B validate：训练侧实验对比（compare runs / cohorts）支撑选型结论
- 交付汇报：`wr.Report` 生成客户可读实验报告，落到客户 W&B 实例

## 相关
[huggingface-llm-trainer](../zone-c-operationalization/huggingface-llm-trainer.md) · [trl-training](../zone-c-operationalization/trl-training.md) · [huggingface-community-evals](huggingface-community-evals.md)

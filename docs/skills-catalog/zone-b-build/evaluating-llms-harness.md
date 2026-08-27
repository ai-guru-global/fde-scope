# evaluating-llms-harness 📦

> 状态：📦 可安装（未装）· 类型：评估基准知识 · FDE 位点：Zone B validate
> 来源：`firecrawl/ai-research-skills@evaluating-llms-harness` · 热度：22 installs · repo 17★ · https://skills.sh/firecrawl/ai-research-skills/evaluating-llms-harness
> 安全审计：Agent Trust Hub **Pass** · Socket **Pass** · Snyk **Warn**（2026-08-27 复核）
> 备选：`ovachiever/droid-tings@evaluating-llms-harness`（53 installs，第三方同名）
> 安装：`npx skills add firecrawl/ai-research-skills@evaluating-llms-harness --directory ~/.qoder/skills -y`

## 能做什么
EleutherAI **lm-evaluation-harness**（`lm-eval`）的用法手册：一条命令在 60+ 学术基准（MMLU / GSM8K / HellaSwag / …）上评估 HF 模型，涵盖 `--model hf|vllm`、task 组合、batch/device 配置、结果解读与自定义 task。

## 何时使用
- 需要**标准化、可引用**的公开分数（客户/评审会拿论文数字对比）
- 已装 `huggingface-community-evals` 但想在 inspect-ai/lighteval 之外再用 `lm-eval` 交叉核对
- 需要给自定义评估写新 task（本地化业务基准）时的参考范式

**不用于**：客户工单/产线数据评估（→ `fde_scope.eval` + [phoenix-evals](phoenix-evals.md)）；生产回归测试（学术基准不是回归门禁）；只要一个 quick score 时用已装的 [huggingface-community-evals](huggingface-community-evals.md) 即可，不必双栈并存。

## 最佳实践
- ⚠️ 定位判断：这是**知识型** skill（教 `lm-eval` 用法），不是执行器。装的唯一理由是"经常要用 lm-eval 且记不住参数矩阵"。若已覆盖在 huggingface-community-evals 里，**可以不装**，避免评估栈碎片化
- 热度只有 22、repo 17★、Snyk Warn：属于"内容看着没问题但社区验证薄"，按规约先过 [skill-criticagent](../cross-cutting/skill-criticagent.md)
- 环境隔离：`pip install lm-eval` 装到独立 venv，它的 transformers 版本约束常与项目主环境冲突
- 结果可比性：报告分数必须注明 harness 版本 + task 配置 + few-shot 数，否则不同来源的数字混在一起会得出错误结论
- 离线现场：`lm-eval` 会下载数据集，气隙环境需提前准备离线数据集与 `--include_path`

## 项目应用位点
- Zone B `validate`：模型选型公开分第二来源
- docs/evaluation.md 的 benchmark 章节参考

## 相关
[huggingface-community-evals](huggingface-community-evals.md) · [phoenix-evals](phoenix-evals.md) · [vllm-deploy-docker](vllm-deploy-docker.md)

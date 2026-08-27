# vllm-ascend 📦

> 状态：📦 可安装（未装）· 类型：推理栈部署（昇腾 NPU） · FDE 位点：Zone B deploy
> 候选 A（知识型）：`ascend-ai-coding/awesome-ascend-skills@vllm-ascend` · 63 installs · repo 164★ · https://skills.sh/ascend-ai-coding/awesome-ascend-skills/vllm-ascend
> 候选 B（官方 org · 工作流型）：`ascend/agent-skills@vllm-ascend-deploy` · 91 installs · repo 37★ · https://skills.sh/ascend/agent-skills/vllm-ascend-deploy
> 安装（择一）：`npx skills add ascend/agent-skills@vllm-ascend-deploy --directory ~/.qoder/skills -y`

## 能做什么
在**华为昇腾 NPU** 上跑 vLLM 推理服务：`vllm-ascend` 插件安装与版本匹配、必需环境变量（`VLLM_WORKER_MULTIPROC_METHOD=spawn`）、Ascend 优化 kernel、量化（W8A8 等）、多卡分布式推理。候选 B 额外提供一键部署工作流：SSH 检查 → 解析模型 → NPU 检查 → 配置发现 → 用户确认 → 执行部署 → 监控启动 → 验证服务。

## 何时使用
- 客户是国产算力环境（Atlas 800/300I、昇腾 910B），CUDA 路径不可用——国内工业/政企项目高频
- 现场已经在昇腾上起了服务但报 kernel/版本不匹配，需要按插件矩阵定位
- 写"私有化 LLM 可行性"方案时评估 NPU 侧的支持面

**不用于**：NVIDIA 卡（→ [vllm-deploy-docker](vllm-deploy-docker.md)）；昇腾**算子开发**（属另一类需求，registry 有 `ascend/agent-skills@ascendc-operator-*` 系列，超出 FDE 交付范围）。

## 最佳实践
- ⚠️ **安全审计现状**（skills.sh 页面可见，建档日 2026-08-27 复核）：候选 A = Agent Trust Hub **Fail** / Socket Pass / Snyk Warn；候选 B = 三项均 **Warn**。两者都**未通过干净审计**，属于必须先过门禁的类型
- 强制门禁：装前用 [skill-criticagent](../cross-cutting/skill-criticagent.md) 人工审 SKILL.md 全文，重点看候选 B 是否会**自动执行远程命令**（SSH + 部署脚本）——这类 skill 相当于给 agent 一把现场钥匙
- 若只用候选 A（纯知识、不改环境），风险显著更低，优先作为默认选择；需要执行部署时更宁愿手写 runbook
- 版本矩阵必须查官方文档：`vllm` / `vllm-ascend` / `CANN` / NPU driver 四元组强绑定，任一升级都可能失效
- 现场凭据：绝不把 SSH key/密码交给 skill 明文使用；走 [alibabacloud-workbench-cli](alibabacloud-workbench-cli.md) 或客户跳板机审批流程

## 项目应用位点
- Zone B deploy：国产化算力客户的模型服务落地路径
- Zone A：`fat_sat` gate 前评估“NPU + 目标模型”在客户设备上是否跑得动

## 相关
[vllm-deploy-docker](vllm-deploy-docker.md) · [skill-criticagent](../cross-cutting/skill-criticagent.md) · [alibabacloud-workbench-cli](alibabacloud-workbench-cli.md)

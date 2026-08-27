# vllm-deploy-docker 📦

> 状态：📦 可安装（未装）· 类型：推理栈部署 · FDE 位点：Zone B deploy（私有化 LLM）
> 来源：`vllm-project/vllm-skills@vllm-deploy-docker`（官方 org）· 热度：174 installs · 详情：https://skills.sh/vllm-project/vllm-skills/vllm-deploy-docker
> 同系列：`vllm-deploy-simple`（148）、`vllm-deploy-k8s`（112）
> 安装：`npx skills add vllm-project/vllm-skills@vllm-deploy-docker --directory ~/.qoder/skills -y`

## 能做什么
vLLM 官方容器部署指导：镜像选择（CUDA 版本/driver 匹配）、`--gpu-memory-utilization`/`--max-model-len`/tensor-parallel 参数、OpenAI 兼容 server 启动、量化与显存预算、健康检查与常见启动失败定位。

## 何时使用
- 客户要求**私有化 LLM**（数据不出厂），fde-scope 的 `llm` 层要指向内网 OpenAI 兼容端点
- 现场 GPU 机器（A10/A100/4090/昇腾）上把开源模型起成服务
- 评估"这个模型在这张卡上能不能跑、能撑多少并发"

**不用于**：只用 MiMo Token Plan 的公有云路径（→ [bailian-train-deploy](bailian-train-deploy.md)）；边缘小设备（→ `nvidia/skills@jetson-llm-serve`，1.1K）；昇腾 NPU（→ [vllm-ascend](vllm-ascend.md)）。

## 最佳实践
- 官方 org 出品，可信度高于社区同类，可直接作为主选；仍建议装前用 [skill-criticagent](../cross-cutting/skill-criticagent.md) 过一次门禁（版本迭代快，看是否与当前 vLLM 版本相符）
- 与 fde-scope 的契约：vLLM 起来后以 **OpenAI 兼容 base_url + key** 接入，凭据仍走 `FDE_SCOPE_MIMO_API_KEY` 风格的环境变量注入，不落配置文件
- 显存预算先算再跑：`模型权重 + KV cache`，`--gpu-memory-utilization` 从 0.9 起，OOM 时先降 `--max-model-len`
- 现场网络受限：镜像与权重都要走离线搬运（`docker save` + modelscope/HF 镜像源），提前列清单
- 版本锁定：交付时记录 vLLM / CUDA / driver / 模型 revision 四元组，否则无法复现

## 项目应用位点
- Zone B deploy：`fde_scope.llm` 的私有化后端落地
- Zone A air-gap gate：气隙环境下的模型服务可行性证据（[air_gap.py `AirGapGate`](../../../fde_scope/engagement/gates/air_gap.py)）

## 相关
[vllm-ascend](vllm-ascend.md) · [bailian-train-deploy](bailian-train-deploy.md) · [docker-build-deploy](docker-build-deploy.md)

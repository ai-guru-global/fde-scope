# huggingface-local-models

> 状态：✅ 已安装（hugging-face 插件 v1.0.0）· 类型：本地推理 · FDE 位点：Zone B build/deploy（客户内网 & air-gap）

## 能做什么
用 llama.cpp + GGUF 把开源模型跑在 CPU / Mac Metal / CUDA / ROCm 上：GGUF 检索与精确文件定位、量化档位选择、本地起服务、格式转换、OpenAI 兼容 serving。配套 `hf-mem` 可先估算权重加载内存再决定下哪个档。

## 何时使用
- 客户数据不能出域 / 无公网（air-gap 工厂、政务、金融内网）——LLM 能力只能本地化
- 现场用 MacBook 演示 Agent 能力，不依赖任何云端 API
- 低成本 PoC：单机跑通"LLM 参与的链路"，再决定是否上 GPU
- 给 fde-scope 这类"LLM 可选回退"系统准备本地端点做联调

**不用于**：有 GPU 集群且要并发吞吐（→ [vllm-deploy-docker](vllm-deploy-docker.md)）；昇腾 NPU（→ [vllm-ascend](vllm-ascend.md)）；模型训练/微调（→ [huggingface-llm-trainer](../zone-c-operationalization/huggingface-llm-trainer.md)）；客户已采购商用 API（直接接，别自建）。

## 最佳实践
- 量化选档：Q4_K_M 是吞吐/质量默认起点；给客户演示优先 Q5/Q6 起步，"答得慢但对"好过"快但胡说"
- 下载前先跑 `hf-mem` 估内存，现场机器爆内存是最难看的演示事故
- 用 OpenAI 兼容端点接系统：本仓库 `fde_scope/config.py` 的 LLM 接入即 OpenAI 兼容——本地服务 URL 指过去、`FDE_SCOPE_MIMO_API_KEY` 给任意占位值即可全链路验证回退逻辑
- 上下文长度吃内存：长上下文需求（语料摘要、工单全文）要把 KV cache 算进预算，别只看权重
- 许可证三查：GGUF 的发布许可、基座模型许可（部分禁商用/需申请）、客户合规红线
- 版本固化：把 GGUF 文件名 + llama.cpp commit 写进交付记录，别用"latest"复现不了

## 项目应用位点
- Zone B manufacturing 场景的 air-gap 部署形态（fde_scope/deploy 无网部署分支）
- LLM 回退链路测试：本地端点 → 断电 → 规则兜底，三态验证

## 相关
[vllm-deploy-docker](vllm-deploy-docker.md) · [vllm-ascend](vllm-ascend.md) · [huggingface-best](huggingface-best.md) · [bailian-cli](../cross-cutting/bailian-cli.md)

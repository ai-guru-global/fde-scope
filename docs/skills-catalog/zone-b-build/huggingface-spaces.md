# huggingface-spaces

> 状态：✅ 已安装（hugging-face 插件 v1.0.0）· 类型：Demo 托管 · FDE 位点：Zone B prototype / Zone D handoff 演示

## 能做什么
在 Hugging Face Spaces 上构建、部署、维护应用：Gradio / Docker / Static 三种 SDK，ZeroGPU 与专用硬件、模型加载、调试、buckets、inference providers、社区 grants 申请。产物是一个**可分享的公网链接**。

## 何时使用
- 给干系人一个"点开就能玩"的 POC 链接（售前比截图有说服力一个量级）
- 模型/数据集的配套 demo：训练完直接挂 Gradio 演示（配合 lora-space-builder 发 LoRA demo）
- 团队内轻量工具页：语料抽检、评测结果浏览器

**不用于**：客户真实数据上云（出境/合规不过就别想，→ 本地部署）；生产负载（Spaces 会休眠、无 SLA）；客户内网访问不到外网的演示（准备离线版）；包含客户敏感配置的镜像（公开 Space = 公开代码）。

## 新人上手

- **触发**："给干系人做一个点开就能玩的 demo 页"、"把这个模型/LoRA 发成 HF Space"
- **第一步**：先确认 `which hf` 有 CLI 且 `hf auth whoami` 已登录（未登录跑 `hf auth login`，需要 write token），再让 agent 用 `hf spaces search "<模型或任务>" --sdk gradio --limit 10` 找同类先例，参考其 `app.py` 的工作模式再动手
- **常见坑**：密钥写进代码或 requirements——公开 Space 默认一切可见，密钥只能走 Space secrets；ZeroGPU 忘加 `@spaces.GPU` 装饰、免费 `cpu-basic` Space 演示当天没提前唤醒预热——冷启动 30s+ 足以让干系人失去兴趣

## 最佳实践
- 密钥走 Space secrets，永远不进代码和 requirements；公开 Space 默认一切可见
- ZeroGPU 记得 `@spaces.GPU` 装饰，注意配额余量；演示前先自己跑一遍热身
- 免费 CPU Space 会休眠：**演示当天提前唤醒 + 预热**，冷启动 30s+ 足够让干系人失去兴趣
- Gradio 热更新迭代快，适合现场按干系人反馈当场改当场看
- 演示数据一律合成/脱敏；Space 描述里写清"数据仅用于演示"
- 移交阶段把 Space 链接 + 截图 + 归档说明写进交付文档，上游 repo 断更也有据可查

## 项目应用位点
- Zone D 移交演示：fde-scope 语料管线/评测结果的浏览器 demo
- Zone B 验证：让客户方工程师自己在浏览器里复现结论，比口头汇报可信

## 相关
[huggingface-gradio 相关训练页](../zone-c-operationalization/huggingface-llm-trainer.md) · [frontend-design](frontend-design.md) · [vercel-deploy](vercel-deploy.md)（另一条 demo 托管路径，适合纯 Web 应用）

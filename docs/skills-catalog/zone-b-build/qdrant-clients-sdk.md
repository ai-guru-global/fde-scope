# qdrant-clients-sdk

> 状态：📦 可安装（registry 真名 `qdrant/skills@qdrant-clients-sdk`）· 类型：工具/数据 · FDE 位点：Zone B · RAG 检索后端（向量库）
> 安装：`npx skills add qdrant/skills@qdrant-clients-sdk --directory ~/.qoder/skills -y` · 装机量：1.6K（skills.sh，2026-08-31）· 详情：https://skills.sh/qdrant/skills/qdrant-clients-sdk

## 能做什么
Qdrant 官方向量库 SDK skill：给六种官方客户端出正确的安装与用法代码——Python `qdrant-client`（`pip install qdrant-client[fastembed]`）、JS/TS `@qdrant/js-client-rest`、Rust `qdrant-client`（`cargo add`）、Go `github.com/qdrant/go-client`、.NET `Qdrant.Client`、Java `io.qdrant/client`（Maven Central）。内置 snippets 检索 API（`https://skills.qdrant.tech/snippets/search?language=python&query=...`，支持 python/typescript/rust/java/go/csharp、`&format=json`），按用例拉官方校对过的代码片段。同 repo 兄弟条目覆盖检索质量、性能、扩容、迁移：`qdrant-search-quality`、`qdrant-performance-optimization`、`qdrant-scaling`、`qdrant-sizing`、`qdrant-monitoring`、`qdrant-multitenancy`、`qdrant-deployment-options`、`qdrant-edge`、`qdrant-model-migration`、`qdrant-version-upgrade`。

## 何时使用
- 客户 RAG 后端选了 Qdrant，要写 Python/JS 等客户端接入代码（建 collection、上传 points、检索）
- 需要某个具体用例的官方代码片段（批量上传、过滤检索）而不想凭记忆写 API
- 评估 Qdrant 后续工程问题：检索质量差、延迟高、数据量涨、换 embedding 模型（→ 上述兄弟条目）

**不用于**：RAG 整体架构与 agent 编排（→ [rag-agent-builder](rag-agent-builder.md)）；embedding 模型本身怎么训练/选型（→ [train-sentence-transformers](train-sentence-transformers.md)）。

## 新人上手
- **触发**：对 agent 说「用 Qdrant 给这批文档建向量索引」「写一段 qdrant-client 的上传+检索代码」
- **第一步**：`npx skills add qdrant/skills@qdrant-clients-sdk --directory ~/.qoder/skills -y` 装完后先 `pip install 'qdrant-client[fastembed]'`，本地零服务原型可直接用内存模式实例化 `QdrantClient(":memory:")` 验证 API 写法，再指到真实 `--url`
- **常见坑**：SKILL.md 推荐 REST 而非 gRPC 给首次使用/原型——gRPC 端口（6334）与 REST（6333）不同，客户防火墙只开了 6333 时 gRPC 客户端会连不上
- **常见坑**：snippets 检索 API 走公网 `skills.qdrant.tech`——air-gap 客户环境拉不到片段，进内网前先把要用的片段缓存下来或离线阅读 qdrant-client 文档

## 最佳实践
- Do：上传用 `client.upload_points(collection_name=..., points=[models.PointStruct(id=..., payload=..., vector=...)], parallel=4, max_retries=3)`，带重试与并行
- Do：复用 id 重传是幂等覆盖、不传 id 会自动生成 UUID——增量更新管线要自己管理 id 稳定性，否则去重失效
- Don't：向量维度必须与创建 collection 时的配置一致，换 embedding 模型（维度变了）要重建 collection，别硬灌
- 现场：客户数据不出内网时，Qdrant 支持本地/自托管部署（兄弟条目 `qdrant-deployment-options`、`qdrant-edge`），是 air-gap RAG 的现实选项之一

## 项目应用位点
- Zone B `build`：RAG 原型的检索层落地——Qdrant collection 设计与客户端接入
- Zone B `validate`：检索质量不达标时按兄弟条目 `qdrant-search-quality` 的诊断路径排
- 客户量产扩容：`qdrant-scaling`/`qdrant-sizing` 决定单机还是集群，先小后大

## 相关
[rag-agent-builder](rag-agent-builder.md) · [train-sentence-transformers](train-sentence-transformers.md) · [query](query.md)

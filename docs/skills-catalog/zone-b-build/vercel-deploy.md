# vercel-deploy

> 状态：✅ 已安装（vercel 插件 v0.44.0；实际 skill 名为 `deployments-cicd` + `vercel-cli`，本页为"用 Vercel 上线 demo"的合页档案）· 类型：部署/平台 · FDE 位点：Zone B demo→客户可访问 URL

## 能做什么
把前端 demo 快速变成客户可点开的 URL：`vercel` CLI 部署、preview → production 提升、回滚、查看部署日志与构建产物（`--prebuilt`）、CI 工作流接入（GitHub/GitLab）。配套还有 env-vars、vercel-functions、vercel-storage、routing-middleware 等同插件 skill。

## 何时使用
- 现场给客户看原型：本地跑通后要一个**能分享**的链接，而不是让客户装环境
- 配 `.github/workflows/*` 做 PR preview 时
- 部署失败/环境变量丢失/缓存导致旧版本还在服务的排障

**不用于**：客户内网/离线场景（Vercel 出网不可用 → 走 [docker-build-deploy](docker-build-deploy.md) 或 [alibabacloud-workbench-cli](alibabacloud-workbench-cli.md)）；纯后端 Python 服务（fde-scope 的 FastAPI 主体）更适合容器化交付。

## 最佳实践
- Do：先 preview 再 promote——preview URL 是给客户"看一眼"的最小暴露面
- Do：Secret 走 `vercel env`，不要写进仓库或命令行历史
- Do：构建重复耗时长时用 `--prebuilt`（本地/CI 构建一次，部署只传产物）
- Don't：不要用 production 部署做冒烟测试；不要留着 demo 长期免费额度消耗
- 隐私红线：客户数据/真实工单一律不得进入 public preview；demo 只用合成数据（`fde_scope` 的 mock/JSONL 模式）

## 项目应用位点
- Zone B demo：Web 控制台前端或独立汇报面板的上线通道
- Zone D handoff：交付演示时的临时环境（会后即降级/删除）

## 相关
[cloudflare](cloudflare.md) · [docker-build-deploy](docker-build-deploy.md) · [frontend-design](frontend-design.md)

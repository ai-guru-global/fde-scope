# docker-build-deploy 📦

> 状态：📦 可安装（未装）· 类型：部署/生产化 · FDE 位点：Zone B deploy
> 来源：`wu529778790/shenzjd-skills@docker-build-deploy` · 热度：745 installs · 详情：https://skills.sh/wu529778790/shenzjd-skills/docker-build-deploy
> 备选：`ailabs-393/ai-labs-claude-skills@docker-containerization`（1.1K installs）、`thebushidocollective/han@docker-compose-production`（421）
> 安装：`npx skills add wu529778790/shenzjd-skills@docker-build-deploy --directory ~/.qoder/skills -y`

## 能做什么
把 Python 服务做成可交付容器：多阶段构建、层缓存顺序、非 root 用户、healthcheck、compose 编排、镜像瘦身与生产化 checklist。

## 何时使用
- **本仓库当前缺口**：`fde-scope` 仓库里没有任何项目级 Dockerfile / compose（仅 `.venv` 内 agentscope 自带的模板），要把 `fde_scope.web` 或 `pawapp/backend` 容器化交付时正好需要它
- 客户只接受"给一个镜像 + 一条 docker run"的交付形式
- 现场镜像体积/拉取时间成为阻塞（工业内网带宽有限）

**不用于**：sandbox 运行时隔离——那是 `fde_scope/deploy/sandbox_config.py` 通过 agentscope `DockerWorkspace` 做的事，已有自研实现，不要被外部 skill 改写语义；K8s 编排（→ [kubernetes-specialist](kubernetes-specialist.md)）。

## 新人上手

- **触发**：要把 Python 服务容器化交付时直接说"给 fde-scope 写一个多阶段 Dockerfile"或"现场镜像太大帮我瘦身"
- **第一步**：先安装 `npx skills add wu529778790/shenzjd-skills@docker-build-deploy --directory ~/.qoder/skills -y`（装前过一次 [skill-criticagent](../cross-cutting/skill-criticagent.md) 门禁），再让 agent 按该技能产出 `deploy/Dockerfile` + `deploy/docker-compose.yml`（本仓库当前正好缺失这两件）
- **常见坑**：把 `FDE_SCOPE_MIMO_API_KEY` 等凭据写进镜像层——现场审计会跑 `docker history`，密钥只能运行时 `-e`/secret 注入；`pip install` 层和源码拷贝层不分离——改一行代码就重装全部依赖，层缓存全部失效

## 最佳实践
- 装前门禁：社区个人源、热度中等 → 先用 [skill-criticagent](../cross-cutting/skill-criticagent.md) 评估；不通过就直接用官方 docker docs + 自建 `deploy/Dockerfile`
- Python 服务必做：`pip install` 层与源码拷贝层分离（缓存命中）、`--no-cache-dir`、锁定 `python3.12` 与 pyproject 一致、非 root `USER`
- 敏感信息：`FDE_SCOPE_MIMO_API_KEY` 等只能运行时注入（`-e`/secret），**不得进入镜像层**（现场审计会 `docker history`）
- 复现性：镜像 tag 绑定 git sha；交付文档里写清 `docker inspect` 取版本的方法
- 离线交付：内网客户要 `docker save/load` 的 tar 流程与校验和

## 项目应用位点
- Zone B deploy：补齐 `deploy/Dockerfile` + `deploy/docker-compose.yml`（当前缺失，属于可执行的改进项）
- Zone D handoff：镜像启动命令与回滚方式是交接文档必答项

## 相关
[kubernetes-specialist](kubernetes-specialist.md) · [vllm-deploy-docker](vllm-deploy-docker.md) · [alibabacloud-workbench-cli](alibabacloud-workbench-cli.md)

# alibabacloud-workbench-cli

> 状态：✅ 已安装（alibabacloud-workbench 插件 v1.1.0）· 类型：运维通道/CLI · FDE 位点：Zone B deploy + Zone C operate

## 能做什么
面向 **无公网 IP 的 ECS 实例** 的 agent 原生 CLI：毫秒级远程命令执行（`workbench exec`）、最大 1GB 文件传输（`upload`/`download`）、会话管理、实例查询过滤、5 种鉴权模式（AK / StsToken / RamRoleArn / CredentialsCmd / CredentialsURI）。插件自带 `scripts/install-cli.sh` 与 `scripts/wb-config.sh`，并有 `/alibabacloud-workbench:setup`、`/alibabacloud-workbench:doctor` 两个 command。

## 何时使用
- 客户的产线/测试机在 VPC 内、没有跳板机权限，需要"打进去跑一条命令、拿一份日志"
- 部署 fde-scope 容器或替换配置后需要即时验证（看进程、看端口、看日志）
- 大文件（数据集/模型权重）进出内网机器

**不用于**：有 SSH 直连的环境（直接 ssh 更简单）；非阿里云的机器（→ [docker-build-deploy](docker-build-deploy.md) / [kubernetes-specialist](kubernetes-specialist.md)）；批量生产变更（要走 IaC，不要用 exec 手搓）。

## 最佳实践
- 首次用先跑 `/alibabacloud-workbench:setup`（装 CLI + 配凭据），出问题用 `:doctor` 诊断，不要手工排查环境变量
- 凭据优先 `RamRoleArn` / `CredentialsCmd`，**不要把 AK 写进仓库或 shell 历史**；用 `wb-config.sh verify` 确认生效
- 命令幂等：exec 的脚本要能在重跑时不出副作用（现场网络抖动会重试）
- 需要出网到 `*.aliyuncs.com` 与 Workbench WebSocket，客户防火墙策略要提前申请——这是常见的交付前置条件
- 大文件传输走 `upload/download`（1GB 上限），不要 base64 塞进 exec
- 安全边界：现场机器上的任何写操作都要先向客户确认窗口期，日志里不留客户数据

## 项目应用位点
- Zone B deploy：把 fde-scope 服务落到客户 ECS（内网机）并自检
- Zone C operate：现场取日志/看进程/改配置的主通道
- docs/architecture.md 的部署侧运维入口

## 相关
[docker-build-deploy](docker-build-deploy.md) · [kubernetes-specialist](kubernetes-specialist.md) · [starops](../zone-c-operationalization/starops.md)

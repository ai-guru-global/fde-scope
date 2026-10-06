# Android 壳（demo 定性）

**这是一个 demo 壳，不可上架。** 它演示「QwenPaw 宿主里嵌 FDE 控制台」的形态，
不是发行目标。

为什么：

- `build.sh` 要求**手工**从腾讯镜像下载 Android 工具链（`build.sh:12-17`），不是可复现构建；
- APK 用**自动生成的 debug keystore**（`storepass android`，`build.sh:41-47`）签名，
  **没有 release 签名路径**——没有任何上架渠道接受 debug 签名；
- 没有接入任何 CI/发布流程。

如果要走向真发布：release keystore + 签名配置、可复现的工具链获取（或 gradle 托管）、
Play/Data 安全表单等合规材料——这是一项独立工程，当前未排期。
桌面端请用 macOS App（`appbuild/`，CI 有构建冒烟）或直接访问 Web 控制台。

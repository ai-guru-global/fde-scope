# macOS App 打包（FDE Scope.app）

把 Web 工作台打成一个**双击即用**的 Mac 应用：无需 Python、无需终端、无需安装任何依赖。
双击后自动在本地启动引擎（仅绑定 `127.0.0.1`），并在浏览器打开工作台 `http://127.0.0.1:8737/console`。

## 产物

| 文件 | 用途 |
|---|---|
| `appbuild/dist/FDE Scope.app` | 本机直接双击运行 |
| `appbuild/dist/FDE-Scope-<version>.dmg` | 分发：拖拽安装到“应用程序” |

## 构建

开发版（当前机器架构，一条命令）：

```bash
./appbuild/build_dmg.sh        # venv → pyinstaller → .app → .dmg
```

生产发布版（universal2 + 签名 + 溯源 + 正式 DMG）：

```bash
./appbuild/build_release.sh --arch universal   # 或 arm64 / x86_64
```

要求：本机有 [`uv`](https://docs.astral.sh/uv)（构建 venv 隔离在 `.venv-build-arm64/`、`.venv-build-x86_64/`，
不污染 `.venv`；x86_64 切片通过 Rosetta 在 Apple Silicon 上构建）。
开发版产物架构 = 构建机架构；`build_release.sh` 默认产出 **universal2**（arm64 + x86_64 同一个包）。

## 运行机制（appbuild/launcher.py）

1. **数据目录**：切换工作目录到 `~/Documents/FDE Scope/`（可用环境变量 `FDE_SCOPE_HOME` 覆盖）。
   engagement JSON（`.fde_scope/engagements/`）、技能库（`.fde_scope/skills/`）、语料报告（`reports/`）
   全部落在里面——升级/重装 App 不丢数据。
2. **端口**：默认 `8737`，被占用时自动换一个空闲端口（日志里有实际地址）。
3. **就绪后开浏览器**：轮询 `/api/health`，200 后 `webbrowser.open(.../console)`。
4. **退出**：windowed 应用没有 Cocoa 事件循环，退出用 `pkill -f "FDE Scope"`（SIGTERM 已映射到
   uvicorn 优雅关闭）；直接在 Dock 退出会由系统发 SIGKILL，数据同样无损（写入均为原子写）。
5. **单实例**：再次双击时若 8737 端口上已有健康的 FDE Scope（health 200 + 页面 title 指纹），
   只会重新打开浏览器，不会起第二个服务。
6. **可观测**：日志 `~/Documents/FDE Scope/fde-scope-app.log`（超 2MB 滚动一份备份）；
   主/子线程未捕获异常都写日志；每次启动打印 `build_info.json` 溯源信息
   （version / git sha / build time / arch），报障时能精确对应到构建。

## 生产级发布（build_release.sh + release.yml）

| 能力 | 实现 |
|---|---|
| Universal2 二进制 | 双 venv 各架构构建一次 → `merge_universal.py` 用 `lipo` 逐文件融合切片 |
| 版本溯源 | `appbuild/build_info.json` 在构建前写入并被 bundle 进去（version/git_sha/build_time/arch/git_dirty） |
| 加固运行时签名 | `codesign --options runtime --entitlements appbuild/entitlements.plist`（由内到外全量重签，覆盖 lipo 融合破坏的签名） |
| Apple 公证 | 检测到 Developer ID 证书时自动 `notarytool submit` + `stapler staple`；无证书降级 ad-hoc（跳过公证） |
| 正式 DMG | 可写镜像上摆好图标位置（app → Applications 拖拽布局）再转 UDZO；Finder 定制失败自动降级朴素 DMG |
| 发布清单 | `manifest.json`（签名方式/架构/公证状态） + `SHA256SUMS` |
| CI 自动出包 | 推 `v*` tag 触发 `.github/workflows/release.yml`（macos-14 runner），产物挂到 GitHub Release；公证靠仓库 secrets，缺 secrets 时仍能出 ad-hoc 包 |

本地上公证需要 Apple Developer 账号，secrets 配置见 `release.yml` 头部注释
（`DEVELOPER_ID_P12_BASE64` / `NOTARY_API_KEY_ID` 等）。

## 分发注意事项（Gatekeeper）

App 默认是 **ad-hoc 签名**（无 Apple Developer ID 时）：

- 本机自己构建的 app 没有隔离属性，双击直接可用；
- 别人通过浏览器/微信等拿到 `.dmg` 后，首次打开会被 Gatekeeper 拦截，任选其一：
  - **右键 → 打开**（一次性确认）；
  - `xattr -dr com.apple.quarantine "/Applications/FDE Scope.app"`；
- 要彻底消除提示需 Apple Developer 证书做 Developer ID 签名 + notarization——
  `build_release.sh` 已内置（检测到证书自动启用），或在 CI 上配好 secrets 由 `release.yml` 完成。

## 文件清单

```
appbuild/
├── launcher.py         # App 入口（数据目录/端口/健康检查/开浏览器/单实例/日志滚动/优雅退出）
├── FDEScope.spec       # PyInstaller 配置（windowed、模板 --add-data、uvicorn hiddenimports、build_info 注入）
├── FDEScope.icns       # App 图标（16→1024 全尺寸）
├── build_dmg.sh        # 开发版一键 .app + .dmg
├── build_release.sh    # 生产发布：多架构构建 → universal 合并 → 签名 → DMG → manifest
├── merge_universal.py  # 两个单架构 bundle 的 lipo 融合器
└── entitlements.plist  # hardened runtime 下 Python 加载动态库所需的 entitlements
```

打包要点（踩过的坑）：

- `fde_scope/templates/` 必须 `datas` 进 bundle——`report.py` / `operationalization.py`
  用 `__file__` 相对路径加载 Jinja2 模板；
- uvicorn 的 `loops/protocols/lifespan` 实现是运行时按名字符串导入的，需列入 `hiddenimports`；
- 冻结应用里 `uvicorn.run()` **不能传 import string + reload/workers**，必须传 app 对象单进程跑；
- 目录名不要叫 `packaging/`——与 PyPA `packaging` 库同名会在构建 venv 里互相遮蔽；
- universal 合并后**所有签名都会失效**（lipo 重写字节），必须“由内到外”整体重签，
  `build_release.sh` 在合并后统一做；
- hardened runtime 下 Python 加载 ad-hoc 签名的 `.so` 会被拦，需要
  `com.apple.security.cs.disable-library-validation` 等 entitlements（见 `entitlements.plist`）。

## 已验证（2026-08-27，macOS 26.5.2 arm64）

- `open "FDE Scope.app"` → health 200、`/console` 200、创建 engagement 成功；
- 从 **DMG 只读卷内直接启动** → 全功能正常，SIGTERM 优雅退出；
- 打包后完整跑通 CSV 上传 → 语料锻造（含 bundle 内模板渲染的 HTML 报告）→ `/reports/*` 回读 200。

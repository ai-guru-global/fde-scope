# 第三方依赖 License 审计

审计日期：2026-09-28 · 方法：`pip show` / package metadata（`License` / `License-Expression` / classifiers）· 范围：`pyproject.toml` 全部直接依赖（core + extras）。

## 审计表

| 包 | 版本（审计时） | License | 风险等级 | 备注 |
|---|---|---|---|---|
| typer | 0.27.2 | MIT | 低 | CLI 框架 |
| rich | 15.0.0 | MIT | 低 | 终端输出 |
| pydantic | 2.13.5 | MIT | 低 | 数据模型核心 |
| pyyaml | 6.0.3 | MIT | 低 | 配置解析 |
| jinja2 | 3.1.6 | BSD-3-Clause | 低 | 报告模板（classifier 标注 BSD） |
| agentscope | 2.0.8 | Apache-2.0 | 低 | agent 运行时；Apache-2.0 与 MIT 兼容，注意其 NOTICE 传递义务 |
| redis | 8.1.0 | MIT | 低 | `serve` extra：`agentscope[service]` 的 RedisStorage 需要但上游未带入 |
| mysql-connector-python | 26.7.0 | GPL-2.0 + FOSS License Exception | **中** | 强 copyleft + FOSS 例外；FOSS 例外明确允许与 MIT 等开源许可组合。保持 optional extra，不 vendored、不静态嵌入；嵌入式/闭源再分发场景需法务确认 |
| asyncua | 2.0.1 | LGPL-3.0-or-later | **中** | 弱 copyleft；以未修改的独立包动态引用通常不构成 derivative work；禁止把 asyncua 源码改后随产品分发而不开源修改 |
| paho-mqtt | 2.1.0 | EPL-2.0 OR BSD-3-Clause（双许可） | 低-中 | 弱 copyleft（EPL 仅及于 EPL 文件本身）；Python 包引用未修改 wheel 不构成衍生作品；可选按 BSD-3-Clause 使用更稳妥 |
| rosbags | 0.11.5 | Apache-2.0 | 低 | ROS 2 bag 解析 |
| fastapi | 0.141.1 | MIT | 低 | Web 层 |
| uvicorn | 0.53.0 | BSD-3-Clause | 低 | ASGI server |
| python-multipart | 0.0.32 | Apache-2.0 | 低 | 表单解析 |
| pytest | 9.1.1 | MIT | 低 | 仅 dev，不随产品分发 |
| pytest-cov | 7.1.0 | MIT | 低 | 仅 dev |
| httpx | 0.28.1 | BSD-3-Clause | 低 | 仅 dev |

## 结论

1. **与 MIT 主许可兼容**：全部 17 个直接依赖均与 MIT 兼容。其中 11 个为
   permissive（MIT/BSD/Apache），不存在许可冲突。
2. **三个 copyleft 包全部是 optional extra**（`mysql` / `opcua` / `mqtt`），
   核心安装（`pip install fde-scope`）只含 MIT/BSD 依赖，核心分发无 copyleft 暴露。
3. **paho-mqtt（EPL-2.0/EDL 双许可）**：EPL-2.0 的 copyleft 仅覆盖 EPL 文件本身；
   以 pip 包形式动态引用未修改的 paho-mqtt 通常不构成衍生作品。注意点：
   不要修改其源码后闭源分发；二进制/嵌入式分发建议附 EPL 声明文本；
   正式商业分发前建议法务确认。
4. **mysql-connector-python（GPLv2 + FOSS 例外）**：FOSS License Exception 明确
   允许与 MIT 许可代码组合分发，但 GPL 文本义务随组合产品生效的场景（如把
   connector 打包进一体机镜像）建议法务逐案确认。
5. **asyncua（LGPLv3+）**：动态引用未修改包满足 LGPL；若未来需要 patch
   asyncua，修改部分须以 LGPL 公开。
6. **守护机制**：`tests/test_third_party_licenses.py` 解析 `pyproject.toml`
   的直接依赖并断言每个包在 `NOTICE` 中有条目，新增依赖漏审计会导致 CI 变红。

> 本文件为工程自查记录，不构成法律意见；商业化分发前请法务复核带 ★ 的包。

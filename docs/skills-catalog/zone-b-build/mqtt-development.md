# mqtt-development 📦

> 状态：📦 可安装（未装）· 类型：领域知识 · FDE 位点：Zone B · connect（工业消息）
> 来源：`mindrally/skills@mqtt-development` · 热度：908 installs · 详情：https://skills.sh/mindrally/skills/mqtt-development
> 安装：`npx skills add mindrally/skills@mqtt-development --directory ~/.qoder/skills -y`

## 能做什么
MQTT 协议开发模式与最佳实践参考（订阅/QoS/保留消息/遗嘱等），辅助排查与实现消息接入层代码。

## 何时使用
- 对接客户 MQTT broker、调试 `fde_scope.connectors.mqtt_sparkplug` 相关问题时作为参考手册
- 现场设备上报异常（掉线、重复、乱序）需要协议层判断

**不用于**：fde-scope 已有自研 connector——以我方可控实现为主，该 skill 只做知识辅助，不要让外部 skill 改写核心连接器语义。

## 最佳实践
- 装前门禁：先用 [skill-criticagent](../cross-cutting/skill-criticagent.md) 评估（社区 skill，质量未经官方验证）
- Sparkplug 规范（状态机 NDEATH/DBIRTH）细节该 skill 未必覆盖，冲突时以 `fde_scope/connectors/mqtt_sparkplug.py` 的实现与规范原文为准
- 评估通过后再安装，并把结论回写本页"最佳实践"段

## 项目应用位点
- Zone B `connect` 工业消息接入的辅助知识
- tests/test_mqtt_connector.py 排障参考

## 相关
[read-file](read-file.md) · [skill-criticagent](../cross-cutting/skill-criticagent.md)

# systematic-debugging

> 状态：✅ 已安装（superpowers 插件 v5.1.0）· 类型：方法论/流程约束 · FDE 位点：Zone B test + Zone C operate

## 能做什么
遇到任何 bug、测试失败、非预期行为时，**在提出修复之前**强制走完整流程：复现 → 定位（读代码/加日志/二分）→ 假设 → 最小验证 → 修复 → 回归。是 superpowers 全家桶里对交付质量最有杠杆的一个。

## 何时使用
- 任何"看起来是 X 问题所以改一下 X"的冲动出现时——这就是它的触发点
- 测试失败但你不确信是测试错还是实现错
- 现场环境只有只读权限、不能试错时（先推理再动）

**不用于**：纯需求变更（不是 bug）；性能调优（→ [web-perf](web-perf.md) / [debug-optimize-lcp](debug-optimize-lcp.md)）；跨系统监控类排障（→ [investigate](investigate.md)）。

## 最佳实践
- 与 [test-driven-development](../cross-cutting/using-superpowers-family.md) 配套：先用失败测试固化 bug，再修
- 写下"当前假设 + 证伪方式"再继续，避免无限层猜测
- 一次只改一个变量；改完没解决要**回滚**再换假设，不要叠加改动（最容易造成"看起来修好了"）
- 修复后补一条能防止复现的测试，交付项目里这是客户信任的基础
- Don't：不要在该 skill 的流程里顺手重构——把重构和修 bug 分成两个提交

## 项目应用位点
- Zone B `build/test`：`tests/` 下任何失败的处理规范
- Zone C：连接器/评估指标异常的定位流程（配合 [investigate](investigate.md)）

## 相关
[investigate](investigate.md) · [troubleshooting](troubleshooting.md) · [using-superpowers-family](../cross-cutting/using-superpowers-family.md)

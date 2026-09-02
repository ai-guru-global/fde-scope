# notion-infographic

> 状态：✅ 已安装（`~/.qoder/skills/notion-infographic`）· 类型：视觉化 · FDE 位点：Zone D present / 传播

## 能做什么
读参考文稿，批量生成 **Notion 风格松弛感手绘信息图组图**，适合社交媒体/内部传播的分发单元（一张一个要点）。

## 何时使用
- 把方案/成果/流程变成一组易传播的图（内部宣导、客户高层"看图 30 秒"场景）
- 公众号/内网帖子需要统一视觉的系列配图
- 长文档需要"图解摘要"降低阅读门槛

**不用于**：需要精确数据与坐标的正式图表（用 [data-visualization 类工具](../zone-b-build/frontend-design.md) 或 matplotlib）；工程图纸/架构图（→ [drawio](../zone-a-pre-engagement/drawio.md) / [architecture-communicator](../zone-a-pre-engagement/architecture-communicator.md)）；正式验收材料（风格过于随意）。

## 新人上手

- **触发**：对 agent 说"阅读 docs/xx.md，生成一组信息图" / "把这篇文稿做成 Notion 风格组图"（description_zh：根据参考文稿批量生成信息图组图）
- **第一步**：对 agent 说"读 `docs/成果.md`，生成 5 张信息图"——可指定张数；不指定则按文章意图自动定（每图一个观点，硬上限 12 张），逐张调用 imageGen 出 16:9 中文标注图
- **常见坑**：
  - 风格前缀/后缀是硬性约束：每张图提示词必须完整保留同一段风格描述（纯黄主色、马克笔松弛笔触、禁止渐变/3D/阴影/密集文字），省略任何细节整组图风格就散了
  - 单张图只放 1 个信息点，堆多个观点是明确禁止项；产物按 `infographic-01.png` 起顺序编号，便于整组分发

## 最佳实践
- 输入文稿先分点（每点一张图），否则组图信息密度失衡
- 风格一次定锚：先出 2~3 张确认风格，再批量，避免整批返工
- 严格禁止"编造数据"：图上所有数字必须来自源文稿，逐张核对
- 中英混排的手绘字体容易失真，专有名词保留原文并检查字形
- 版权与品牌：客户 logo/受版权字体不要进传播素材

## 项目应用位点
- Zone D：交付成果的可视化传播（内部知识库/客户宣导）
- 与 [podcast](podcast.md) 组成"同一份文档 → 多种传播形态"

## 相关
[shifu](shifu.md) · [visual-deck-builder](visual-deck-builder.md) · [drawio](../zone-a-pre-engagement/drawio.md)

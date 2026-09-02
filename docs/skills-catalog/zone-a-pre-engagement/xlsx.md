# xlsx

> 状态：✅ 已安装 · 类型：工具/数据 · FDE 位点：Zone A/B（点单）· D（报表）

## 能做什么
高级电子表格工具箱：数据与公式双向抽取、复杂格式处理、专业表格生成、可填表单。处理 Excel/CSV/TSV 的默认技能。

## 何时使用
- 用户附 `.xlsx/.csv/.tsv` 文件或提到 spreadsheet/工作表/报表
- 交付结构化报表（KPI 表、bad case 清单、语料盘点表）
- 需要保留公式/多 sheet 结构的表格操作

**不用于**：只需看数据内容不关心格式（→ [read-file](../zone-b-build/read-file.md)）；超大数据文件分析（→ DuckDB [query](../zone-b-build/query.md)）。

## 新人上手

- **触发**：附 `.xlsx/.csv/.tsv` 文件，或提到 spreadsheet / 工作表 / 报表 / 数据分析
- **第一步**：数据画像用 pandas：`pd.read_excel('file.xlsx', sheet_name=None)` 一次拿全部 sheet，再 `df.head()` / `df.info()` 确认列结构
- **常见坑**：公式类需求必须生成真 Excel 公式（如 `=B5*(1+$B$6)`），不许在 Python 里算死硬编码；交付标准是零公式错误（#REF!/#DIV/0! 等）
- **常见坑**：公式求值依赖 LibreOffice（`formula_processor.py`），环境里没有会跑不动；改既有文件要保住原模板格式，别用统一格式覆盖客户既有约定

## 最佳实践
- Do：先 `read-file`/画像确认列结构，再决定转换或分析路径
- Do：公式计算类需求直接生成带公式的 xlsx，不要预先在代码里算死
- Don't：不要用文本方式手改二进制；合并多表时注意列名归一
- 现场：客户工单导出、设备点检表几乎都是 xlsx，是 connectors 之外的重要入口

## 项目应用位点
- Zone B `connect`：客户点检表/工单表 → `fde_scope.connectors.csv_fallback` 前的格式归一（`convert-file`）
- Zone C KPI 报表（OEE/MTBF 表）交付

## 相关
[read-file](../zone-b-build/read-file.md) · [convert-file](../zone-b-build/convert-file.md) · [query](../zone-b-build/query.md)

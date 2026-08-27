# spatial

> 状态：✅ 已安装（duckdb-skills 系）· 类型：工具/数据 · FDE 位点：Zone B · 地理数据分析

## 能做什么
用 DuckDB 回答地理空间问题：位置/坐标/距离/地图地址、邻近与包含判断、GeoJSON/Shapefile/GeoPackage/GPX/GeoParquet 格式处理；全球基础地图数据经 Overture Maps（S3 免费无 key）。

## 何时使用
- 提到 lat/lng、距离、"离 X 最近的"、区域包含、地图数据文件
- 物流/车辆/网点类客户数据的空间分析（工单地理分布、服务站覆盖）

**不用于**：非空间的普通数据分析（→ query）；地图渲染类产品开发。

## 最佳实践
- Do：先确认坐标系（WGS84 vs 投影坐标），距离计算错坐标系是最常见事故
- Do：大表空间 join 前用边界框粗筛再精算
- Don't：不要拿 Overture 数据当权威产权/行政数据交付客户，注明数据源与时间

## 项目应用位点
- 制造业/物流案例：园区设备点位、巡检路线覆盖分析
- ticket 场景的网点地理热力图数据准备

## 相关
[query](query.md) · [convert-file](convert-file.md)

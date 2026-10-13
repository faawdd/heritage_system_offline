# Wave 1 Implementation Status

## Implemented

### Backend v1 APIs

- `GET /api/v1/heritage/map-points/`
- `GET /api/v1/heritage/stats/meta/`
- `GET /api/v1/heritage/classification-stats/` (legacy logic reused)
- `GET /api/v1/heritage/<site_id>/detail/`
- `POST /api/v1/heritage/<pk>/boundary-export/` (legacy export reused)

### Frontend Pages

- `/heritage/map` 文物一张图（OpenLayers）
- `/heritage/stats` 文物统计（Element Plus + ECharts）
- 乡镇统计、筛选及下拉选项使用统一口径：优先使用关联登记档案的乡镇，缺失时解析地址开头的行政区划；不使用后续距离描述中的附近乡镇。鄯善历史乡镇名和常见异写合并为标准名称（如辟展乡 → 辟展镇、达浪坎乡 → 达朗坎乡），去除名称空白，不修改原始档案。无法识别所在地的记录归入“未标注乡镇”。
- `/heritage/:siteId` 文物详情（OpenLayers + 边界导出）

### Component Split

- `components/heritage/HeritageMapCanvas.vue`
- `components/heritage/HeritageStatsChart.vue`
- `components/heritage/HeritageZoneMap.vue`

## Compatibility Guarantees

- Database schema unchanged.
- Django models unchanged.
- FastAPI unchanged.
- Existing admin templates/URLs remain online.
- Existing API behavior reused where possible.

## Validation

- `python manage.py check` passed.

## Current Known Gap

- Node/npm missing in current environment; frontend runtime build test pending.

## Next Wave

- Migrate GIS/KML module pages using same function-migration method.
- Keep upload/download/analysis behavior unchanged and reuse existing APIs.

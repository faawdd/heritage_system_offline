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

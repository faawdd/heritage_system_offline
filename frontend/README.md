# Frontend (Vue3 + Vite)

## Stack

- Vue3
- Vite
- Pinia
- Vue Router
- Axios
- Element Plus
- ECharts
- OpenLayers

## Development

```bash
cd frontend
npm install
npm run dev
```

Default dev server: `http://localhost:5173`

API proxy target is configured to `http://127.0.0.1:8000`.

## Build

```bash
cd frontend
npm run build
```

Build output target: `../static/frontend`

## Notes

- This migration keeps legacy Django template pages online.
- New frontend pages are migrated module by module.
- Backend API namespace is `/api/v1/` for new pages.

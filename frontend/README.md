# 基层文物管理系统（Vue 离线版前端）

![Brand Logo](../logo.png)

![品牌](https://img.shields.io/badge/品牌-基层文物管理系统-0A5C36)
![形态](https://img.shields.io/badge/形态-Vue3%20%2B%20Electron-1D4ED8)
![定位](https://img.shields.io/badge/定位-离线部署-9A3412)

> 本前端为离线桌面系统 UI 层，打包后的 Electron 应用图标使用 `../logo.png`。

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

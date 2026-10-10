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

## 四普导入与业务页面

- 四普导入的完整登记档案保存在 `ImmovableHeritage`，通过四普编号与
  `HeritageSite` 建立一对一关联。不可移动文物管理、文物一张图和 KML
  叠加检查使用后者；导入时会自动创建或更新对应文物点，不按名称合并。
- 不可移动文物管理中的“完整档案”按钮可查看和编辑关联登记表的全部字段。
  两个编辑入口保存的基础信息会同步，避免地图与完整档案不一致。
- “更新已有文物点边界”开关只影响已有文物点的边界更新，不影响档案进入
  业务页面；新文物点始终保存本次导入取得的边界。
- 升级已有部署时，先备份数据库，再在项目根目录执行
  `.venv/bin/python manage.py migrate`（其他环境使用对应的 Python 解释器）。
  `0038_heritagesite_registration` 会补齐此前已导入四普但未进入业务文物库的
  记录，保留已有文物点 ID 和非空边界，无需重新登录四普或重新下载附件。
  完成后重启服务并刷新页面。在线版和离线版都需要执行迁移。

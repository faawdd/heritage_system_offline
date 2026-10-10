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

## 地图定位与公文文号

- 文物一张图、仪表盘及未选择 KML 的叠加地图按有效文物点分布居中并适配范围；
  无有效文物点时显示全国。空值、非有限值、越界坐标和导入时代表缺失的
  `(0, 0)` 不参与定位。数据异步返回后会重新计算范围。
- 选择 KML 或冲突对象后优先聚焦所选数据；详情地图显示当前文物点及全部
  本体、保护范围、建控地带区块。离线地图包预览按地图包覆盖范围定位。
- 项目详情的县局请示文号按当地实际文号输入，不再限制地区前缀、年份或
  编号格式；必填项、附件要求和最大长度仍保留。升级时执行数据库迁移
  `0039_alter_landuseprojectapproval_shanshan_request_num`。
- 定位回归测试：在前端目录执行 `node --test src/utils/mapViewport.test.js`。

# Function Migration Analysis - Wave 1

## A. 全量页面分组（按业务域）

### 1) 文物管理域
- templates/admin/heritage_map.html
- templates/admin/heritage_dashboard.html
- templates/admin/heritage_detail.html
- templates/admin/core/heritagesite/change_list.html

### 2) 项目审批域（已进入迁移）
- templates/admin/land_project_management.html
- templates/admin/land_project_edit.html

### 3) GIS/KML域
- templates/admin/kml_overlay_check.html
- templates/admin/kml_management.html
- templates/admin/kml_process_convert.html
- templates/admin/ovkml_converter.html

### 4) 巡查管理域
- templates/admin/inspection_mobile.html
- templates/admin/inspection_mobile_list.html

### 5) 坎儿井专项域
- templates/admin/kanerjing_list.html
- templates/admin/kanerjing_import_check.html

### 6) 首页与系统入口
- templates/admin/index_dashboard.html
- templates/admin/index_custom.html
- templates/admin/home_dashboard.html
- templates/admin/base_site.html

### 7) 公众与移动入口
- templates/public/app_showcase.html
- templates/public/heritage_collect.html
- templates/public/detail_preview.html

---

## B. Wave 1 页面分析（文物管理域）

## Page 1: 文物一张图

### ① 页面职责分析
- 全县文物点地图总览。
- 提供等级筛选、名称搜索、点位定位。

### ② 页面功能分析
- 点位渲染（按等级颜色）。
- 关键词搜索联想并飞行定位。
- 等级多选过滤显示。
- 鼠标坐标实时显示。

### ③ 数据来源分析
- 当前来自服务端模板变量 sites_json（服务端 render 注入）。
- 来源视图为 core.views.heritage_map_view。

### ④ 权限分析
- @staff_member_required。
- 仅后台登录用户可访问。

### ⑤ AJAX请求分析
- 当前页面无 fetch/axios 请求。
- 迁移后应改为 Axios 拉取点位 API。

### ⑥ 表单分析
- 无传统表单提交。
- 有搜索输入框与筛选复选框。

### ⑦ 弹窗分析
- 地图 marker popup（文物基础信息+查看详情链接）。

### ⑧ 文件上传分析
- 无。

### ⑨ 文件下载分析
- 无直接下载。

### ⑩ 地图功能分析
- 当前使用 Leaflet + 天地图底图。
- 迁移目标：OpenLayers 重建底图、点图层、筛选、搜索定位。

### 数据流设计（迁移后）
- Vue onMounted -> GET /api/v1/heritage/map-points/ -> store -> OpenLayers vector layer。
- 侧栏筛选 -> computed filtered features -> 图层刷新。

### API设计（新增，不破坏旧接口）
- GET /api/v1/heritage/map-points/
  - response: [{id, name, level, lng, lat}]

### 页面结构设计
- 顶部: 标题 + 搜索。
- 左侧: 图层与等级筛选卡。
- 中央: 地图主画布。
- 右侧: 当前选中文物信息卡。

### Vue组件拆分
- views/heritage/HeritageMapView.vue
- components/heritage/HeritageMapCanvas.vue
- components/heritage/HeritageMapFilterPanel.vue
- components/heritage/HeritageSearchBox.vue
- components/heritage/HeritageSelectionCard.vue

---

## Page 2: 文物分类统计面板

### ① 页面职责分析
- 面向管理端的文物统计与筛选分析。

### ② 页面功能分析
- 统计维度切换（类别/等级/乡镇）。
- 坎儿井范围过滤。
- 类别/等级/乡镇/地址关键词组合筛选。
- 图表与明细表联动展示。

### ③ 数据来源分析
- 初始筛选选项来自模板变量 category_choices_json/level_choices_json/township_options_json。
- 核心统计来自 /api/heritage-classification-stats/。

### ④ 权限分析
- @staff_member_required。

### ⑤ AJAX请求分析
- fetch /api/heritage-classification-stats/?...。

### ⑥ 表单分析
- 多个 select + 关键词 input。

### ⑦ 弹窗分析
- 无复杂弹窗。

### ⑧ 文件上传分析
- 无。

### ⑨ 文件下载分析
- 无。

### ⑩ 地图功能分析
- 本页无地图。

### 数据流设计（迁移后）
- 初始化加载筛选元数据和统计结果。
- 条件变化后 debounce 请求统计 API。

### API设计（优先复用）
- 复用: GET /api/heritage-classification-stats/
- 新增（可选）: GET /api/v1/heritage/stats/meta/（统一返回下拉选项，摆脱模板变量依赖）

### 页面结构设计
- 顶部: 标题 + 返回地图按钮。
- 筛选区: Element Plus Form Inline。
- 指标区: Statistic 组件。
- 内容区: 左图表（ECharts）右明细表（Table）。

### Vue组件拆分
- views/heritage/HeritageStatsView.vue
- components/heritage/HeritageStatsFilterForm.vue
- components/heritage/HeritageStatsChart.vue
- components/heritage/HeritageStatsTable.vue

---

## Page 3: 文物档案详情页

### ① 页面职责分析
- 单文物档案总览与只读查看。
- 包含边界范围可视化、巡查记录、四普边界导出入口。

### ② 页面功能分析
- 基础信息/扩展信息展示。
- 两线坐标（保护范围、建控地带）地图展示。
- 最近巡查记录展示。
- 单文物四普边界导出（CSV/KMZ）。

### ③ 数据来源分析
- 当前主数据来自 render context（heritage、protection_zone_data、control_zone_data、inspection_records）。
- 导出提交到 heritage_boundary_export。

### ④ 权限分析
- @staff_member_required。
- 只读详情，但页面有“编辑此文物”跳转。

### ⑤ AJAX请求分析
- 当前主要为页面内脚本渲染，不依赖异步 API 拉主数据。

### ⑥ 表单分析
- 四普导出表单：cookie、county、action（csv/kmz）。

### ⑦ 弹窗分析
- 地图 popup。

### ⑧ 文件上传分析
- 无直接上传。

### ⑨ 文件下载分析
- 四普边界 CSV/KMZ 下载（POST 后返回文件）。

### ⑩ 地图功能分析
- 当前 Leaflet + 天地图，叠加文物点、保护范围、建控地带。
- 迁移目标：OpenLayers 统一实现，并保持现有边界几何逻辑和可视效果。

### 数据流设计（迁移后）
- onMounted -> GET /api/v1/heritage/{id}/detail/
- 导出按钮 -> POST /api/v1/heritage/{id}/boundary-export/（服务端仍复用旧业务）

### API设计（新增，不改业务）
- GET /api/v1/heritage/{id}/detail/
- POST /api/v1/heritage/{id}/boundary-export/

### 页面结构设计
- 顶部: 标题 + 返回 + 编辑跳转。
- 主区: 左侧档案信息卡，右侧 OpenLayers 地图卡。
- 下区: 巡查记录时间线 + 导出面板（Drawer/Dialog）。

### Vue组件拆分
- views/heritage/HeritageDetailView.vue
- components/heritage/HeritageBaseInfoCard.vue
- components/heritage/HeritageZoneMap.vue
- components/heritage/HeritageInspectionTimeline.vue
- components/heritage/HeritageBoundaryExportPanel.vue

---

## C. 业务逻辑拆分建议（Template 混合逻辑）

### 应迁入 services
- 乡镇归一化与筛选组合构建。
- 文物点地图数据投影/清洗。
- 详情页边界数据整理（保护范围、建控地带）。

### 应迁入 API
- 所有模板变量数据（sites_json、choices、detail context）改为 API 输出。
- 导出动作保留原业务函数，增加 v1 包装路由。

### 应迁入 Vue
- 交互状态（筛选条件、搜索词、激活图层、弹窗状态）。
- 图表、表格、地图组件渲染。

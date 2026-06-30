# Function Migration Analysis - Wave 2 (GIS/KML)

## Page A: KML 文件管理与批量冲突检查（kml_management）

1) 页面职责
- KML/KMZ 文件上传、记录管理、冲突复算、边界导出、地图叠加查看。

2) 页面功能
- 多文件上传与即时分析。
- 批量勾选记录并执行冲突查询、导出 CSV/KML、导出四普边界 CSV/KMZ。
- 记录重命名、删除、单条查询。
- 地图叠加（文物点 + KML + 冲突标记）与测距辅助。

3) 数据来源
- KmlUploadRecord 列表、HeritageSite 点位。
- 冲突结果来自记录 report_json 或实时复算。

4) 权限控制
- _is_admin_user（管理权限）。

5) AJAX 请求
- 页面脚本存在前端解析 KML/KMZ 与地图叠加逻辑。
- 服务端主要通过表单 POST 行为处理。

6) 表单
- 上传表单、批量操作表单、四普 cookie 表单。

7) 弹窗
- 冲突明细浮层、操作提示。

8) 文件上传
- KML/KMZ/OVKML/OVKMZ 上传。

9) 文件下载
- 冲突报告 CSV、冲突 KML、边界 CSV、边界 KMZ、源文件下载。

10) 地图功能
- 多底图切换、叠加显示、冲突定位。
- 迁移目标：统一 OpenLayers。

---

## Page B: KML处理和转换（kml_process_convert）

1) 页面职责
- DXF->KML；KML/KMZ 生成坐标表（预览/导出 CSV）。

2) 页面功能
- 双工具模式：DXF 转换、坐标表转换。
- 输入坐标系和输出模式切换。

3) 数据来源
- 上传文件或已上传记录（KmlUploadRecord）。

4) 权限控制
- _is_admin_user。

5) AJAX 请求
- 原页面为同步表单提交。
- 迁移后改 Axios + 文件流下载。

6) 表单
- dxf_file、source_mode、uploaded_record_id、kml_file、input_crs、output_mode、geo_output_crs。

7) 弹窗
- 无复杂弹窗。

8) 文件上传
- DXF、KML/KMZ。

9) 文件下载
- KML 下载、CSV 下载。

10) 地图功能
- 无。

---

## Page C: OVKML/KML/KMZ 转换导入（ovkml_converter）

1) 页面职责
- 提取 Placemark，导出 ProjectAudit CSV/明细 CSV，可直接导入 ProjectAudit。

2) 页面功能
- 坐标系转换、去重导入、预览。

3) 数据来源
- 上传文件；导入写入 ProjectAudit。

4) 权限控制
- @staff_member_required。

5) AJAX 请求
- 原页面同步表单提交。
- 迁移后改 Axios 提交、文件下载。

6) 表单
- ovkml_file/input_crs/output_crs/deduplicate/action(convert/import)。

7) 弹窗
- 无复杂弹窗。

8) 文件上传
- KML/OVKML/KMZ/OVKMZ。

9) 文件下载
- ProjectAudit CSV、Detail CSV。

10) 地图功能
- 无。

---

## 拆分原则（本轮实施）
- 业务逻辑保留在后端，Vue 只承载交互。
- 新增 `/api/v1/gis/*` API，旧页面与旧 URL 保留。
- 先完成 B/C 两个页面完整迁移；A 页面先做 v1 API 与基础 Vue 管理页，地图增强下一轮补齐。

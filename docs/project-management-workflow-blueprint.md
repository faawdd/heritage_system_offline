# 建设项目管理（流程驱动）模块整体设计蓝图

## 1. 目标与范围

本模块服务县级文物行政主管部门，对“建设项目涉及文物保护”进行全过程电子化管理，覆盖以下主流程：

1. 接收请示
2. 收文登记
3. 现场勘查
4. 勘查意见
5. 上报审批
6. 上级批复
7. 涉文判定
8. 分支流程执行
9. 办结归档

设计目标：

- 非普通 CRUD，采用流程驱动式交互
- 前后端分离，前端可扩展，后端流程可配置
- 同时兼容离线（SQLite）与在线（MySQL）
- 支持后续 AI 文书自动生成能力接入

---

## 2. 总体架构

### 2.1 前端（Vue3 + TS + Pinia + Router + Element Plus）

模块化分层：

- 页面容器：负责三栏布局与状态同步
- 业务组件：每个流程步骤独立组件
- 状态层（Pinia）：项目详情、流程、附件、时间轴、地图状态
- API 层：统一请求封装，按资源域拆分

### 2.2 后端（FastAPI + SQLAlchemy）

- 资源 RESTful 接口 + 流程动作接口
- 流程引擎采用“状态机 + 条件分支 + 可配置流程定义”
- 附件与日志事件统一审计记录
- 数据访问层与业务服务层解耦

### 2.3 数据库（SQLite/MySQL 双兼容）

- 业务表 + 配置表分离
- 核心流程数据以项目为中心（project_id）
- 时间轴由 project_log 聚合

---

## 3. 页面信息架构

## 3.1 项目管理首页（Workflow Dashboard）

页面结构：

- 顶部统计卡片：
  - 项目总数
  - 待勘查
  - 待审批
  - 待回复
  - 已办结
  - 超期项目
- 下方项目列表（卡片+高级表格切换）
  - 项目名称
  - 建设单位
  - 当前位置
  - 当前流程
  - 进度条
  - 办理人员
  - 更新时间
  - 当前状态

交互特征：

- 支持按状态、流程节点、责任人、日期范围筛选
- 支持按超期风险排序
- 点击任一项目进入流程详情页

## 3.2 项目详情（三栏流程页）

布局：

- 左栏：流程导航（步骤态）
  - 已完成：绿色
  - 当前步骤：高亮
  - 未开始：灰色
- 中栏：当前步骤业务内容区
  - 项目信息、附件、地图、照片、意见、文书
- 右栏：时间轴
  - 自动记录所有关键动作和状态变更

顶部信息头：

- 项目名称
- 项目编号
- 状态
- 负责人
- 项目位置
- 项目类型
- 建设单位
- 文号
- 收文日期

---

## 4. 组件拆分方案（前端）

建议目录：

```text
frontend/src/modules/project-workflow/
  api/
    projectApi.ts
    projectFlowApi.ts
    projectAttachmentApi.ts
  stores/
    useProjectWorkflowStore.ts
  views/
    ProjectDashboardView.vue
    ProjectWorkflowDetailView.vue
  components/
    layout/
      WorkflowThreePane.vue
      WorkflowStepNav.vue
      WorkflowTimeline.vue
    header/
      ProjectHeaderBar.vue
      ProjectStatusTag.vue
    steps/
      ReceiveComponent.vue
      SurveyComponent.vue
      ApprovalComponent.vue
      ReplyComponent.vue
      HeritageDecisionComponent.vue
      ArchiveComponent.vue
    blocks/
      AttachmentPanel.vue
      MapPanel.vue
      DocumentActionPanel.vue
      TimelineEventItem.vue
```

步骤组件职责：

- `ReceiveComponent`：收文登记、请示文件上传、基础字段录入
- `SurveyComponent`：勘查人员、日期、GPS、地图、照片、意见
- `ApprovalComponent`：上报材料、审批流转、审批意见
- `ReplyComponent`：上级批复登记、批复文件管理
- `HeritageDecisionComponent`：涉文类型选择与分支触发
- `ArchiveComponent`：办结归档、归档目录生成、文书归档

---

## 5. 涉文判定与分支流程

## 5.1 判定选项

采用单选枚举（可扩展）：

- `NO_HERITAGE`：不涉及文物
- `IMMOVABLE_HERITAGE`：涉及不可移动文物
- `PROTECTION_ZONE`：涉及保护范围
- `CONTROL_ZONE`：涉及建设控制地带
- `UNDERGROUND_HERITAGE`：涉及地下文物
- `NEED_MORE_INVESTIGATION`：需要进一步调查

## 5.2 分支策略

- 不涉及文物：生成复函 -> 办结归档
- 涉及保护范围：专家论证 -> 方案修改 -> 重新审批
- 涉及地下文物：考古调查 -> 考古勘探 -> 审批

## 5.3 流程引擎配置（建议）

采用数据库配置 + JSON DSL：

- `project_flow` 定义流程图
- `project_step` 实例化项目步骤
- `condition_expression` 决定跳转
- `next_step_code` 定义分支走向

示例 DSL：

```json
{
  "flow_code": "default_construction",
  "start": "receive",
  "nodes": [
    {"code": "receive", "next": "survey"},
    {"code": "survey", "next": "approval"},
    {"code": "approval", "next": "reply"},
    {
      "code": "heritage_decision",
      "branches": [
        {"when": "decision == 'NO_HERITAGE'", "to": "reply_generate"},
        {"when": "decision == 'PROTECTION_ZONE'", "to": "expert_review"},
        {"when": "decision == 'UNDERGROUND_HERITAGE'", "to": "archaeology_survey"}
      ]
    }
  ]
}
```

---

## 6. 数据库设计（SQLAlchemy）

## 6.1 表清单（最少）

- `project`
- `project_step`
- `project_attachment`
- `project_log`
- `project_reply`
- `project_survey`
- `project_document`
- `project_flow`
- `project_status`

## 6.2 核心字段建议

### project

- `id` (PK)
- `project_no` (唯一)
- `project_name`
- `project_type`
- `construction_unit`
- `location_text`
- `location_lng`, `location_lat`
- `owner_user_id`
- `status_code`
- `current_step_code`
- `incoming_doc_no`
- `incoming_doc_date`
- `is_overdue`
- `created_at`, `updated_at`

### project_step

- `id` (PK)
- `project_id` (FK)
- `step_code`
- `step_name`
- `step_order`
- `status` (`PENDING/IN_PROGRESS/DONE/SKIPPED`)
- `started_at`, `finished_at`
- `assignee_id`
- `payload_json`

### project_attachment

- `id` (PK)
- `project_id` (FK)
- `step_code`
- `file_type` (`request/survey_photo/cad/pdf/doc/reply/other`)
- `file_name`
- `file_path`
- `file_hash`
- `version_no`
- `uploaded_by`
- `uploaded_at`

### project_log

- `id` (PK)
- `project_id` (FK)
- `event_type`
- `event_title`
- `event_detail`
- `operator_id`
- `operator_name`
- `created_at`

### project_survey

- `id` (PK)
- `project_id` (FK)
- `survey_users`
- `survey_date`
- `gps_lng`, `gps_lat`
- `survey_opinion`
- `map_snapshot_path`

### project_reply

- `id` (PK)
- `project_id` (FK)
- `reply_no`
- `reply_date`
- `reply_result`
- `reply_file_attachment_id`

### project_document

- `id` (PK)
- `project_id` (FK)
- `doc_type` (`survey_opinion/reply/report/archive_catalog/...`)
- `doc_title`
- `content_md`
- `generated_by` (`manual/ai`)
- `generated_at`
- `version_no`

### project_flow

- `id` (PK)
- `flow_code` (唯一)
- `flow_name`
- `version`
- `is_active`
- `definition_json`

### project_status

- `status_code` (PK)
- `status_name`
- `status_color`
- `is_terminal`

---

## 7. 接口设计（RESTful）

## 7.1 项目主接口

- `GET /api/v1/projects`：分页列表（支持筛选）
- `POST /api/v1/projects`：创建项目
- `GET /api/v1/projects/{id}`：项目详情
- `PATCH /api/v1/projects/{id}`：更新项目基本信息

## 7.2 流程接口

- `GET /api/v1/projects/{id}/workflow`：流程节点状态
- `POST /api/v1/projects/{id}/workflow/actions/{action}`：执行步骤动作
- `PATCH /api/v1/projects/{id}/workflow/decision`：涉文判定并触发分支

## 7.3 勘查接口

- `GET /api/v1/projects/{id}/survey`
- `POST /api/v1/projects/{id}/survey`
- `PATCH /api/v1/projects/{id}/survey`

## 7.4 附件接口

- `GET /api/v1/projects/{id}/attachments`
- `POST /api/v1/projects/{id}/attachments`
- `GET /api/v1/projects/{id}/attachments/{attachment_id}/download`
- `GET /api/v1/projects/{id}/attachments/{attachment_id}/preview`
- `GET /api/v1/projects/{id}/attachments/{attachment_id}/versions`

## 7.5 时间轴接口

- `GET /api/v1/projects/{id}/logs`

## 7.6 文书接口

- `POST /api/v1/projects/{id}/documents/generate`
- `GET /api/v1/projects/{id}/documents`
- `GET /api/v1/projects/{id}/documents/{doc_id}`

---

## 8. 地图与空间联动设计

- 项目点位（当前项目）
- 周边文物点（可点击查看详情）
- 保护范围/建控地带图层
- 勘查轨迹/采样点图层（可选）

地图交互：

- 点击文物点 -> 右侧抽屉显示文物详情
- 选择涉文判定时自动标注空间风险提示
- 勘查页支持 GPS 回填到 survey 数据

---

## 9. 时间轴自动记录规则

统一事件模型：

- 收到请示
- 上传请示文件
- 开始现场勘查
- 上传现场照片
- 提交审批
- 收到批复
- 生成文书
- 判定涉文类型
- 办结归档

每个动作接口成功后必须写入 `project_log`，前端时间轴实时刷新。

---

## 10. UI 风格规范

- 参考飞书/钉钉/腾讯文档的轻量工作台风格
- 以 Card + Drawer + Timeline + Steps 为主
- 尽量减少阻断弹窗，优先右侧抽屉编辑
- 状态信息标签化（Tag）
- 首页统计使用 Statistic + 趋势标识

三栏布局建议宽度：

- 左：260px（流程导航）
- 中：自适应（业务主内容）
- 右：320px（时间轴）

---

## 11. 状态与权限建议

角色至少包含：

- 收文人员
- 勘查人员
- 审批专员
- 管理员

权限粒度：

- `project:view`
- `project:create`
- `project:edit`
- `project:survey`
- `project:approve`
- `project:archive`
- `project:document_generate`

---

## 12. 分阶段实施计划（从本设计进入编码）

### Phase 1（本次完成）

- 完成整体页面与架构设计蓝图
- 锁定数据库模型与接口契约

### Phase 2（下一步）

- 先实现项目首页 + 项目详情三栏容器
- 接入流程导航与时间轴 mock 数据

### Phase 3

- 完成 Receive/Survey/Approval/Reply/Archive 组件
- 完成附件上传、地图联动、文书生成按钮入口

### Phase 4

- 接入 FastAPI + SQLAlchemy 真实接口
- 完成分支流程引擎与条件跳转

### Phase 5

- 接入 AI 文书服务
- 性能优化与审计追踪完善

---

## 13. 交付说明

本文件作为“建设项目管理模块升级”的总蓝图。

后续开发将按本文件顺序推进：

1. 三栏容器与首页视觉骨架
2. 步骤组件逐个落地
3. 后端接口与数据库实现
4. 流程引擎与条件分支上线

<template>
  <section class="project-dashboard">
    <header class="page-header">
      <h1>建设项目管理</h1>
      <p>流程驱动工作台：按当前环节、办理风险和办理进度统一管理项目。</p>
    </header>

    <div class="toolbar card">
      <el-input
        v-model="store.filters.keyword"
        placeholder="按项目名/企业名/文号检索"
        clearable
        style="max-width: 320px"
      />
      <el-select v-model="store.filters.status" placeholder="状态筛选" clearable style="width: 220px">
        <el-option label="10_已收文" value="10_已收文" />
        <el-option label="20_初审安全" value="20_初审安全" />
        <el-option label="21_初审涉及" value="21_CHECK_OVERLAP" />
        <el-option label="30_现场勘查完成" value="30_现场勘查完成" />
        <el-option label="40_市局审批中" value="40_市局审批中" />
        <el-option label="45_考古流转中" value="45_考古流转中" />
        <el-option label="50_批复已收到" value="50_批复已收到" />
        <el-option label="60_已结案归档" value="60_已结案归档" />
      </el-select>
      <el-select v-model="store.filters.workflowPath" placeholder="流程分支" clearable style="width: 180px">
        <el-option label="考古流程" value="ARCHAEOLOGY_FLOW" />
        <el-option label="直接复函流程" value="DIRECT_REPLY" />
      </el-select>
      <el-button type="primary" @click="store.loadProjects">查询</el-button>
      <el-button type="success" @click="goCreate">新建项目</el-button>
    </div>

    <div class="stats-row">
      <el-card class="stat-item" shadow="hover" @click="applyStatusFilter('')">
        <el-statistic title="项目总数" :value="summary.total" />
      </el-card>
      <el-card class="stat-item" shadow="hover">
        <el-statistic title="办理中" :value="summary.in_progress" />
      </el-card>
      <el-card class="stat-item stat-item--danger" shadow="hover" @click="applyStatusFilter('10_已收文')">
        <el-statistic title="待初步核查" :value="summary.pending_precheck" />
      </el-card>
      <el-card class="stat-item" shadow="hover">
        <el-statistic title="涉及文物" :value="summary.overlap" />
      </el-card>
      <el-card class="stat-item" shadow="hover" @click="applyStatusFilter('60_已结案归档')">
        <el-statistic title="已办结" :value="summary.archived" />
      </el-card>
      <el-card class="stat-item stat-item--danger" shadow="hover">
        <el-statistic title="超期未办结" :value="overdueCount" />
      </el-card>
    </div>

    <div class="card status-chips">
      <el-tag
        v-for="item in summary.status_counts || []"
        :key="item.status"
        :type="store.filters.status === item.status ? 'primary' : 'info'"
        :effect="store.filters.status === item.status ? 'dark' : 'plain'"
        class="status-chip"
        @click="applyStatusFilter(item.status)"
      >{{ item.label }} ({{ item.count }})</el-tag>
    </div>

    <div class="view-switch card">
      <el-segmented v-model="viewMode" :options="viewOptions" />
      <span class="view-summary">共 {{ store.rows.length }} 个项目</span>
    </div>

    <div v-if="viewMode === 'card'" class="project-card-grid">
      <el-card v-for="row in store.rows" :key="row.id" class="project-card" shadow="hover">
        <div class="project-card-header">
          <h3>{{ row.project_name || '-' }}</h3>
          <el-tag size="small" :type="tagTypeByStatus(row)">{{ currentFlowLabel(row) }}</el-tag>
        </div>

        <div class="project-card-meta">
          <div><span>建设单位</span><strong>{{ row.company_name || '-' }}</strong></div>
          <div><span>当前待办</span><strong>{{ todoHint(row) }}</strong></div>
          <div><span>核验时间</span><strong>{{ row.spatial_check_at || '尚未核验' }}</strong></div>
          <div><span>更新时间</span><strong>{{ row.updated_at || row.receive_date || '-' }}</strong></div>
        </div>

        <div class="project-card-progress">
          <div class="progress-row">
            <span>办理进度</span>
            <strong>{{ progressByStatus(row) }}%</strong>
          </div>
          <el-progress :percentage="progressByStatus(row)" :stroke-width="10" :show-text="false" />
        </div>

        <div class="project-card-footer">
          <el-tag :type="row.is_overlap_artifact ? 'danger' : 'success'" effect="plain">
            {{ row.is_overlap_artifact ? `涉及文物 ${row.overlap_count}处` : '不涉及文物' }}
          </el-tag>
          <el-tag :type="row.workflow_path === 'ARCHAEOLOGY_FLOW' ? 'warning' : 'info'" effect="plain">
            {{ row.workflow_path === 'ARCHAEOLOGY_FLOW' ? '考古流程' : '直接复函流程' }}
          </el-tag>
          <el-button link type="primary" @click="goDetail(row.id)">进入详情</el-button>
        </div>
      </el-card>
    </div>

    <div class="card" v-else>
      <el-table :data="store.rows" v-loading="store.loading" stripe>
        <el-table-column prop="project_name" label="项目名称" min-width="220" />
        <el-table-column prop="company_name" label="企业单位" min-width="180" />
        <el-table-column label="当前流程" min-width="180">
          <template #default="scope">
            <el-tag size="small" :type="tagTypeByStatus(scope.row)">{{ currentFlowLabel(scope.row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="180">
          <template #default="scope">
            <el-progress :percentage="progressByStatus(scope.row)" :stroke-width="8" :show-text="false" />
          </template>
        </el-table-column>
        <el-table-column prop="receive_date" label="收文日期" width="130" />
        <el-table-column label="当前待办" min-width="170">
          <template #default="scope">
            <span :class="{ 'todo-warn': !scope.row.spatial_check_at && !scope.row.is_archived }">
              {{ todoHint(scope.row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="涉及文物" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.is_overlap_artifact ? 'danger' : 'success'">
              {{ scope.row.is_overlap_artifact ? `是 (${scope.row.overlap_count})` : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="流程分支" min-width="150">
          <template #default="scope">
            <el-tag :type="scope.row.workflow_path === 'ARCHAEOLOGY_FLOW' ? 'warning' : 'info'" effect="plain">
              {{ scope.row.workflow_path === 'ARCHAEOLOGY_FLOW' ? '考古流程' : '直接复函流程' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button link type="primary" @click="goDetail(scope.row.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useProjectStore } from '../../stores/projectStore'

const store = useProjectStore()
const router = useRouter()
const viewMode = ref('card')
const viewOptions = [
  { label: '卡片视图', value: 'card' },
  { label: '表格视图', value: 'table' },
]

function statusRaw(row) {
  return String(row.status || row.status_label || '').trim()
}

function progressByStatus(row) {
  const status = statusRaw(row)
  if (status.includes('60_') || status.includes('已结案归档')) return 100
  if (status.includes('50_') || status.includes('批复已收到')) return 88
  if (status.includes('45_') || status.includes('考古流转中')) return 70
  if (status.includes('40_') || status.includes('审批中')) return 60
  if (status.includes('30_') || status.includes('现场勘查完成')) return 45
  if (status.includes('21_') || status.includes('初审涉及')) return 35
  if (status.includes('20_') || status.includes('初审安全')) return 30
  return 15
}

const STEP_LABELS = {
  receive: '收文登记',
  precheck: '初步核查',
  field_check: '联合实地勘查',
  city_review: '上报市局与回复意见',
  archaeology: '专项保护与逐级报审',
  reply: '出具复函',
  archive: '办结归档'
}

function currentFlowLabel(row) {
  return STEP_LABELS[row.current_step] || '收文登记'
}

function todoHint(row) {
  if (row.is_archived) return '已办结'
  if (!row.spatial_check_at) return '待执行叠加核验'
  if (row.has_high_level_overlap) return '高等级文物，建议避让'
  return currentFlowLabel(row)
}

function tagTypeByStatus(row) {
  const status = statusRaw(row)
  if (status.includes('60_')) return 'success'
  if (status.includes('45_') || status.includes('21_')) return 'warning'
  if (status.includes('50_')) return ''
  return 'info'
}

function isOverdue(row) {
  const status = statusRaw(row)
  if (status.includes('60_')) return false
  const dateText = row.receive_date || row.created_at
  if (!dateText) return false
  const start = new Date(dateText)
  if (Number.isNaN(start.getTime())) return false
  const diffDays = (Date.now() - start.getTime()) / (1000 * 60 * 60 * 24)
  return diffDays > 30
}

const summary = computed(() => store.summary || {})

const overdueCount = computed(() => (store.rows || []).filter((row) => isOverdue(row)).length)

function applyStatusFilter(status) {
  store.filters.status = store.filters.status === status ? '' : status
  store.loadProjects()
}

function goCreate() {
  router.push('/projects/new')
}

function goDetail(projectId) {
  router.push(`/projects/${projectId}`)
}

onMounted(() => {
  store.loadProjects()
})
</script>

<style scoped>
.project-dashboard {
  display: grid;
  gap: 14px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.stat-item--danger :deep(.el-statistic__content-value) {
  color: #c81e1e;
}

.stat-item {
  cursor: pointer;
}

.status-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.status-chip {
  cursor: pointer;
}

.todo-warn {
  color: #c81e1e;
  font-weight: 600;
}

.view-switch {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.view-summary {
  color: #64748b;
  font-size: 13px;
}

.project-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.project-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.project-card-header h3 {
  margin: 0;
  font-size: 16px;
}

.project-card-meta {
  margin-top: 12px;
  display: grid;
  gap: 8px;
}

.project-card-meta div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
}

.project-card-meta span {
  color: #64748b;
}

.project-card-progress {
  margin-top: 14px;
}

.progress-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
}

.project-card-footer {
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

@media (max-width: 1300px) {
  .stats-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .project-card-grid {
    grid-template-columns: 1fr;
  }

  .stats-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

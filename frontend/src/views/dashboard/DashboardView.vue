<template>
  <section>
    <header class="page-header">
      <h1>综合看板</h1>
      <p>面向审批、巡查、文保风险和地图联动的统一首页</p>
    </header>

    <div class="stats-grid">
      <StatCard title="待审批项目" :value="overview.pending_project_count" />
      <StatCard title="今日巡查" :value="overview.today_inspection_count" />
      <StatCard title="文保点总数" :value="overview.heritage_total_count" />
      <StatCard title="风险预警" :value="overview.risk_warning_count" />
      <StatCard title="巡查总数" :value="inspectionStats.total_count" />
      <StatCard title="巡查异常率" :value="inspectionRateText" />
    </div>

    <div class="dashboard-grid dashboard-grid-rich">
      <div class="dashboard-left-col">
        <div class="card">
          <div class="card-header-row">
            <h3>文物等级分布</h3>
            <span class="muted-text">实时统计</span>
          </div>
          <div ref="levelChartEl" class="dashboard-chart"></div>
        </div>

        <div class="card">
          <div class="card-header-row">
            <h3>巡查健康度</h3>
            <span class="muted-text">系统版本 {{ versionText }}</span>
          </div>
          <div ref="inspectionChartEl" class="dashboard-chart"></div>
        </div>

        <div class="card">
          <div class="card-header-row">
            <h3>文物类别 TOP 8</h3>
            <span class="muted-text">按数量降序</span>
          </div>
          <el-table :data="categoryTopRows" stripe size="small" max-height="280">
            <el-table-column prop="label" label="类别" min-width="180" />
            <el-table-column prop="count" label="数量" width="90" />
            <el-table-column prop="ratio" label="占比" width="100" />
          </el-table>
        </div>
      </div>

      <div class="card tall">
        <div class="card-header-row">
          <h3>文物一张图</h3>
          <span class="muted-text">点选查看文物档案入口</span>
        </div>

        <div class="map-toolbar-row">
          <el-input v-model="mapKeyword" placeholder="按文物名称筛选" clearable />
          <el-checkbox-group v-model="mapActiveLevels" class="map-level-group">
            <el-checkbox label="GB">国保</el-checkbox>
            <el-checkbox label="SB">区保</el-checkbox>
            <el-checkbox label="XB">县保</el-checkbox>
            <el-checkbox label="DS">未定级</el-checkbox>
          </el-checkbox-group>
        </div>

        <HeritageMapCanvas
          class="dashboard-heritage-map"
          :points="mapPoints"
          :active-levels="mapActiveLevels"
          :keyword="mapKeyword"
          @select="onSelectSite"
        />

        <div class="selected-site-box">
          <div class="selected-site-title">当前选中</div>
          <div class="selected-site-content">
            <span>名称：{{ selectedSite.name || '-' }}</span>
            <span>等级：{{ selectedSite.level_label || '-' }}</span>
            <span>坐标：{{ selectedSite.lng ?? '-' }}, {{ selectedSite.lat ?? '-' }}</span>
          </div>
          <el-button type="primary" link :disabled="!selectedSite.id" @click="openSiteDetail">查看档案详情</el-button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import * as echarts from 'echarts'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { fetchDashboardOverview, fetchSystemVersion } from '../../api/dashboardApi'
import { fetchHeritageClassificationStats, fetchHeritageMapPoints } from '../../api/heritageApi'
import { fetchInspectionStats } from '../../api/inspectionApi'
import HeritageMapCanvas from '../../components/heritage/HeritageMapCanvas.vue'
import StatCard from '../../components/StatCard.vue'

const router = useRouter()

const versionText = ref('-')
const overview = ref({
  pending_project_count: '-',
  today_inspection_count: '-',
  heritage_total_count: '-',
  risk_warning_count: '-'
})

const inspectionStats = reactive({
  total_count: '-',
  today_count: '-',
  abnormal_count: '-'
})

const levelLabels = ref([])
const levelValues = ref([])
const categoryRows = ref([])
const mapPoints = ref([])
const mapKeyword = ref('')
const mapActiveLevels = ref(['GB', 'SB', 'XB', 'DS'])
const selectedSite = reactive({})

const levelChartEl = ref(null)
const inspectionChartEl = ref(null)
let levelChartRef = null
let inspectionChartRef = null

const inspectionRateText = computed(() => {
  const total = Number(inspectionStats.total_count)
  const abnormal = Number(inspectionStats.abnormal_count)
  if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(abnormal)) {
    return '-'
  }
  return `${((abnormal / total) * 100).toFixed(1)}%`
})

const categoryTopRows = computed(() => categoryRows.value.slice(0, 8))

function toRows(labels = [], values = []) {
  const total = values.reduce((sum, item) => sum + Number(item || 0), 0)
  return labels.map((label, index) => {
    const count = Number(values[index] || 0)
    const ratio = total > 0 ? `${((count / total) * 100).toFixed(1)}%` : '0.0%'
    return {
      label,
      count,
      ratio
    }
  })
}

function renderLevelChart() {
  if (!levelChartRef) {
    return
  }
  levelChartRef.setOption({
    color: ['#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
    tooltip: { trigger: 'item' },
    legend: {
      bottom: 0,
      icon: 'circle'
    },
    series: [
      {
        name: '文物等级',
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        label: {
          formatter: '{b}: {c}'
        },
        data: levelLabels.value.map((label, index) => ({
          name: label,
          value: Number(levelValues.value[index] || 0)
        }))
      }
    ]
  })
}

function renderInspectionChart() {
  if (!inspectionChartRef) {
    return
  }
  const total = Number(inspectionStats.total_count) || 0
  const abnormal = Number(inspectionStats.abnormal_count) || 0
  const normal = Math.max(0, total - abnormal)

  inspectionChartRef.setOption({
    color: ['#22c55e', '#ef4444'],
    tooltip: { trigger: 'item' },
    series: [
      {
        name: '巡查健康度',
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['30%', '48%'],
        label: {
          formatter: '{b}\n{c}'
        },
        data: [
          { name: '正常巡查', value: normal },
          { name: '异常巡查', value: abnormal }
        ]
      }
    ],
    graphic: [
      {
        type: 'text',
        right: 24,
        top: '20%',
        style: {
          text: [
            `今日巡查: ${inspectionStats.today_count}`,
            `累计巡查: ${inspectionStats.total_count}`,
            `异常巡查: ${inspectionStats.abnormal_count}`,
            `异常率: ${inspectionRateText.value}`
          ].join('\n'),
          fill: '#334155',
          fontSize: 13,
          lineHeight: 24,
          fontWeight: 600
        }
      }
    ]
  })
}

function onSelectSite(payload) {
  Object.keys(selectedSite).forEach((key) => delete selectedSite[key])
  Object.keys(payload || {}).forEach((key) => {
    selectedSite[key] = payload[key]
  })
}

function openSiteDetail() {
  if (!selectedSite.id) {
    return
  }
  router.push(`/heritage/${selectedSite.id}`)
}

function resizeCharts() {
  if (levelChartRef) {
    levelChartRef.resize()
  }
  if (inspectionChartRef) {
    inspectionChartRef.resize()
  }
}

async function loadDashboardData() {
  try {
    const [dashboardRes, versionRes, inspectionRes, levelStatsRes, categoryStatsRes, mapPointsRes] = await Promise.all([
      fetchDashboardOverview(),
      fetchSystemVersion(),
      fetchInspectionStats(),
      fetchHeritageClassificationStats({ group_by: 'level', kanerjing_scope: 'all' }),
      fetchHeritageClassificationStats({ group_by: 'category', kanerjing_scope: 'all' }),
      fetchHeritageMapPoints()
    ])

    if (dashboardRes?.success && dashboardRes?.data) {
      overview.value = {
        ...overview.value,
        ...dashboardRes.data
      }
    }

    versionText.value = versionRes?.data?.version || '-'

    if (inspectionRes?.success && inspectionRes?.data) {
      inspectionStats.total_count = inspectionRes.data.total_count
      inspectionStats.today_count = inspectionRes.data.today_count
      inspectionStats.abnormal_count = inspectionRes.data.abnormal_count
    }

    if (levelStatsRes?.success) {
      levelLabels.value = levelStatsRes.labels || []
      levelValues.value = levelStatsRes.data || []
    }

    if (categoryStatsRes?.success) {
      categoryRows.value = toRows(categoryStatsRes.labels || [], categoryStatsRes.data || []).sort(
        (a, b) => b.count - a.count
      )
    }

    if (mapPointsRes?.success) {
      mapPoints.value = mapPointsRes.rows || []
    }
  } catch (error) {
    ElMessage.error(error?.message || '综合看板数据加载失败')
  }
}

onMounted(async () => {
  await loadDashboardData()

  levelChartRef = echarts.init(levelChartEl.value)
  inspectionChartRef = echarts.init(inspectionChartEl.value)
  renderLevelChart()
  renderInspectionChart()
  window.addEventListener('resize', resizeCharts)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCharts)
  if (levelChartRef) {
    levelChartRef.dispose()
    levelChartRef = null
  }
  if (inspectionChartRef) {
    inspectionChartRef.dispose()
    inspectionChartRef = null
  }
})

watch(
  () => [levelLabels.value, levelValues.value],
  () => renderLevelChart(),
  { deep: true }
)

watch(
  () => [inspectionStats.total_count, inspectionStats.today_count, inspectionStats.abnormal_count],
  () => renderInspectionChart(),
  { deep: true }
)
</script>

<style scoped>
.dashboard-grid-rich {
  grid-template-columns: 1.1fr 1.35fr;
  align-items: start;
}

.dashboard-left-col {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.card-header-row h3 {
  margin: 0;
}

.muted-text {
  color: #64748b;
  font-size: 12px;
}

.dashboard-chart {
  height: 280px;
}

.map-toolbar-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.map-level-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.dashboard-heritage-map {
  height: 470px;
  border-radius: 10px;
  overflow: hidden;
}

.selected-site-box {
  margin-top: 10px;
  border: 1px solid #dbe5ef;
  background: #f8fafc;
  border-radius: 10px;
  padding: 10px 12px;
}

.selected-site-title {
  color: #0f172a;
  font-weight: 600;
  font-size: 13px;
}

.selected-site-content {
  margin-top: 6px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 4px;
  color: #334155;
  font-size: 12px;
}

@media (max-width: 1024px) {
  .dashboard-grid-rich {
    grid-template-columns: 1fr;
  }

  .dashboard-chart {
    height: 260px;
  }

  .map-toolbar-row {
    grid-template-columns: 1fr;
  }

  .dashboard-heritage-map {
    height: 420px;
  }
}
</style>

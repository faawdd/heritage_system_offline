<template>
  <section class="dashboard-page">
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
        <div class="left-chart-grid">
          <div class="card compact-card">
            <div class="card-header-row">
              <h3>{{ levelChartTitle }}</h3>
              <span class="muted-text">字段 {{ levelGroupField }}</span>
            </div>
            <div ref="levelChartEl" class="dashboard-chart"></div>
          </div>

          <div class="card compact-card">
            <div class="card-header-row">
              <h3>巡查健康度</h3>
              <span class="muted-text">系统版本 {{ versionText }}</span>
            </div>
            <div ref="inspectionChartEl" class="dashboard-chart"></div>
          </div>

          <div class="card compact-card">
            <div class="card-header-row">
              <h3>近7天巡查趋势</h3>
              <span class="muted-text">总巡查 vs 异常巡查</span>
            </div>
            <div ref="trendChartEl" class="dashboard-chart"></div>
          </div>

          <div class="card compact-card">
            <div class="card-header-row">
              <h3>项目审批漏斗</h3>
              <span class="muted-text">各审批阶段数量</span>
            </div>
            <div ref="funnelChartEl" class="dashboard-chart"></div>
          </div>
        </div>

        <div class="card compact-card category-card">
          <div class="card-header-row">
            <h3>文物类别 TOP 8</h3>
            <span class="muted-text">按数量降序</span>
          </div>
          <el-table :data="categoryTopRows" stripe size="small" max-height="160">
            <el-table-column prop="label" label="类别" min-width="180" />
            <el-table-column prop="count" label="数量" width="90" />
            <el-table-column prop="ratio" label="占比" width="100" />
          </el-table>
        </div>
      </div>

      <div class="card map-card">
        <div class="card-header-row">
          <h3>文物一张图</h3>
          <span class="muted-text">点选查看文物档案入口</span>
        </div>

        <div class="map-toolbar-row">
          <el-input v-model="mapKeyword" placeholder="按文物名称筛选" clearable />
          <div class="map-filter-col">
            <el-checkbox-group v-model="mapActiveLevels" class="map-level-group">
              <el-checkbox label="GB">国保</el-checkbox>
              <el-checkbox label="SB">区保</el-checkbox>
              <el-checkbox label="XB">县保</el-checkbox>
              <el-checkbox label="DS">未定级</el-checkbox>
            </el-checkbox-group>
            <el-switch v-model="showAbnormalHeat" active-text="异常巡查热力" inactive-text="关闭热力" />
          </div>
        </div>

        <HeritageMapCanvas
          class="dashboard-heritage-map"
          :points="mapPoints"
          :abnormal-points="abnormalInspectionPoints"
          :show-abnormal-heat="showAbnormalHeat"
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
const showAbnormalHeat = ref(true)
const inspectionTrendRows = ref([])
const projectFunnelRows = ref([])
const abnormalInspectionPoints = ref([])
const selectedSite = reactive({})

const levelChartEl = ref(null)
const inspectionChartEl = ref(null)
const trendChartEl = ref(null)
const funnelChartEl = ref(null)
let levelChartRef = null
let inspectionChartRef = null
let trendChartRef = null
let funnelChartRef = null

const inspectionRateText = computed(() => {
  const total = Number(inspectionStats.total_count)
  const abnormal = Number(inspectionStats.abnormal_count)
  if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(abnormal)) {
    return '-'
  }
  return `${((abnormal / total) * 100).toFixed(1)}%`
})

const categoryTopRows = computed(() => categoryRows.value.slice(0, 8))

const levelChartTitle = computed(() => {
  if (levelGroupField.value === 'protection_level') {
    return '文物保护级别分布'
  }
  return '文物等级分布'
})

const levelGroupField = ref('level')

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

function renderTrendChart() {
  if (!trendChartRef) {
    return
  }

  const labels = inspectionTrendRows.value.map((item) => item.label)
  const totalSeries = inspectionTrendRows.value.map((item) => Number(item.total_count || 0))
  const abnormalSeries = inspectionTrendRows.value.map((item) => Number(item.abnormal_count || 0))

  trendChartRef.setOption({
    color: ['#0ea5e9', '#ef4444'],
    tooltip: { trigger: 'axis' },
    legend: { top: 4 },
    grid: { left: 36, right: 18, top: 42, bottom: 28 },
    xAxis: {
      type: 'category',
      data: labels
    },
    yAxis: {
      type: 'value',
      minInterval: 1
    },
    series: [
      {
        name: '总巡查',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: totalSeries
      },
      {
        name: '异常巡查',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: abnormalSeries
      }
    ]
  })
}

function renderFunnelChart() {
  if (!funnelChartRef) {
    return
  }
  const rows = (projectFunnelRows.value || [])
    .filter((item) => Number(item.count || 0) >= 0)
    .map((item) => ({
      name: item.label,
      value: Number(item.count || 0)
    }))

  funnelChartRef.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}' },
    color: ['#0ea5e9', '#10b981', '#f59e0b', '#fb7185', '#8b5cf6', '#14b8a6', '#64748b', '#334155'],
    series: [
      {
        name: '审批漏斗',
        type: 'funnel',
        left: '6%',
        top: 10,
        bottom: 10,
        width: '88%',
        min: 0,
        max: Math.max(...rows.map((item) => item.value), 10),
        minSize: '18%',
        maxSize: '100%',
        sort: 'descending',
        gap: 4,
        label: {
          show: true,
          position: 'inside',
          formatter: '{b}: {c}'
        },
        itemStyle: {
          borderColor: '#ffffff',
          borderWidth: 1
        },
        data: rows
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
  if (trendChartRef) {
    trendChartRef.resize()
  }
  if (funnelChartRef) {
    funnelChartRef.resize()
  }
}

async function loadDashboardData() {
  try {
    const [dashboardRes, versionRes, inspectionRes, levelStatsRes, categoryStatsRes, mapPointsRes] = await Promise.all([
      fetchDashboardOverview(),
      fetchSystemVersion(),
      fetchInspectionStats(),
      fetchHeritageClassificationStats({ group_by: 'level', source: 'legacy', kanerjing_scope: 'all' }),
      fetchHeritageClassificationStats({ group_by: 'category', source: 'legacy', kanerjing_scope: 'all' }),
      fetchHeritageMapPoints()
    ])

    if (dashboardRes?.success && dashboardRes?.data) {
      overview.value = {
        ...overview.value,
        ...dashboardRes.data
      }
      inspectionTrendRows.value = dashboardRes.data.inspection_trend_7d || []
      projectFunnelRows.value = dashboardRes.data.project_funnel || []
      abnormalInspectionPoints.value = dashboardRes.data.abnormal_inspection_points || []
    }

    versionText.value = versionRes?.data?.version || '-'

    if (inspectionRes?.success && inspectionRes?.data) {
      inspectionStats.total_count = inspectionRes.data.total_count
      inspectionStats.today_count = inspectionRes.data.today_count
      inspectionStats.abnormal_count = inspectionRes.data.abnormal_count
    }

    if (levelStatsRes && typeof levelStatsRes === 'object') {
      levelGroupField.value = levelStatsRes.group_by_field || 'level'
      if (Array.isArray(levelStatsRes.rows) && levelStatsRes.rows.length > 0) {
        levelLabels.value = levelStatsRes.rows.map((item) => item.label)
        levelValues.value = levelStatsRes.rows.map((item) => Number(item.count || 0))
      } else {
        levelLabels.value = levelStatsRes.labels || []
        levelValues.value = levelStatsRes.data || []
      }
    }

    if (categoryStatsRes && typeof categoryStatsRes === 'object') {
      if (Array.isArray(categoryStatsRes.rows) && categoryStatsRes.rows.length > 0) {
        const total = categoryStatsRes.rows.reduce((sum, item) => sum + Number(item.count || 0), 0)
        categoryRows.value = categoryStatsRes.rows
          .map((item) => {
            const count = Number(item.count || 0)
            return {
              label: item.label,
              count,
              ratio: total > 0 ? `${((count / total) * 100).toFixed(1)}%` : '0.0%'
            }
          })
          .sort((a, b) => b.count - a.count)
      } else {
        categoryRows.value = toRows(categoryStatsRes.labels || [], categoryStatsRes.data || []).sort(
          (a, b) => b.count - a.count
        )
      }
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
  trendChartRef = echarts.init(trendChartEl.value)
  funnelChartRef = echarts.init(funnelChartEl.value)
  renderLevelChart()
  renderInspectionChart()
  renderTrendChart()
  renderFunnelChart()
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
  if (trendChartRef) {
    trendChartRef.dispose()
    trendChartRef = null
  }
  if (funnelChartRef) {
    funnelChartRef.dispose()
    funnelChartRef = null
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

watch(
  () => inspectionTrendRows.value,
  () => renderTrendChart(),
  { deep: true }
)

watch(
  () => projectFunnelRows.value,
  () => renderFunnelChart(),
  { deep: true }
)
</script>

<style scoped>
.dashboard-page {
  height: calc(100vh - 48px);
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 10px;
  overflow: hidden;
}

.page-header p {
  margin-top: 4px;
}

.stats-grid {
  margin-top: 0;
  gap: 10px;
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.stats-grid :deep(.stat-card) {
  padding: 10px 12px;
  min-height: 74px;
}

.stats-grid :deep(.stat-title) {
  font-size: 12px;
}

.stats-grid :deep(.stat-value) {
  margin-top: 4px;
  font-size: 22px;
}

.dashboard-grid-rich {
  margin-top: 0;
  grid-template-columns: 1.15fr 1.35fr;
  align-items: stretch;
  min-height: 0;
}

.dashboard-left-col {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 10px;
  min-height: 0;
}

.left-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  min-height: 0;
}

.compact-card {
  padding: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.category-card {
  max-height: 236px;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.card-header-row h3 {
  margin: 0;
  font-size: 15px;
}

.muted-text {
  color: #64748b;
  font-size: 12px;
}

.dashboard-chart {
  height: 190px;
  min-height: 0;
}

.map-card {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.map-toolbar-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.map-filter-col {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.map-level-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.dashboard-heritage-map {
  flex: 1;
  min-height: 250px;
  border-radius: 10px;
  overflow: hidden;
}

.selected-site-box {
  margin-top: 8px;
  border: 1px solid #dbe5ef;
  background: #f8fafc;
  border-radius: 10px;
  padding: 8px 10px;
}

.selected-site-title {
  color: #0f172a;
  font-weight: 600;
  font-size: 13px;
}

.selected-site-content {
  margin-top: 4px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 2px;
  color: #334155;
  font-size: 12px;
}

@media (max-width: 1440px) {
  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .dashboard-chart {
    height: 180px;
  }
}

@media (max-width: 1024px) {
  .dashboard-page {
    height: auto;
    overflow: visible;
  }

  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid-rich {
    grid-template-columns: 1fr;
  }

  .left-chart-grid {
    grid-template-columns: 1fr;
  }

  .category-card {
    max-height: none;
  }

  .dashboard-chart {
    height: 260px;
  }

  .map-toolbar-row {
    grid-template-columns: 1fr;
  }

  .map-filter-col {
    width: 100%;
  }

  .dashboard-heritage-map {
    height: 420px;
    min-height: 420px;
    flex: none;
  }
}
</style>

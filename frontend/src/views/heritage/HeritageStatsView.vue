<template>
  <section>
    <header class="page-header">
      <h1>文物分类统计面板</h1>
      <p>多维筛选与统计图表联动</p>
    </header>

    <div class="card">
      <el-form :inline="true" class="stats-filter-form">
        <el-form-item label="统计维度">
          <el-select v-model="filters.group_by" style="width: 180px" @change="loadStats">
            <el-option label="按文物类别" value="category" />
            <el-option label="按保护等级" value="level" />
            <el-option label="按地址乡镇" value="township" />
          </el-select>
        </el-form-item>
        <el-form-item label="坎儿井范围">
          <el-select v-model="filters.kanerjing_scope" style="width: 180px" @change="loadStats">
            <el-option label="包含坎儿井" value="all" />
            <el-option label="只显示坎儿井" value="only" />
            <el-option label="不包含坎儿井" value="exclude" />
          </el-select>
        </el-form-item>
        <el-form-item label="文物类别">
          <el-select v-model="filters.category" style="width: 180px" clearable @change="loadStats">
            <el-option v-for="item in meta.category_choices" :key="item[0]" :label="item[1]" :value="item[0]" />
          </el-select>
        </el-form-item>
        <el-form-item label="保护等级">
          <el-select v-model="filters.level" style="width: 180px" clearable @change="loadStats">
            <el-option v-for="item in meta.level_choices" :key="item[0]" :label="item[1]" :value="item[0]" />
          </el-select>
        </el-form-item>
        <el-form-item label="地址乡镇">
          <el-select v-model="filters.township" style="width: 180px" clearable @change="loadStats">
            <el-option v-for="item in meta.township_options" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="地址关键词">
          <el-input v-model="filters.address_keyword" placeholder="如：鲁克沁" @change="loadStats" />
        </el-form-item>
      </el-form>
    </div>

    <div class="stats-grid top-space">
      <div class="stat-card">
        <p class="stat-title">筛选后文物点总数</p>
        <p class="stat-value">{{ total }}</p>
      </div>
    </div>

    <div class="dashboard-grid top-space">
      <div class="card">
        <h3>统计图表</h3>
        <HeritageStatsChart :labels="labels" :values="values" @select="selectChartItem" />
      </div>
      <div class="card">
        <h3>统计明细</h3>
        <el-table :data="rows" stripe highlight-current-row @row-click="selectRow">
          <el-table-column prop="label" label="分类" min-width="200" />
          <el-table-column prop="count" label="数量" width="100" />
          <el-table-column prop="ratio" label="占比" width="100" />
        </el-table>
      </div>
    </div>

    <div v-if="selectedRow" class="card top-space">
      <div class="detail-header">
        <div>
          <h3>{{ selectedRow.label }}明细</h3>
          <p>共 {{ detailRows.length }} 个文物点</p>
        </div>
        <el-button type="primary" :loading="exporting" @click="exportDetail">导出此分类文物列表</el-button>
      </div>
      <el-table :data="detailRows" v-loading="detailLoading" stripe max-height="420">
        <el-table-column prop="name" label="文物名称" min-width="180" />
        <el-table-column prop="sip_code" label="编号" width="150" />
        <el-table-column prop="category_label" label="文物类别" width="180" />
        <el-table-column prop="level_label" label="保护级别" width="180" />
        <el-table-column prop="township" label="乡镇" width="120" />
        <el-table-column prop="address" label="详细地址" min-width="220" />
        <el-table-column prop="manager" label="管理单位/负责人" width="180" />
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  fetchHeritageClassificationStats,
  fetchHeritageClassificationDetail,
  exportHeritageClassificationDetail,
  fetchHeritageStatsMeta
} from '../../api/heritageApi'
import HeritageStatsChart from '../../components/heritage/HeritageStatsChart.vue'

const meta = reactive({
  category_choices: [],
  level_choices: [],
  township_options: []
})

const filters = reactive({
  group_by: 'category',
  kanerjing_scope: 'all',
  category: '',
  level: '',
  township: '',
  address_keyword: ''
})

const labels = ref([])
const values = ref([])
const total = ref(0)
const rows = ref([])
const selectedRow = ref(null)
const detailRows = ref([])
const detailLoading = ref(false)
const exporting = ref(false)

function fillReactive(target, source) {
  Object.keys(target).forEach((key) => {
    target[key] = source?.[key] ?? target[key]
  })
}

async function loadMeta() {
  const result = await fetchHeritageStatsMeta()
  if (!result.success) {
    throw new Error(result.message || '加载筛选元数据失败')
  }
  fillReactive(meta, result.data || {})
}

async function loadStats() {
  try {
    const result = await fetchHeritageClassificationStats(filters)
    labels.value = result.labels || []
    values.value = result.data || []
    total.value = result.total || 0
    rows.value = labels.value.map((label, index) => {
      const count = values.value[index] || 0
      const ratio = total.value > 0 ? `${((count / total.value) * 100).toFixed(1)}%` : '0.0%'
      return { value: result.rows?.[index]?.value ?? '', label, count, ratio }
    })
    selectedRow.value = null
    detailRows.value = []
  } catch (error) {
    ElMessage.error(error?.message || '加载统计数据失败')
  }
}

function segmentParams() {
  return {
    ...filters,
    group_value: selectedRow.value?.value ?? ''
  }
}

async function selectRow(row) {
  if (!row) return
  selectedRow.value = row
  detailLoading.value = true
  try {
    const result = await fetchHeritageClassificationDetail(segmentParams())
    detailRows.value = result.rows || []
  } catch (error) {
    detailRows.value = []
    ElMessage.error(error?.message || '加载分类明细失败')
  } finally {
    detailLoading.value = false
  }
}

function selectChartItem(index) {
  if (rows.value[index]) selectRow(rows.value[index])
}

function downloadBlob(response, fallbackName) {
  const disposition = response.headers?.['content-disposition'] || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  const filename = match ? decodeURIComponent(match[1]) : fallbackName
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

async function exportDetail() {
  if (!selectedRow.value) return
  exporting.value = true
  try {
    const response = await exportHeritageClassificationDetail(segmentParams())
    downloadBlob(response, `${selectedRow.value.label}-文物统计.csv`)
  } catch (error) {
    ElMessage.error(error?.message || '导出分类文物列表失败')
  } finally {
    exporting.value = false
  }
}

async function bootstrap() {
  try {
    await loadMeta()
    await loadStats()
  } catch (error) {
    ElMessage.error(error?.message || '初始化失败')
  }
}

bootstrap()
</script>

<style scoped>
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
}
.detail-header h3,
.detail-header p {
  margin: 0;
}
.detail-header p {
  margin-top: 0.25rem;
  color: var(--el-text-color-secondary);
}
</style>

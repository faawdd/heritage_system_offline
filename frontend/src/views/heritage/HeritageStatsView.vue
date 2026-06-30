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
        <HeritageStatsChart :labels="labels" :values="values" />
      </div>
      <div class="card">
        <h3>统计明细</h3>
        <el-table :data="rows" stripe>
          <el-table-column prop="label" label="分类" min-width="200" />
          <el-table-column prop="count" label="数量" width="100" />
          <el-table-column prop="ratio" label="占比" width="100" />
        </el-table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  fetchHeritageClassificationStats,
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
      return { label, count, ratio }
    })
  } catch (error) {
    ElMessage.error(error?.message || '加载统计数据失败')
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

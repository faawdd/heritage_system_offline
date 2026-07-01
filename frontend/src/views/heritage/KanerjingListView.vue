<template>
  <section>
    <header class="page-header">
      <h1>坎儿井专项管理</h1>
      <p>按名称和类别自动识别坎儿井文物点，支持检索与等级筛选</p>
    </header>

    <div class="stats-grid top-space">
      <div class="stat-card">
        <p class="stat-title">筛选后总数</p>
        <p class="stat-value">{{ totalCount }}</p>
      </div>
      <div v-for="item in levelStats" :key="item.value" class="stat-card">
        <p class="stat-title">{{ item.label }}</p>
        <p class="stat-value">{{ item.count }}</p>
      </div>
    </div>

    <div class="toolbar card top-space">
      <el-input
        v-model="filters.keyword"
        placeholder="按名称/编号/地址/责任人检索"
        clearable
        style="max-width: 360px"
      />
      <el-select v-model="filters.level" clearable placeholder="保护等级" style="width: 220px">
        <el-option v-for="item in levelOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button type="primary" :loading="loading" @click="search">查询</el-button>
    </div>

    <div class="card top-space">
      <el-table :data="rows" stripe v-loading="loading">
        <el-table-column prop="name" label="文物名称" min-width="180" />
        <el-table-column prop="sip_code" label="四普编号" width="140" />
        <el-table-column prop="level_label" label="保护等级" width="180" />
        <el-table-column prop="address" label="详细地址" min-width="220" show-overflow-tooltip />
        <el-table-column prop="manager" label="管理责任人" width="140" />
        <el-table-column label="坐标" width="170">
          <template #default="scope">
            {{ scope.row.longitude }}, {{ scope.row.latitude }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="现状描述" min-width="220" show-overflow-tooltip />
      </el-table>

      <div class="top-space" style="display: flex; justify-content: flex-end">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="pagination.total"
          :page-size="pagination.page_size"
          :current-page="pagination.page"
          @current-change="onPageChange"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchKanerjingList } from '../../api/heritageApi'

const loading = ref(false)
const rows = ref([])
const totalCount = ref(0)
const levelOptions = ref([])
const levelStats = ref([])

const filters = reactive({
  keyword: '',
  level: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

function buildParams() {
  return {
    page: pagination.page,
    page_size: pagination.page_size,
    keyword: filters.keyword,
    level: filters.level
  }
}

async function loadRows() {
  loading.value = true
  try {
    const result = await fetchKanerjingList(buildParams())
    if (!result.success) {
      throw new Error(result.message || '加载失败')
    }

    rows.value = result.rows || []
    Object.assign(pagination, result.pagination || {})
    totalCount.value = result.meta?.total_count || 0
    levelOptions.value = result.meta?.level_choices || []
    levelStats.value = result.meta?.level_stats || []
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  pagination.page = 1
  loadRows()
}

function onPageChange(page) {
  pagination.page = page
  loadRows()
}

loadRows()
</script>

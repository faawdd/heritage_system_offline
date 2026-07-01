<template>
  <section>
    <header class="page-header">
      <h1>坎儿井导入检查</h1>
      <p>核查坎儿井数据覆盖率与分布，辅助导入结果验收</p>
    </header>

    <div class="stats-grid top-space">
      <div class="stat-card">
        <p class="stat-title">坎儿井数量</p>
        <p class="stat-value">{{ data.kanerjing_count }}</p>
      </div>
      <div class="stat-card">
        <p class="stat-title">文物总数</p>
        <p class="stat-value">{{ data.total_count }}</p>
      </div>
      <div class="stat-card">
        <p class="stat-title">占比</p>
        <p class="stat-value">{{ data.kanerjing_percentage }}%</p>
      </div>
    </div>

    <div class="card top-space">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
        <h3 style="margin: 0">等级分布</h3>
        <el-button :loading="loading" @click="loadData">刷新</el-button>
      </div>
      <el-table :data="data.level_breakdown" stripe v-loading="loading">
        <el-table-column prop="label" label="保护等级" min-width="220" />
        <el-table-column prop="count" label="数量" width="120" />
      </el-table>
    </div>

    <div class="card top-space">
      <h3 style="margin-top: 0">地址乡镇 Top10</h3>
      <el-table :data="data.top_addresses" stripe v-loading="loading">
        <el-table-column prop="township" label="乡镇/街道" min-width="220" />
        <el-table-column prop="count" label="数量" width="120" />
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchKanerjingImportCheck } from '../../api/heritageApi'

const loading = ref(false)
const data = reactive({
  kanerjing_count: 0,
  total_count: 0,
  kanerjing_percentage: 0,
  level_breakdown: [],
  top_addresses: []
})

async function loadData() {
  loading.value = true
  try {
    const result = await fetchKanerjingImportCheck()
    if (!result.success) {
      throw new Error(result.message || '加载失败')
    }
    Object.assign(data, result.data || {})
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

loadData()
</script>

<template>
  <section>
    <header class="page-header">
      <h1>日志中心</h1>
      <p>按用户组和日志查看权限显示记录。当前范围：{{ scope || '正在加载' }}。日志仅可查看，不可修改或删除。</p>
    </header>
    <div class="card top-space">
      <div class="toolbar">
        <el-select v-model="filters.source" aria-label="日志类型" style="width: 200px" @change="search">
          <el-option v-for="item in sourceOptions" :key="item.value" :value="item.value" :label="item.label" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="用户、对象或操作关键词" clearable style="max-width: 260px" @keyup.enter="search" />
        <el-select v-model="filters.success" aria-label="操作结果" style="width: 120px">
          <el-option label="全部结果" value="" />
          <el-option label="成功" value="true" />
          <el-option label="失败" value="false" />
        </el-select>
        <el-date-picker v-model="dateRange" type="datetimerange" start-placeholder="开始时间" end-placeholder="结束时间" />
        <el-button type="primary" :loading="loading" @click="search">查询</el-button>
      </div>
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />
      <el-table :data="rows" stripe v-loading="loading">
        <el-table-column prop="operator_name" label="操作用户" min-width="130" />
        <el-table-column prop="module" label="业务模块" min-width="150" />
        <el-table-column prop="action" label="操作" min-width="150" />
        <el-table-column label="结果" width="80">
          <template #default="{ row }"><el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="target" label="操作对象" min-width="160" show-overflow-tooltip />
        <el-table-column prop="detail" label="操作详情" min-width="260" show-overflow-tooltip />
        <el-table-column prop="ip" label="来源地址" min-width="140" />
        <el-table-column label="时间" min-width="180">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN', { hour12: false }) }}</template>
        </el-table-column>
        <el-table-column label="详情" width="80">
          <template #default="{ row }"><el-button link type="primary" @click="detail = row">查看</el-button></template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="loadLogs" />
    </div>
    <el-dialog :model-value="Boolean(detail)" title="日志详情" width="min(720px, 95vw)" @close="detail = null">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="日志类型">{{ detail.source_name }}</el-descriptions-item>
        <el-descriptions-item label="操作用户">{{ detail.operator_name }}</el-descriptions-item>
        <el-descriptions-item label="业务模块">{{ detail.module }}</el-descriptions-item>
        <el-descriptions-item label="操作">{{ detail.action }}</el-descriptions-item>
        <el-descriptions-item label="详情">{{ detail.detail || '无' }}</el-descriptions-item>
        <el-descriptions-item label="请求路径">{{ detail.request_path || '未记录' }}</el-descriptions-item>
        <el-descriptions-item label="请求方法">{{ detail.method || '未记录' }}</el-descriptions-item>
        <el-descriptions-item label="来源地址">{{ detail.ip || '未记录' }}</el-descriptions-item>
        <el-descriptions-item label="浏览器信息">{{ detail.user_agent || '未记录' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { fetchAuditLogs } from '../../../api/system/systemApi'
import { useAuthStore } from '../../../stores/system/authStore'

const authStore = useAuthStore()
const labels = { login: '登录日志', operation: '系统操作日志', django: 'Django后台操作日志', user: '用户管理审计', project: '用地项目流程日志' }
const sourceOptions = computed(() => (authStore.user?.capabilities?.log_sources || []).map(value => ({ value, label: labels[value] })))
const filters = reactive({ source: sourceOptions.value[0]?.value || 'login', keyword: '', success: '' })
const rows = ref([])
const scope = ref('')
const total = ref(0)
const page = ref(1)
const dateRange = ref(null)
const loading = ref(false)
const errorMessage = ref('')
const detail = ref(null)
let requestId = 0
async function loadLogs() {
  const id = ++requestId
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await fetchAuditLogs({
      ...filters, page: page.value, page_size: 20,
      ...(dateRange.value ? { start: dateRange.value[0].toISOString(), end: dateRange.value[1].toISOString() } : {})
    })
    if (!result.success) throw new Error(result.message || '日志加载失败')
    if (id !== requestId) return
    rows.value = result.rows
    total.value = result.pagination.total
    scope.value = result.scope
  } catch (error) {
    if (id !== requestId) return
    rows.value = []
    total.value = 0
    errorMessage.value = error?.response?.data?.detail || error.message || '日志加载失败'
  } finally {
    if (id === requestId) loading.value = false
  }
}
function search() {
  page.value = 1
  loadLogs()
}
loadLogs()
</script>

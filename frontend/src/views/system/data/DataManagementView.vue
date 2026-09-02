<template>
  <section>
    <header class="page-header">
      <h1>数据管理</h1>
      <p>在线版与离线版数据同步，以及从四普系统抓取“文物矢量图”边界坐标</p>
    </header>

    <DataSyncPanel class="card top-space" />

    <div class="card top-space">
      <h3>四普系统文物边界导入</h3>
      <p class="hint">
        Cookie 需手动从浏览器登录四普系统后，通过开发者工具的网络请求中复制 Cookie 请求头粘贴到下方；
        导入任务在后台按页（默认80条/页）分页多线程并发抓取，避免一次性长耗时请求触发网关超时。
      </p>

      <el-form label-width="140px" style="max-width: 760px">
        <el-form-item label="四普 Cookie" required>
          <el-input
            v-model="form.cookie"
            type="textarea"
            :rows="3"
            placeholder="粘贴四普系统登录后的 Cookie 请求头"
            :disabled="running"
          />
        </el-form-item>

        <el-form-item label="导入范围">
          <el-radio-group v-model="form.scope" :disabled="running">
            <el-radio label="missing">仅补全缺失本体边界的文物点</el-radio>
            <el-radio label="all">全部文物点（覆盖已导入数据）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="行政区划代码">
          <el-input v-model="form.user_county" placeholder="通常无需填写，留空即可" style="max-width: 320px" :disabled="running" />
          <div class="hint">留空按名称精确检索即可，多数情况下无需填写；填写错误的代码会导致检索始终返回0条，进而全部未匹配。</div>
        </el-form-item>

        <el-form-item label="每页数量">
          <el-input-number v-model="form.page_size" :min="10" :max="500" :disabled="running" />
          <div class="hint">文物点列表按此数量自动翻页处理，默认 80 条一页。</div>
        </el-form-item>

        <el-form-item label="并发线程数">
          <el-input-number v-model="form.max_workers" :min="1" :max="32" :disabled="running" />
          <div class="hint">页内并发请求四普系统的线程数，数值越大速度越快，但对目标服务器压力也越大。</div>
        </el-form-item>

        <el-form-item label="试跑数量限制">
          <el-input-number v-model="form.limit" :min="0" :max="2000" :disabled="running" />
          <div class="hint">建议首次先填写较小数值（如 10）验证 Cookie 有效后，再置 0 全量导入。</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="starting" :disabled="running" @click="startImport">开始导入</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="card top-space" v-if="progress.job_id">
      <h3>导入进度</h3>
      <el-progress
        :percentage="progressPercentage"
        :status="progressBarStatus"
        :stroke-width="18"
        :text-inside="true"
      />
      <div class="stats-grid top-space">
        <div class="stat-card">
          <p class="stat-title">状态</p>
          <p class="stat-value">{{ statusLabel }}</p>
        </div>
        <div class="stat-card">
          <p class="stat-title">已处理 / 总数</p>
          <p class="stat-value">{{ progress.processed }} / {{ progress.total }}</p>
        </div>
        <div class="stat-card">
          <p class="stat-title">成功写入</p>
          <p class="stat-value">{{ progress.matched }}</p>
        </div>
        <div class="stat-card">
          <p class="stat-title">未匹配</p>
          <p class="stat-value">{{ progress.unmatched_count }}</p>
        </div>
        <div class="stat-card">
          <p class="stat-title">匹配但无边界数据</p>
          <p class="stat-value">{{ progress.no_geometry_count }}</p>
        </div>
      </div>

      <el-alert
        v-if="progress.status === 'failed'"
        type="error"
        :title="`导入失败：${progress.error_message || '未知错误'}`"
        show-icon
        class="top-space"
      />

      <div class="top-space" v-if="(progress.unmatched || []).length">
        <h4>未匹配文物点</h4>
        <el-table :data="progress.unmatched" stripe size="small" max-height="260">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="name" label="文物名称" min-width="180" />
          <el-table-column label="候选名称" min-width="260">
            <template #default="scope">{{ (scope.row.candidates || []).join('、') || '-' }}</template>
          </el-table-column>
        </el-table>
      </div>

      <div class="top-space" v-if="(progress.no_geometry || []).length">
        <h4>匹配成功但四普未登记矢量图</h4>
        <el-table :data="progress.no_geometry" stripe size="small" max-height="260">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="name" label="文物名称" min-width="180" />
        </el-table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchSipuBoundaryImportStatus, startSipuBoundaryImport } from '../../../api/system/systemApi'
import DataSyncPanel from '../../../components/system/DataSyncPanel.vue'

const starting = ref(false)
const running = ref(false)
let pollTimer = null

const form = reactive({
  cookie: '',
  scope: 'missing',
  user_county: '',
  page_size: 80,
  max_workers: 8,
  limit: 0
})

const progress = reactive({
  job_id: '',
  status: '',
  total: 0,
  processed: 0,
  matched: 0,
  unmatched_count: 0,
  no_geometry_count: 0,
  unmatched: [],
  no_geometry: [],
  error_message: ''
})

const progressPercentage = computed(() => {
  if (!progress.total) return 0
  return Math.min(100, Math.round((progress.processed / progress.total) * 100))
})

const progressBarStatus = computed(() => {
  if (progress.status === 'success') return 'success'
  if (progress.status === 'failed') return 'exception'
  return ''
})

const statusLabel = computed(() => {
  const map = { running: '进行中', success: '已完成', failed: '失败' }
  return map[progress.status] || '-'
})

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function applyStatus(data) {
  progress.job_id = data.job_id
  progress.status = data.status
  progress.total = data.total
  progress.processed = data.processed
  progress.matched = data.matched
  progress.unmatched_count = data.unmatched_count
  progress.no_geometry_count = data.no_geometry_count
  progress.unmatched = data.unmatched || []
  progress.no_geometry = data.no_geometry || []
  progress.error_message = data.error_message
}

async function pollStatus(jobId) {
  try {
    const result = await fetchSipuBoundaryImportStatus(jobId)
    if (!result.success) {
      throw new Error(result.message || '查询进度失败')
    }
    applyStatus(result.data)
    if (result.data.status !== 'running') {
      running.value = false
      stopPolling()
      if (result.data.status === 'success') {
        ElMessage.success(`导入完成，成功写入 ${result.data.matched} 条`)
      } else {
        ElMessage.error(`导入失败：${result.data.error_message || '未知错误'}`)
      }
    }
  } catch (error) {
    running.value = false
    stopPolling()
    ElMessage.error(error?.message || '查询进度失败')
  }
}

async function startImport() {
  if (!form.cookie.trim()) {
    ElMessage.warning('请先填写四普系统 Cookie')
    return
  }

  starting.value = true
  try {
    const response = await startSipuBoundaryImport({
      cookie: form.cookie.trim(),
      scope: form.scope,
      user_county: form.user_county.trim(),
      page_size: form.page_size || 80,
      max_workers: form.max_workers || 8,
      limit: form.limit || 0
    })
    if (!response.success) {
      throw new Error(response.message || '创建导入任务失败')
    }

    const jobId = response.data.job_id
    Object.assign(progress, {
      job_id: jobId,
      status: 'running',
      total: 0,
      processed: 0,
      matched: 0,
      unmatched_count: 0,
      no_geometry_count: 0,
      unmatched: [],
      no_geometry: [],
      error_message: ''
    })
    running.value = true
    ElMessage.success('导入任务已创建，正在后台执行')

    stopPolling()
    pollTimer = setInterval(() => pollStatus(jobId), 2000)
  } catch (error) {
    ElMessage.error(error?.message || '创建导入任务失败')
  } finally {
    starting.value = false
  }
}

onUnmounted(() => {
  stopPolling()
})
</script>

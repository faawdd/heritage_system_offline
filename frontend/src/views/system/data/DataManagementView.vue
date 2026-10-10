<template>
  <section>
    <header class="page-header">
      <h1>数据管理</h1>
      <p>在线版与离线版数据同步，以及从四普系统全量导入不可移动文物数据</p>
    </header>

    <DataSyncPanel class="card top-space" />

    <div class="card top-space">
      <h3>四普系统文物数据全量导入</h3>
      <p class="hint">
        从四普系统一次性导入不可移动文物管理所需的全部数据：基本信息、文物构成、测点坐标、矢量范围（本体/保护区/建设控制地带）、
        照片、图纸、其他资料、关联专项等，按四普记录 ID 幂等写入，可重复执行。
        Cookie 需手动从浏览器登录四普系统后，通过开发者工具的网络请求中复制 Cookie 请求头粘贴到下方；
        导入任务在后台分页（四普单页上限 90 条）并发抓取，避免长耗时请求触发网关超时。
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
            <el-radio label="missing">仅导入尚未导入的文物点</el-radio>
            <el-radio label="all">全部文物点（刷新已导入数据）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="文物类别">
          <el-select v-model="form.category" style="width: 240px" :disabled="running">
            <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="行政区划代码">
          <el-input v-model="form.region_code" placeholder="留空：区县账号自动使用所属区县" style="max-width: 420px" :disabled="running" />
          <div class="hint">留空时自动识别账号：区县审定端账号只导入本区县数据（列表接口按 userCounty 过滤）；市/省级账号留空导入账号可见全部，也可填 6 位县级代码或市州/省前缀过滤。</div>
        </el-form-item>

        <el-form-item label="导入内容">
          <el-checkbox-group v-model="form.modules" :disabled="running">
            <el-checkbox v-for="item in moduleOptions" :key="item.value" :label="item.value">{{ item.label }}</el-checkbox>
          </el-checkbox-group>
          <div class="hint">基本信息与封面（含行政区划、保护级别、权属、简介等）始终导入。</div>
        </el-form-item>

        <el-form-item label="附件文件">
          <el-radio-group v-model="form.file_mode" :disabled="running">
            <el-radio label="none">仅导入元数据（不下载文件）</el-radio>
            <el-radio label="cover">仅下载每处文物封面图（推荐）</el-radio>
            <el-radio label="photos">下载照片原图</el-radio>
            <el-radio label="all">下载照片、图纸、资料中的图片</el-radio>
          </el-radio-group>
          <div class="hint">
            四普原图单张约 3MB，全量下载可能占用数百 GB 磁盘且耗时很长，请确认磁盘空间；PDF 等非图片附件四普不提供下载，仅保存元数据。
          </div>
        </el-form-item>

        <el-form-item label="同步文物点边界">
          <el-switch v-model="form.sync_sites" :disabled="running" />
          <div class="hint">按名称把矢量范围同步到“文物点”（HeritageSite）的本体/保护区/建控地带边界。</div>
        </el-form-item>

        <el-form-item label="并发线程数">
          <el-input-number v-model="form.max_workers" :min="1" :max="16" :disabled="running" />
          <div class="hint">页内并发请求四普系统的线程数，数值越大速度越快，但对目标服务器压力也越大。</div>
        </el-form-item>

        <el-form-item label="试跑数量限制">
          <el-input-number v-model="form.limit" :min="0" :max="100000" :disabled="running" />
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
          <p class="stat-title">失败</p>
          <p class="stat-value">{{ progress.failed_count }}</p>
        </div>
        <div v-for="item in statItems" :key="item.key" class="stat-card">
          <p class="stat-title">{{ item.label }}</p>
          <p class="stat-value">{{ progress.stats[item.key] || 0 }}</p>
        </div>
      </div>

      <el-alert
        v-if="progress.status === 'failed'"
        type="error"
        :title="`导入失败：${progress.error_message || '未知错误'}`"
        show-icon
        class="top-space"
      />

      <div class="top-space" v-if="(progress.failed || []).length">
        <h4>导入失败的文物点</h4>
        <el-table :data="progress.failed" stripe size="small" max-height="260">
          <el-table-column prop="code" label="四普编码" width="140" />
          <el-table-column prop="name" label="文物名称" min-width="180" />
          <el-table-column prop="error" label="失败原因" min-width="260" />
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

const categoryOptions = [
  { value: '', label: '全部类别' },
  { value: '0100', label: '古文化遗址' },
  { value: '0200', label: '古墓葬' },
  { value: '0300', label: '古建筑' },
  { value: '0400', label: '石窟寺及石刻' },
  { value: '0500', label: '近现代重要史迹及代表性建筑' },
  { value: '0600', label: '其他' }
]

const moduleOptions = [
  { value: 'constitute', label: '文物构成' },
  { value: 'points', label: '测点坐标' },
  { value: 'boundary', label: '矢量范围' },
  { value: 'photos', label: '照片' },
  { value: 'drawings', label: '图纸' },
  { value: 'materials', label: '其他资料' },
  { value: 'related', label: '关联专项/三普对应' }
]

const statItems = [
  { key: 'created', label: '新增文物' },
  { key: 'updated', label: '更新文物' },
  { key: 'constituents', label: '文物构成' },
  { key: 'points', label: '测点坐标' },
  { key: 'photos', label: '照片' },
  { key: 'drawings', label: '图纸' },
  { key: 'materials', label: '其他资料' },
  { key: 'relations', label: '关联记录' },
  { key: 'sites_synced', label: '同步边界的文物点' }
]

const form = reactive({
  cookie: '',
  scope: 'missing',
  category: '',
  region_code: '',
  modules: moduleOptions.map((item) => item.value),
  file_mode: 'cover',
  sync_sites: true,
  max_workers: 6,
  limit: 0
})

const progress = reactive({
  job_id: '',
  status: '',
  total: 0,
  processed: 0,
  matched: 0,
  failed_count: 0,
  failed: [],
  stats: {},
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
  progress.failed_count = data.failed_count || 0
  progress.failed = data.failed || []
  progress.stats = data.stats || {}
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
      category: form.category,
      region_code: form.region_code.trim(),
      modules: form.modules,
      file_mode: form.file_mode,
      sync_sites: form.sync_sites,
      max_workers: form.max_workers || 6,
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
      failed_count: 0,
      failed: [],
      stats: {},
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

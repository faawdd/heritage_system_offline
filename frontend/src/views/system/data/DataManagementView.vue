<template>
  <section class="data-management">
    <header class="page-header">
      <h1>数据管理</h1>
      <p>支持基础文物数据 CSV 导入与用户数据备份/恢复，并提供在线离线数据同步、四普系统边界坐标抓取。</p>
      <el-alert
        v-if="fromSetup"
        title="首次启动提示：建议先导入基础文物数据，再开展巡查与管理业务。"
        type="success"
        :closable="false"
        show-icon
      />
    </header>

    <DataSyncPanel class="card top-space" />

    <div class="card top-space">
      <h3>基础数据导入（CSV）</h3>
      <p class="hint">模板字段包含：文物名称、简介、位置、保护级别、经纬度等关键字段。</p>

      <div class="row">
        <el-button @click="downloadTemplate">下载导入模板</el-button>
        <el-upload
          :auto-upload="false"
          :show-file-list="true"
          accept=".csv"
          :limit="1"
          :on-change="onFileChange"
          :on-remove="onFileRemove"
        >
          <template #trigger>
            <el-button type="primary" plain>选择CSV文件</el-button>
          </template>
        </el-upload>
        <el-button type="primary" :loading="importing" :disabled="!selectedFile" @click="submitImport">
          {{ importing ? '导入中...' : '开始导入' }}
        </el-button>
      </div>

      <div class="import-result" v-if="importResult">
        <el-alert :title="importResult.message || '导入已完成'" :type="importResult.success ? 'success' : 'error'" :closable="false" show-icon />
        <ul v-if="importResult.success && importResult.data" class="stat-list">
          <li>新增：{{ importResult.data.created_count || 0 }}</li>
          <li>更新：{{ importResult.data.updated_count || 0 }}</li>
          <li>跳过：{{ importResult.data.skipped_count || 0 }}</li>
        </ul>
      </div>
    </div>

    <div class="card top-space">
      <h3>用户数据备份/恢复</h3>
      <p class="hint">备份将生成单文件 ZIP 压缩包，包含数据目录、日志目录及运行配置。恢复后应用会自动重启。</p>

      <div class="row">
        <el-button type="primary" :disabled="!desktopAvailable" :loading="backingUp" @click="createBackup">
          {{ backingUp ? '备份中...' : '一键备份' }}
        </el-button>
        <el-button type="warning" :disabled="!desktopAvailable" :loading="restoring" @click="restoreBackup">
          {{ restoring ? '恢复中...' : '一键恢复' }}
        </el-button>
      </div>

      <p v-if="lastBackupPath" class="path-note">最近备份：{{ lastBackupPath }}</p>
      <p v-if="!desktopAvailable" class="warn">当前非桌面环境，备份/恢复功能不可用。</p>
    </div>

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
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { importImmovableHeritage } from '../../../api/heritageApi'
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

const route = useRoute()
const importing = ref(false)
const selectedFile = ref(null)
const importResult = ref(null)
const backingUp = ref(false)
const restoring = ref(false)
const lastBackupPath = ref('')

const desktopAvailable = computed(() => typeof window !== 'undefined' && !!window.desktopData)
const fromSetup = computed(() => String(route.query.fromSetup || '') === '1' || String(route.query.fromSetup || '') === 'true')

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

function buildTemplateCsv() {
  const headers = [
    '采集编号',
    '文物名称',
    '时代',
    '文物类别',
    '保护级别',
    '权属',
    '保存现状',
    '省/自治区/直辖市',
    '市/州',
    '县/市/区',
    '乡镇/街道',
    '村/社区',
    '详细地址',
    '经度',
    '纬度',
    '管理责任人',
    '文物简介',
    '备注'
  ]
  const sample = [
    'SS-CJ-2026-0001',
    '示例文物点',
    '清',
    '古建筑',
    '县级文物保护单位',
    '国有',
    '一般',
    '新疆维吾尔自治区',
    '吐鲁番市',
    '鄯善县',
    '辟展镇',
    '示例村',
    '示例路1号',
    '90.123456',
    '42.654321',
    '示例管理单位',
    '用于演示的文物简介',
    '可按需补充'
  ]

  const toCsvLine = (cells) => cells.map((cell) => {
    const text = String(cell ?? '')
    return `"${text.replaceAll('"', '""')}"`
  }).join(',')

  return `\ufeff${toCsvLine(headers)}\n${toCsvLine(sample)}\n`
}

function downloadTemplate() {
  const csv = buildTemplateCsv()
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = '基础文物数据导入模板.csv'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

function onFileChange(file) {
  selectedFile.value = file?.raw || null
}

function onFileRemove() {
  selectedFile.value = null
}

async function submitImport() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择 CSV 文件')
    return
  }

  importing.value = true
  importResult.value = null
  try {
    const result = await importImmovableHeritage(selectedFile.value)
    importResult.value = result
    if (result?.success) {
      ElMessage.success(result?.message || '导入成功')
    } else {
      ElMessage.error(result?.message || '导入失败')
    }
  } catch (error) {
    importResult.value = {
      success: false,
      message: error?.message || '导入失败'
    }
    ElMessage.error(error?.message || '导入失败')
  } finally {
    importing.value = false
  }
}

async function createBackup() {
  if (!desktopAvailable.value) {
    ElMessage.warning('当前环境不支持桌面备份功能')
    return
  }

  backingUp.value = true
  try {
    const selected = await window.desktopData.pickBackupDir()
    if (!selected || selected.canceled) {
      return
    }

    const result = await window.desktopData.createBackup({ destinationRoot: selected.path })
    if (!result?.ok) {
      throw new Error(result?.message || '备份失败')
    }

    lastBackupPath.value = result.backupPath || ''
    ElMessage.success(result?.message || '备份成功')
  } catch (error) {
    ElMessage.error(error?.message || '备份失败')
  } finally {
    backingUp.value = false
  }
}

async function restoreBackup() {
  if (!desktopAvailable.value) {
    ElMessage.warning('当前环境不支持桌面恢复功能')
    return
  }

  try {
    await ElMessageBox.confirm('恢复会覆盖当前用户数据并自动重启，是否继续？', '恢复确认', {
      confirmButtonText: '继续恢复',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  restoring.value = true
  try {
    const selected = await window.desktopData.pickRestoreFile()
    if (!selected || selected.canceled) {
      return
    }

    const result = await window.desktopData.restoreBackup({ backupPath: selected.path })
    if (!result?.ok) {
      throw new Error(result?.message || '恢复失败')
    }

    ElMessage.success(result?.message || '恢复成功，正在重启')
  } catch (error) {
    ElMessage.error(error?.message || '恢复失败')
  } finally {
    restoring.value = false
  }
}

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.data-management {
  max-width: 1100px;
  margin: 0 auto;
  padding: 22px;
}

.header-block h1 {
  margin: 0;
  font-size: 28px;
}

.header-block p {
  margin: 10px 0 14px;
  color: #64748b;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.pane {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  background: #fff;
}

.pane h2 {
  margin: 0;
  font-size: 18px;
}

.hint {
  margin: 8px 0 14px;
  color: #64748b;
  font-size: 13px;
}

.row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.import-result {
  margin-top: 12px;
}

.stat-list {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #334155;
}

.path-note {
  margin-top: 12px;
  color: #334155;
  font-size: 13px;
  word-break: break-all;
}

.warn {
  margin-top: 10px;
  color: #b45309;
  font-size: 13px;
}

@media (max-width: 960px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>

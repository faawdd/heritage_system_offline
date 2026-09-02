<template>
  <article class="pane data-sync-panel">
    <h2>在线/离线数据同步</h2>
    <p class="hint">
      在联网版与离线版之间迁移业务数据：导出生成单个 ZIP 数据包，在另一端一键导入即可。
      <span v-if="systemVersion">当前系统版本 {{ systemVersion }}。</span>
    </p>

    <el-skeleton v-if="loadingOptions" :rows="3" animated />

    <template v-else>
      <div class="section">
        <div class="section-title">同步范围</div>
        <el-checkbox-group v-model="selectedDatasets">
          <el-checkbox v-for="item in datasets" :key="item.key" :value="item.key" :label="item.key">
            {{ item.label }}
            <span class="count">（{{ item.count }} 条）</span>
            <span class="desc">{{ item.description }}</span>
          </el-checkbox>
        </el-checkbox-group>
        <el-checkbox v-model="includeMedia">包含上传附件（照片、KML 等文件）</el-checkbox>
      </div>

      <div class="section">
        <div class="section-title">导出数据包</div>
        <div class="row">
          <el-button type="primary" :loading="exporting" :disabled="selectedDatasets.length === 0" @click="handleExport">
            {{ exporting ? '导出中...' : '一键导出 ZIP' }}
          </el-button>
          <span class="hint-inline">导出当前系统所选范围的全部数据。</span>
        </div>
      </div>

      <div class="section">
        <div class="section-title">导入数据包</div>
        <div class="row">
          <el-radio-group v-model="importMode">
            <el-radio value="merge">增量合并（按主键更新/新增）</el-radio>
            <el-radio value="replace">全量替换（先清空所选范围）</el-radio>
          </el-radio-group>
        </div>
        <div class="row">
          <el-upload
            :auto-upload="false"
            :show-file-list="true"
            accept=".zip"
            :limit="1"
            :on-change="onPackageChange"
            :on-remove="onPackageRemove"
          >
            <template #trigger>
              <el-button plain>选择 ZIP 数据包</el-button>
            </template>
          </el-upload>
          <el-button type="warning" :loading="importing" :disabled="!packageFile" @click="handleImport">
            {{ importing ? '导入中...' : '一键导入' }}
          </el-button>
        </div>
        <p class="warn">全量替换会删除所选范围内的现有记录，请先做好备份。</p>
      </div>

      <div class="section" v-if="importReport">
        <div class="section-title">导入结果</div>
        <ul class="stat-list">
          <li>写入记录：{{ importReport.imported_count }}</li>
          <li>跳过记录：{{ importReport.skipped_count }}</li>
          <li>恢复附件：{{ importReport.media_count }}</li>
          <li v-if="importReport.source?.generated_at">数据包生成时间：{{ importReport.source.generated_at }}</li>
        </ul>
        <el-table :data="importReport.details || []" size="small" border>
          <el-table-column prop="label" label="数据表" min-width="140" />
          <el-table-column prop="imported" label="写入" width="80" />
          <el-table-column prop="skipped" label="跳过" width="80" />
          <el-table-column label="错误摘要" min-width="220">
            <template #default="{ row }">
              <span v-if="!row.errors?.length">-</span>
              <span v-else class="warn">{{ row.errors.join('；') }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </article>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  exportDataSyncPackage,
  fetchDataSyncOptions,
  importDataSyncPackage
} from '../../api/system/systemApi'

const loadingOptions = ref(false)
const exporting = ref(false)
const importing = ref(false)

const datasets = ref([])
const selectedDatasets = ref([])
const includeMedia = ref(true)
const importMode = ref('merge')
const packageFile = ref(null)
const importReport = ref(null)
const systemVersion = ref('')

async function loadOptions() {
  loadingOptions.value = true
  try {
    const result = await fetchDataSyncOptions()
    if (!result?.success) {
      throw new Error(result?.message || '加载同步选项失败')
    }
    datasets.value = result.data?.datasets || []
    selectedDatasets.value = datasets.value.filter((item) => item.default_selected).map((item) => item.key)
    systemVersion.value = result.data?.system_version || ''
  } catch (error) {
    ElMessage.error(error?.message || '加载同步选项失败')
  } finally {
    loadingOptions.value = false
  }
}

function onPackageChange(file) {
  packageFile.value = file?.raw || null
}

function onPackageRemove() {
  packageFile.value = null
}

function saveBlob(blob, filename) {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

async function handleExport() {
  exporting.value = true
  try {
    const result = await exportDataSyncPackage({
      datasets: selectedDatasets.value,
      includeMedia: includeMedia.value
    })
    if (!result?.success || !result.download) {
      throw new Error(result?.message || '导出失败')
    }
    saveBlob(result.download.blob, result.download.filename)
    ElMessage.success('数据包导出成功')
  } catch (error) {
    ElMessage.error(error?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function handleImport() {
  if (!packageFile.value) {
    ElMessage.warning('请先选择 ZIP 数据包')
    return
  }

  const tip = importMode.value === 'replace'
    ? '全量替换会先清空所选范围内的现有数据，且不可撤销，是否继续？'
    : '将按主键合并导入数据包内容，是否继续？'
  try {
    await ElMessageBox.confirm(tip, '导入确认', {
      confirmButtonText: '继续导入',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  importing.value = true
  importReport.value = null
  try {
    const result = await importDataSyncPackage({
      file: packageFile.value,
      datasets: selectedDatasets.value,
      mode: importMode.value,
      importMedia: includeMedia.value
    })
    if (!result?.success) {
      throw new Error(result?.message || '导入失败')
    }
    importReport.value = result.data || null
    ElMessage.success(result.message || '导入成功')
    await loadOptions()
  } catch (error) {
    ElMessage.error(error?.message || '导入失败')
  } finally {
    importing.value = false
  }
}

onMounted(loadOptions)
</script>

<style scoped>
.data-sync-panel .section {
  margin-top: 16px;
}

.section-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.hint,
.hint-inline {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.count {
  color: var(--el-color-primary);
}

.desc {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: 6px;
}

.warn {
  color: var(--el-color-warning);
  font-size: 13px;
}

.stat-list {
  margin: 0 0 10px;
  padding-left: 18px;
}

:deep(.el-checkbox) {
  display: flex;
  align-items: center;
  height: auto;
  margin-bottom: 6px;
}
</style>

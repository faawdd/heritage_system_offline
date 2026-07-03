<template>
  <section class="data-management card">
    <header class="header-block">
      <h1>数据管理</h1>
      <p>支持基础文物数据 CSV 导入，以及用户数据一键备份/恢复。</p>
      <el-alert
        v-if="fromSetup"
        title="首次启动提示：建议先导入基础文物数据，再开展巡查与管理业务。"
        type="success"
        :closable="false"
        show-icon
      />
    </header>

    <div class="grid">
      <article class="pane">
        <h2>基础数据导入（CSV）</h2>
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
      </article>

      <article class="pane">
        <h2>用户数据备份/恢复</h2>
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
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { importImmovableHeritage } from '../../../api/heritageApi'

const route = useRoute()
const importing = ref(false)
const selectedFile = ref(null)
const importResult = ref(null)
const backingUp = ref(false)
const restoring = ref(false)
const lastBackupPath = ref('')

const desktopAvailable = computed(() => typeof window !== 'undefined' && !!window.desktopData)
const fromSetup = computed(() => String(route.query.fromSetup || '') === '1' || String(route.query.fromSetup || '') === 'true')

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

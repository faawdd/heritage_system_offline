<template>
  <section class="kml-fullscreen-page">
    <KmlOverlayMap
      class="kml-fullscreen-map"
      :selected-records="selectedRows"
      :conflict-rows="latestConflicts"
      :focus-conflict="activeConflict"
      :focus-overlap="activeOverlap"
      @conflict-click="onMapConflictClick"
      @overlap-update="onOverlapUpdate"
      @overlap-click="onMapOverlapClick"
    />

    <div class="kml-menu-toggle">
      <el-button type="primary" plain @click="menuVisible = !menuVisible">
        {{ menuVisible ? '隐藏菜单' : '显示菜单' }}
      </el-button>
    </div>

    <aside v-show="menuVisible" class="kml-floating-menu">
      <div class="floating-menu-header">
        <div>
          <h3>KML叠加检查</h3>
          <p>多文件叠加渲染 + 文物点冲突检查</p>
        </div>
        <el-button link type="primary" @click="menuVisible = false">收起</el-button>
      </div>

      <el-scrollbar class="floating-menu-scroll">
        <el-collapse v-model="activePanels">
          <el-collapse-item title="上传与即时分析" name="upload">
            <div class="floating-form-block">
              <input ref="uploadInputRef" type="file" accept=".kml,.kmz,.ovkml,.ovkmz" multiple />
              <div class="floating-row">
                <span>阈值(米)</span>
                <el-input-number v-model="threshold" :min="1" :max="5000" />
              </div>
              <el-switch v-model="immediateAnalyze" active-text="立即分析" inactive-text="仅上传" />
              <el-button type="primary" :loading="uploading" @click="uploadFiles">开始上传</el-button>
              <p class="hint-text">支持一个或多个KML叠加渲染，自动与文物点坐标进行冲突检查。</p>
            </div>
          </el-collapse-item>

          <el-collapse-item title="批量查询与导出" name="batch">
            <div class="floating-form-block">
              <div class="floating-row">
                <span>阈值(米)</span>
                <el-input-number v-model="threshold" :min="1" :max="5000" />
              </div>
              <el-switch v-model="forceReanalyze" active-text="强制重算" inactive-text="优先缓存" />
              <div class="floating-btn-grid">
                <el-button type="success" :loading="processing" @click="analyzeSelected">更新冲突数</el-button>
                <el-button type="primary" :loading="processing" @click="exportByAction('analyze_export_selected', 'conflict_report.csv')">导出查询报告</el-button>
                <el-button type="warning" :loading="processing" @click="exportByAction('export_conflict_kml', 'conflict_sites.kml')">导出冲突KML</el-button>
              </div>
              <el-input v-model="sipuCookie" placeholder="四普 Cookie（导出边界必填）" />
              <el-input v-model="sipuCounty" placeholder="行政区划代码（可选）" />
              <div class="floating-btn-grid">
                <el-button type="primary" plain :loading="processing" @click="exportByAction('export_boundary_points', 'boundary_points.csv')">导出边界CSV</el-button>
                <el-button type="primary" plain :loading="processing" @click="exportByAction('export_boundary_kmz', 'boundary.kmz')">导出边界KMZ</el-button>
              </div>
            </div>
          </el-collapse-item>

          <el-collapse-item title="KML叠加检查" name="overlap" v-if="overlapRows.length > 0">
            <div class="floating-form-block">
              <el-input v-model="overlapKeyword" placeholder="按文件名或要素名称筛选" clearable />

              <h4 class="floating-subtitle">按文件组合聚合</h4>
              <el-table :data="overlapGroupRows" stripe size="small" max-height="160">
                <el-table-column prop="pair_name" label="文件组合" min-width="180" />
                <el-table-column prop="overlap_count" label="叠加数" width="90" />
              </el-table>

              <h4 class="floating-subtitle">叠加明细</h4>
              <el-table
                :data="filteredOverlapRows"
                stripe
                size="small"
                max-height="220"
                :row-class-name="overlapRowClassName"
                @row-click="setActiveOverlap"
              >
                <el-table-column prop="kind_label" label="类型" width="90" />
                <el-table-column prop="source_a" label="文件A" min-width="120" />
                <el-table-column prop="source_b" label="文件B" min-width="120" />
              </el-table>
            </div>
          </el-collapse-item>

          <el-collapse-item title="记录选择与操作" name="records">
            <div class="floating-form-block">
              <div class="floating-row">
                <el-button type="primary" @click="loadRows">刷新记录</el-button>
                <span class="muted-text">已选 {{ selectedRows.length }} 条</span>
              </div>
              <el-table :data="rows" v-loading="loading" stripe size="small" max-height="280" @selection-change="onSelectionChange">
                <el-table-column type="selection" width="52" />
                <el-table-column prop="title" label="文件名" min-width="180" />
                <el-table-column prop="conflict_count" label="冲突数" width="90">
                  <template #default="scope">
                    <el-tag :type="scope.row.conflict_count > 0 ? 'danger' : 'success'">
                      {{ scope.row.conflict_count }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="180">
                  <template #default="scope">
                    <el-button link type="success" :loading="processing" @click="analyzeSingle(scope.row)">查询</el-button>
                    <el-button link type="primary" @click="openFile(scope.row)">源文件</el-button>
                    <el-button link type="danger" :loading="processing" @click="deleteRecord(scope.row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>

              <div class="floating-rename-list" v-if="rows.length > 0">
                <div class="rename-item" v-for="row in rows" :key="row.id">
                  <el-input v-model="renameDraft[row.id]" :placeholder="row.title" />
                  <el-button link type="success" :loading="processing" @click="renameRecord(row)">重命名</el-button>
                </div>
              </div>
            </div>
          </el-collapse-item>

          <el-collapse-item title="冲突详情" name="conflicts" v-if="latestConflicts.length > 0">
            <div class="floating-form-block">
              <el-input v-model="conflictKeyword" placeholder="按文物名称或来源文件筛选" clearable />

              <h4 class="floating-subtitle">按文物点聚合</h4>
              <el-table :data="siteSummaryRows" stripe size="small" max-height="180" @row-click="onSiteSummaryClick">
                <el-table-column prop="site_name" label="文物名称" min-width="140" />
                <el-table-column prop="conflict_count" label="冲突数" width="90" />
              </el-table>

              <h4 class="floating-subtitle">冲突明细</h4>
              <el-table
                :data="filteredConflicts"
                stripe
                size="small"
                max-height="220"
                :row-class-name="conflictRowClassName"
                @row-click="setActiveConflict"
              >
                <el-table-column prop="feature_source" label="来源文件" min-width="140" />
                <el-table-column prop="site_name" label="文物名称" min-width="120" />
                <el-table-column prop="relation" label="关系" width="100" />
              </el-table>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-scrollbar>
    </aside>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchGisKmlRecords, submitGisKmlManagementAction } from '../../api/gisApi'
import KmlOverlayMap from '../../components/gis/KmlOverlayMap.vue'

const rows = ref([])
const loading = ref(false)
const uploading = ref(false)
const processing = ref(false)
const uploadInputRef = ref(null)
const selectedIds = ref([])
const selectedRows = ref([])
const latestConflicts = ref([])

const threshold = ref(50)
const immediateAnalyze = ref(true)
const sipuCookie = ref('')
const sipuCounty = ref('')
const conflictKeyword = ref('')
const activeConflict = ref(null)
const overlapRows = ref([])
const overlapKeyword = ref('')
const activeOverlap = ref(null)
const forceReanalyze = ref(false)
const renameDraft = reactive({})
const menuVisible = ref(true)
const activePanels = ref(['upload', 'batch', 'overlap', 'records', 'conflicts'])

const filteredConflicts = computed(() => {
  const keyword = conflictKeyword.value.trim()
  if (!keyword) {
    return latestConflicts.value
  }
  return latestConflicts.value.filter((item) => {
    const source = String(item?.feature_source || '')
    const siteName = String(item?.site_name || '')
    return source.includes(keyword) || siteName.includes(keyword)
  })
})

const siteSummaryRows = computed(() => {
  const map = new Map()
  filteredConflicts.value.forEach((item) => {
    const siteId = String(item?.site_id || '')
    if (!siteId) {
      return
    }
    if (!map.has(siteId)) {
      map.set(siteId, {
        site_id: siteId,
        site_name: item?.site_name || '-',
        site_level: item?.site_level || '-',
        conflict_count: 0
      })
    }
    const row = map.get(siteId)
    row.conflict_count += 1
  })
  return Array.from(map.values()).sort((a, b) => b.conflict_count - a.conflict_count)
})

const filteredOverlapRows = computed(() => {
  const keyword = overlapKeyword.value.trim()
  const rows = overlapRows.value.map((item) => ({
    ...item,
    kind_label: item.kind === 'point' ? '点重叠' : item.kind === 'line' ? '线重叠' : '面重叠'
  }))
  if (!keyword) {
    return rows
  }
  return rows.filter((item) => {
    return [item.source_a, item.source_b, item.feature_a, item.feature_b].some((text) =>
      String(text || '').includes(keyword)
    )
  })
})

const overlapGroupRows = computed(() => {
  const grouped = new Map()
  filteredOverlapRows.value.forEach((item) => {
    const pair = [String(item.source_a || ''), String(item.source_b || '')].sort().join(' <-> ')
    if (!grouped.has(pair)) {
      grouped.set(pair, { pair_name: pair || '-', overlap_count: 0 })
    }
    grouped.get(pair).overlap_count += 1
  })
  return Array.from(grouped.values()).sort((a, b) => b.overlap_count - a.overlap_count)
})

function saveBlob(blob, filename) {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename || 'export.dat'
  link.click()
  URL.revokeObjectURL(link.href)
}

function appendSelectedIds(formData) {
  selectedIds.value.forEach((id) => {
    formData.append('selected_ids', String(id))
  })
}

function onSelectionChange(selection) {
  selectedIds.value = selection.map((item) => item.id)
  selectedRows.value = selection
}

function conflictKey(rowLike) {
  return [
    String(rowLike?.site_id || ''),
    String(rowLike?.feature_source || ''),
    String(rowLike?.relation || '')
  ].join('|')
}

function setActiveConflict(row) {
  activeConflict.value = row || null
}

function onMapConflictClick(row) {
  setActiveConflict(row)
}

function setActiveOverlap(row) {
  activeOverlap.value = row || null
}

function onMapOverlapClick(row) {
  setActiveOverlap(row)
}

function onOverlapUpdate(rows) {
  overlapRows.value = rows || []
  if (!activeOverlap.value) {
    return
  }
  const stillExists = overlapRows.value.some((item) => item.overlap_key === activeOverlap.value.overlap_key)
  if (!stillExists) {
    activeOverlap.value = null
  }
}

function onSiteSummaryClick(row) {
  const matched = filteredConflicts.value.find((item) => String(item?.site_id || '') === String(row?.site_id || ''))
  if (matched) {
    setActiveConflict(matched)
  }
}

function conflictRowClassName({ row }) {
  if (!activeConflict.value) {
    return ''
  }
  return conflictKey(row) === conflictKey(activeConflict.value) ? 'conflict-row-active' : ''
}

function overlapRowClassName({ row }) {
  if (!activeOverlap.value) {
    return ''
  }
  return row?.overlap_key === activeOverlap.value?.overlap_key ? 'conflict-row-active' : ''
}

async function runAction(formData, fallbackFileName = '') {
  const result = await submitGisKmlManagementAction(formData)
  if (!result.success) {
    throw new Error(result.message || '操作失败')
  }

  if (result.download?.blob) {
    saveBlob(result.download.blob, result.download.filename || fallbackFileName || 'export.dat')
  }

  const warnings = result.data?.warnings || []
  if (warnings.length > 0) {
    warnings.slice(0, 3).forEach((item) => ElMessage.warning(item))
  }
  return result
}

async function loadRows() {
  loading.value = true
  try {
    const result = await fetchGisKmlRecords()
    if (!result.success) {
      throw new Error(result.message || '加载失败')
    }
    rows.value = result.rows || []
    rows.value.forEach((row) => {
      if (renameDraft[row.id] == null) {
        renameDraft[row.id] = row.title
      }
    })
  } catch (error) {
    ElMessage.error(error?.message || '加载记录失败')
  } finally {
    loading.value = false
  }
}

async function uploadFiles() {
  const files = Array.from(uploadInputRef.value?.files || [])
  if (files.length === 0) {
    ElMessage.warning('请先选择上传文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.set('action', 'upload')
    formData.set('threshold_m', String(threshold.value))
    formData.set('immediate_analyze', immediateAnalyze.value ? '1' : '0')
    files.forEach((file) => formData.append('kml_files', file))

    const result = await runAction(formData)
    ElMessage.success(result.message || '上传完成')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

function openFile(row) {
  if (!row.file_url) {
    ElMessage.warning('该记录没有源文件地址')
    return
  }
  window.open(row.file_url, '_blank')
}

async function renameRecord(row) {
  const newTitle = (renameDraft[row.id] || '').trim()
  if (!newTitle) {
    ElMessage.warning('新名称不能为空')
    return
  }

  processing.value = true
  try {
    const formData = new FormData()
    formData.set('action', 'rename_record')
    formData.set('record_id', String(row.id))
    formData.set('new_title', newTitle)
    const result = await runAction(formData)
    ElMessage.success(result.message || '重命名成功')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '重命名失败')
  } finally {
    processing.value = false
  }
}

async function deleteRecord(row) {
  processing.value = true
  try {
    const formData = new FormData()
    formData.set('action', 'delete_record')
    formData.set('record_id', String(row.id))
    const result = await runAction(formData)
    ElMessage.success(result.message || '删除成功')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '删除失败')
  } finally {
    processing.value = false
  }
}

async function analyzeSingle(row) {
  processing.value = true
  try {
    const formData = new FormData()
    formData.set('action', 'analyze_selected')
    formData.set('threshold_m', String(threshold.value))
    formData.set('force_reanalyze', forceReanalyze.value ? '1' : '0')
    formData.set('single_record_id', String(row.id))
    const result = await runAction(formData)
    latestConflicts.value = result.data?.conflicts || []
    activeConflict.value = null
    ElMessage.success(result.message || '查询完成')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '查询失败')
  } finally {
    processing.value = false
  }
}

async function analyzeSelected() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先勾选记录')
    return
  }

  processing.value = true
  try {
    const formData = new FormData()
    formData.set('action', 'analyze_selected')
    formData.set('threshold_m', String(threshold.value))
    formData.set('force_reanalyze', forceReanalyze.value ? '1' : '0')
    appendSelectedIds(formData)
    const result = await runAction(formData)
    latestConflicts.value = result.data?.conflicts || []
    activeConflict.value = null
    ElMessage.success(result.message || '批量查询完成')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '批量查询失败')
  } finally {
    processing.value = false
  }
}

async function exportByAction(action, fallbackFileName) {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先勾选记录')
    return
  }

  processing.value = true
  try {
    const formData = new FormData()
    formData.set('action', action)
    formData.set('threshold_m', String(threshold.value))
    formData.set('force_reanalyze', forceReanalyze.value ? '1' : '0')
    appendSelectedIds(formData)
    if (action === 'export_boundary_points' || action === 'export_boundary_kmz') {
      formData.set('sipu_cookie', sipuCookie.value)
      formData.set('sipu_county', sipuCounty.value)
    }
    await runAction(formData, fallbackFileName)
    ElMessage.success('导出成功')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '导出失败')
  } finally {
    processing.value = false
  }
}

onMounted(() => {
  loadRows()
})
</script>

<style scoped>
.kml-fullscreen-page {
  position: relative;
  height: 100dvh;
  min-height: 100dvh;
  background: #f1f5f9;
  overflow: hidden;
}

.kml-fullscreen-map {
  height: 100%;
}

.kml-fullscreen-map :deep(.kml-overlay-map-wrap) {
  height: 100%;
}

.kml-fullscreen-map :deep(.kml-overlay-map) {
  height: 100%;
  border-radius: 0;
}

.kml-menu-toggle {
  position: absolute;
  left: 16px;
  top: 16px;
  z-index: 20;
}

.kml-floating-menu {
  position: absolute;
  left: 16px;
  top: 62px;
  bottom: 16px;
  width: min(420px, calc(100vw - 32px));
  z-index: 18;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe5ef;
  border-radius: 14px;
  box-shadow: 0 14px 36px rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(5px);
  display: flex;
  flex-direction: column;
}

.floating-menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 14px 8px;
  border-bottom: 1px solid #e2e8f0;
}

.floating-menu-header h3 {
  margin: 0;
  font-size: 16px;
}

.floating-menu-header p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.floating-menu-scroll {
  flex: 1;
  padding: 8px 10px 12px;
}

.floating-form-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.floating-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.floating-btn-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.floating-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #334155;
}

.floating-rename-list {
  border-top: 1px dashed #dbe5ef;
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rename-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.muted-text {
  color: #64748b;
  font-size: 12px;
}

.hint-text {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

:deep(.conflict-row-active > td) {
  background: #fff7ed !important;
}

@media (max-width: 1024px) {
  .kml-fullscreen-page {
    height: 100dvh;
    min-height: 100dvh;
  }

  .kml-floating-menu {
    top: 58px;
    left: 10px;
    right: 10px;
    width: auto;
    bottom: 10px;
  }

  .kml-menu-toggle {
    left: 10px;
    top: 10px;
  }
}
</style>

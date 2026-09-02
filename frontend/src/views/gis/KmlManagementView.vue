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
          <el-collapse-item title="上传与即时分析" name="upload" class="panel-upload">
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

          <el-collapse-item title="批量查询与导出" name="batch" class="panel-batch">
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
              <div class="floating-btn-grid">
                <el-button type="primary" plain :loading="processing" @click="exportByAction('export_boundary_points', 'boundary_points.csv')">导出边界CSV</el-button>
                <el-button type="primary" plain :loading="processing" @click="exportByAction('export_boundary_kmz', 'boundary.kmz')">导出边界KMZ</el-button>
              </div>
            </div>
          </el-collapse-item>

          <el-collapse-item title="KML叠加检查" name="overlap" class="panel-overlap" v-if="overlapRows.length > 0">
            <div class="floating-form-block">
              <el-input v-model="overlapKeyword" placeholder="按文件名或要素名称筛选" clearable />

              <h4 class="floating-subtitle">按文件组合聚合</h4>
              <div class="gis-info-cards">
                <article class="gis-info-card">
                  <span class="label">组合总数</span>
                  <strong>{{ overlapGroupRows.length }}</strong>
                </article>
                <article class="gis-info-card">
                  <span class="label">叠加明细</span>
                  <strong>{{ filteredOverlapRows.length }}</strong>
                </article>
              </div>
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

          <el-collapse-item title="记录选择与操作" name="records" class="panel-records">
            <div class="floating-form-block">
              <div class="floating-row">
                <el-button type="primary" @click="loadRows">刷新记录</el-button>
                <span class="muted-text">已选 {{ selectedRows.length }} 条</span>
              </div>
              <div class="floating-row">
                <el-button
                  type="success"
                  plain
                  :disabled="selectedRows.length !== 1"
                  @click="openProjectLinkDialog"
                >关联/新建项目选址</el-button>
                <span class="muted-text">选中单条记录后，可直接作为建设项目的选址范围</span>
              </div>
              <div class="gis-info-cards">
                <article class="gis-info-card">
                  <span class="label">记录总数</span>
                  <strong>{{ rows.length }}</strong>
                </article>
                <article class="gis-info-card">
                  <span class="label">当前选中</span>
                  <strong>{{ selectedRows.length }}</strong>
                </article>
                <article class="gis-info-card">
                  <span class="label">冲突合计</span>
                  <strong>{{ totalConflictCount }}</strong>
                </article>
              </div>
              <el-table ref="recordsTableRef" :data="rows" v-loading="loading" stripe size="small" max-height="280" @selection-change="onSelectionChange">
                <el-table-column type="selection" width="52" />
                <el-table-column prop="title" label="文件名" min-width="180" />
                <el-table-column prop="conflict_count" label="冲突数" width="90">
                  <template #default="scope">
                    <el-tag :type="scope.row.conflict_count > 0 ? 'danger' : 'success'">
                      {{ scope.row.conflict_count }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" min-width="280">
                  <template #default="scope">
                    <div class="record-op-cell">
                      <div class="record-op-actions">
                        <el-button link type="success" :loading="processing" @click="analyzeSingle(scope.row)">查询</el-button>
                        <el-button link type="primary" @click="openFile(scope.row)">源文件</el-button>
                        <el-button link type="danger" :loading="processing" @click="deleteRecord(scope.row)">删除</el-button>
                      </div>
                      <div class="record-rename-inline">
                        <el-input
                          v-model="renameDraft[scope.row.id]"
                          :placeholder="scope.row.title"
                          size="small"
                          @keyup.enter="renameRecord(scope.row)"
                        />
                        <el-button link type="warning" :loading="processing" @click="renameRecord(scope.row)">重命名</el-button>
                      </div>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-collapse-item>

          <el-collapse-item title="冲突详情" name="conflicts" class="panel-conflicts" v-if="latestConflicts.length > 0">
            <div class="floating-form-block">
              <el-input v-model="conflictKeyword" placeholder="按文物名称或来源文件筛选" clearable />

              <h4 class="floating-subtitle">按文物点聚合</h4>
              <div class="gis-info-cards">
                <article class="gis-info-card">
                  <span class="label">冲突总数</span>
                  <strong>{{ filteredConflicts.length }}</strong>
                </article>
                <article class="gis-info-card">
                  <span class="label">涉及文物点</span>
                  <strong>{{ siteSummaryRows.length }}</strong>
                </article>
                <article class="gis-info-card">
                  <span class="label">选中记录</span>
                  <strong>{{ selectedRows.length }}</strong>
                </article>
              </div>
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

    <el-dialog v-model="projectLinkVisible" title="关联/新建项目选址" width="620px">
      <p class="muted-text">
        当前记录：<strong>{{ selectedRows[0]?.title || '-' }}</strong>
      </p>
      <el-tabs v-model="projectLinkMode">
        <el-tab-pane label="关联已有项目" name="existing">
          <el-table
            :data="projectRows"
            size="small"
            border
            highlight-current-row
            max-height="300"
            @current-change="(row) => (selectedProject = row)"
          >
            <el-table-column prop="project_name" label="项目名称" min-width="200" />
            <el-table-column prop="company_name" label="项目单位" min-width="150" />
            <el-table-column prop="status_label" label="状态" width="140" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="新建项目" name="create">
          <el-form label-width="110px">
            <el-form-item label="项目名称" required>
              <el-input v-model="newProject.project_name" placeholder="建设项目名称" />
            </el-form-item>
            <el-form-item label="项目单位" required>
              <el-input v-model="newProject.company_name" placeholder="项目方/企业单位名称" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="projectLinkVisible = false">取消</el-button>
        <el-button type="primary" :loading="projectLinking" @click="submitProjectLink">确定</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { fetchGisKmlRecords, submitGisKmlManagementAction } from '../../api/gisApi'
import { createProject, fetchProjectList, linkProjectKmlRecord } from '../../api/projectApi'
import KmlOverlayMap from '../../components/gis/KmlOverlayMap.vue'

const router = useRouter()
const projectLinkVisible = ref(false)
const projectLinkMode = ref('existing')
const projectLinking = ref(false)
const projectRows = ref([])
const selectedProject = ref(null)
const newProject = reactive({ project_name: '', company_name: '' })

const rows = ref([])
const recordsTableRef = ref(null)
const loading = ref(false)
const uploading = ref(false)
const processing = ref(false)
const uploadInputRef = ref(null)
const selectedIds = ref([])
const selectedRows = ref([])
const latestConflicts = ref([])

const threshold = ref(50)
const immediateAnalyze = ref(true)
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

const totalConflictCount = computed(() => {
  return rows.value.reduce((sum, row) => {
    return sum + Number(row?.conflict_count || 0)
  }, 0)
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

async function syncTableSelectionByIds(ids = []) {
  if (!recordsTableRef.value) {
    return
  }

  recordsTableRef.value.clearSelection()
  if (!Array.isArray(ids) || ids.length === 0) {
    selectedIds.value = []
    selectedRows.value = []
    return
  }

  const wanted = new Set(ids.map((id) => String(id)))
  const matchedRows = rows.value.filter((row) => wanted.has(String(row.id)))

  matchedRows.forEach((row) => {
    recordsTableRef.value.toggleRowSelection(row, true)
  })

  selectedIds.value = matchedRows.map((item) => item.id)
  selectedRows.value = matchedRows
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
    const previousSelectedIds = [...selectedIds.value]
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

    await nextTick()
    await syncTableSelectionByIds(previousSelectedIds)
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
    await runAction(formData, fallbackFileName)
    ElMessage.success('导出成功')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '导出失败')
  } finally {
    processing.value = false
  }
}

async function openProjectLinkDialog() {
  if (selectedRows.value.length !== 1) {
    ElMessage.warning('请先在记录表中勾选一条记录')
    return
  }

  selectedProject.value = null
  newProject.project_name = selectedRows.value[0]?.title || ''
  newProject.company_name = ''
  projectLinkVisible.value = true

  try {
    const result = await fetchProjectList({})
    projectRows.value = result?.rows || []
  } catch (error) {
    ElMessage.error(error?.message || '加载项目列表失败')
  }
}

async function submitProjectLink() {
  const record = selectedRows.value[0]
  if (!record) {
    return
  }

  projectLinking.value = true
  try {
    let projectId = selectedProject.value?.id

    if (projectLinkMode.value === 'create') {
      if (!newProject.project_name.trim() || !newProject.company_name.trim()) {
        ElMessage.warning('请填写项目名称与项目单位')
        return
      }
      const created = await createProject({
        project_name: newProject.project_name.trim(),
        company_name: newProject.company_name.trim()
      })
      if (!created?.success) {
        throw new Error(created?.message || '新建项目失败')
      }
      projectId = created.data?.id || created.project_id || created.id
    }

    if (!projectId) {
      ElMessage.warning('请选择要关联的项目')
      return
    }

    const linked = await linkProjectKmlRecord(projectId, record.id)
    if (!linked?.success) {
      throw new Error(linked?.message || '关联失败')
    }

    ElMessage.success('已关联，正在跳转到项目详情')
    projectLinkVisible.value = false
    router.push(`/projects/${projectId}`)
  } catch (error) {
    ElMessage.error(error?.message || '操作失败')
  } finally {
    projectLinking.value = false
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
  background:
    radial-gradient(circle at 6% 8%, rgba(14, 165, 233, 0.22) 0, rgba(14, 165, 233, 0) 36%),
    radial-gradient(circle at 92% 12%, rgba(59, 130, 246, 0.24) 0, rgba(59, 130, 246, 0) 38%),
    linear-gradient(165deg, #e0f2fe 0%, #ecfeff 36%, #f8fafc 72%, #f1f5f9 100%);
  overflow: hidden;
}

.kml-fullscreen-page::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: linear-gradient(rgba(15, 23, 42, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(15, 23, 42, 0.03) 1px, transparent 1px);
  background-size: 28px 28px;
  opacity: 0.28;
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
  z-index: 30;
}

.kml-menu-toggle :deep(.el-button) {
  border: 1px solid rgba(148, 163, 184, 0.45);
  background: rgba(255, 255, 255, 0.76);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(6px);
}

.kml-floating-menu {
  position: absolute;
  left: 16px;
  top: 62px;
  bottom: 16px;
  width: min(420px, calc(100vw - 32px));
  z-index: 28;
  background: linear-gradient(168deg, rgba(255, 255, 255, 0.9) 0%, rgba(248, 250, 252, 0.94) 100%);
  border: 1px solid rgba(148, 163, 184, 0.38);
  border-radius: 18px;
  box-shadow: 0 20px 46px rgba(15, 23, 42, 0.2);
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  animation: menu-fade-in 220ms ease-out;
}

.floating-menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 10px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.28);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.84) 0%, rgba(255, 255, 255, 0.38) 100%);
}

.floating-menu-header h3 {
  margin: 0;
  font-size: 17px;
  letter-spacing: 0.2px;
  color: #0f172a;
}

.floating-menu-header p {
  margin: 5px 0 0;
  font-size: 12px;
  color: #475569;
}

.floating-menu-scroll {
  flex: 1;
  padding: 10px 12px 14px;
}

.floating-menu-scroll :deep(.el-collapse) {
  border: 0;
  background: transparent;
}

.floating-menu-scroll :deep(.el-collapse-item) {
  background: rgba(255, 255, 255, 0.54);
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 12px;
  margin-bottom: 10px;
  overflow: hidden;
  position: relative;
}

.floating-menu-scroll :deep(.el-collapse-item)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, #94a3b8 0%, #64748b 100%);
  opacity: 0.55;
}

.floating-menu-scroll :deep(.panel-upload.el-collapse-item)::before {
  background: linear-gradient(180deg, #0284c7 0%, #0ea5e9 100%);
  opacity: 0.9;
}

.floating-menu-scroll :deep(.panel-batch.el-collapse-item)::before {
  background: linear-gradient(180deg, #16a34a 0%, #14b8a6 100%);
  opacity: 0.9;
}

.floating-menu-scroll :deep(.panel-overlap.el-collapse-item)::before,
.floating-menu-scroll :deep(.panel-conflicts.el-collapse-item)::before {
  background: linear-gradient(180deg, #dc2626 0%, #f97316 100%);
  opacity: 0.9;
}

.floating-menu-scroll :deep(.panel-records.el-collapse-item)::before {
  background: linear-gradient(180deg, #6366f1 0%, #2563eb 100%);
  opacity: 0.85;
}

.floating-menu-scroll :deep(.el-collapse-item__header) {
  height: 42px;
  line-height: 42px;
  padding: 0 12px 0 14px;
  border: 0;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.9) 0%, rgba(241, 245, 249, 0.8) 100%);
}

.floating-menu-scroll :deep(.el-collapse-item__wrap) {
  border: 0;
  background: transparent;
}

.floating-menu-scroll :deep(.el-collapse-item__content) {
  padding: 12px;
}

.floating-form-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.floating-row {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
}

.floating-row > span {
  font-size: 12px;
  color: #475569;
  white-space: nowrap;
}

:deep(.floating-row .el-input-number),
:deep(.floating-row .el-select),
:deep(.floating-row .el-input) {
  width: 100%;
}

.floating-btn-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

:deep(.floating-btn-grid .el-button) {
  margin: 0;
  width: 100%;
}

:deep(.floating-form-block .el-switch) {
  align-self: flex-start;
}

:deep(.floating-form-block .el-input),
:deep(.floating-form-block .el-select),
:deep(.floating-form-block .el-input-number) {
  width: 100%;
}

.floating-subtitle {
  margin: 6px 0 0;
  font-size: 12px;
  color: #0f172a;
  font-weight: 600;
  letter-spacing: 0.25px;
  text-transform: uppercase;
}

.gis-info-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.gis-info-card {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 10px;
  padding: 7px 8px;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.92) 0%, rgba(241, 245, 249, 0.88) 100%);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.gis-info-card .label {
  font-size: 11px;
  color: #64748b;
  line-height: 1.2;
}

.gis-info-card strong {
  font-size: 15px;
  color: #0f172a;
  font-weight: 700;
  line-height: 1;
}

.record-op-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.record-op-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 1;
}

.record-rename-inline {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}

:deep(.record-rename-inline .el-input__wrapper) {
  min-height: 28px;
}

.muted-text {
  color: #64748b;
  font-size: 12px;
}

.hint-text {
  margin: 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.5;
}

:deep(.el-table) {
  --el-table-bg-color: rgba(255, 255, 255, 0.86);
  --el-table-tr-bg-color: rgba(255, 255, 255, 0.86);
  --el-table-header-bg-color: rgba(241, 245, 249, 0.92);
  --el-table-border-color: rgba(148, 163, 184, 0.3);
  --el-table-row-hover-bg-color: rgba(219, 234, 254, 0.52);
  border-radius: 10px;
  overflow: hidden;
}

:deep(.floating-form-block .el-input__wrapper),
:deep(.floating-form-block .el-textarea__inner),
:deep(.floating-form-block .el-select__wrapper),
:deep(.floating-form-block .el-input-number),
:deep(.floating-form-block .el-switch) {
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.38) inset;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.92);
}

:deep(.floating-form-block .el-input__wrapper:hover),
:deep(.floating-form-block .el-select__wrapper:hover),
:deep(.floating-form-block .el-input-number:hover) {
  box-shadow: 0 0 0 1px rgba(14, 116, 144, 0.45) inset;
}

:deep(.floating-form-block .el-button--primary),
:deep(.floating-form-block .el-button--success),
:deep(.floating-form-block .el-button--warning) {
  border: 0;
  box-shadow: 0 8px 18px rgba(14, 116, 144, 0.22);
  transition: transform 140ms ease, box-shadow 140ms ease, filter 140ms ease, opacity 140ms ease;
}

:deep(.floating-form-block .el-button--primary) {
  background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%);
}

:deep(.floating-form-block .el-button--success) {
  background: linear-gradient(135deg, #059669 0%, #0ea5e9 100%);
}

:deep(.floating-form-block .el-button--warning) {
  background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
  color: #fff;
}

:deep(.floating-form-block .el-button:hover) {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(14, 116, 144, 0.25);
}

:deep(.floating-form-block .el-button:active) {
  transform: translateY(0) scale(0.98);
  filter: saturate(1.06);
  box-shadow: 0 5px 12px rgba(14, 116, 144, 0.2);
}

:deep(.floating-form-block .el-button.is-disabled),
:deep(.floating-form-block .el-button.is-loading) {
  filter: saturate(0.5) brightness(1.02);
  opacity: 0.72;
  transform: none;
  box-shadow: none;
}

/* 给地图右上工具栏预留用户面板空间，避免模块重叠 */
.kml-fullscreen-page :deep(.kml-overlay-toolbar) {
  top: 76px;
  right: 14px;
  z-index: 14;
  max-width: min(360px, calc(100vw - 32px));
}

.kml-fullscreen-page :deep(.kml-legend-panel) {
  z-index: 13;
}

.kml-fullscreen-page :deep(.kml-overlay-tip) {
  z-index: 12;
}

:deep(.conflict-row-active > td) {
  background: rgba(254, 215, 170, 0.35) !important;
}

@keyframes menu-fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1360px) {
  .kml-fullscreen-page :deep(.kml-overlay-toolbar) {
    top: 88px;
  }
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
    border-radius: 14px;
  }

  .kml-menu-toggle {
    left: 10px;
    top: 10px;
  }

  .floating-btn-grid {
    grid-template-columns: 1fr;
  }

  .gis-info-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .kml-fullscreen-page :deep(.kml-overlay-toolbar) {
    top: auto;
    right: 10px;
    bottom: 210px;
    max-width: min(320px, calc(100vw - 20px));
  }

  .floating-menu-scroll :deep(.el-collapse-item__content) {
    padding: 10px;
  }
}

@media (max-width: 640px) {
  .gis-info-cards {
    grid-template-columns: 1fr;
  }
}
</style>

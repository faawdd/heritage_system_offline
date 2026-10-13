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

    <div v-if="!menuVisible" class="kml-menu-toggle">
      <el-button type="primary" @click="menuVisible = true">
        <span class="menu-toggle-mark">K</span>
        KML 检查
      </el-button>
    </div>

    <aside v-show="menuVisible" class="kml-floating-menu">
      <div class="floating-menu-header">
        <div class="menu-heading">
          <span class="menu-eyebrow">地图工作台</span>
          <h3>KML 叠加检查</h3>
          <p>图层、记录与空间冲突，一处管理</p>
        </div>
        <el-button class="menu-close-button" text circle aria-label="收起菜单" @click="menuVisible = false">×</el-button>
      </div>

      <el-tabs v-model="activeMenuTab" class="floating-menu-tabs" stretch>
        <el-tab-pane name="workspace">
          <template #label>工作台</template>
          <el-scrollbar class="floating-menu-scroll">
            <el-collapse v-model="activeWorkspacePanels">
          <el-collapse-item title="上传与即时分析" name="upload" class="panel-upload">
            <div class="floating-form-block">
              <label class="upload-picker">
                <span class="upload-picker-icon">＋</span>
                <span>
                  <strong>{{ uploadSelection.length ? `已选择 ${uploadSelection.length} 个文件` : '选择 KML 文件' }}</strong>
                  <small>{{ uploadSelection[0]?.name || '支持 KML、KMZ、OVKML、OVKMZ，可多选' }}</small>
                </span>
                <input ref="uploadInputRef" type="file" accept=".kml,.kmz,.ovkml,.ovkmz" multiple @change="onUploadSelectionChange" />
                <span class="upload-file-browse">浏览</span>
              </label>
              <div class="upload-options-row">
                <label class="switch-copy">
                  <strong>上传后立即分析</strong>
                  <small>检测要素与文物范围的冲突</small>
                </label>
                <el-switch v-model="immediateAnalyze" active-text="立即分析" inactive-text="仅上传" />
              </div>
              <div class="floating-row">
                <span>距离阈值</span>
                <el-input-number v-model="threshold" :min="1" :max="5000" controls-position="right">
                  <template #suffix>米</template>
                </el-input-number>
              </div>
              <el-button class="upload-submit" type="primary" :loading="uploading" @click="uploadFiles">
                {{ uploading ? '正在上传…' : '开始上传并加载' }}
              </el-button>
            </div>
          </el-collapse-item>

          <el-collapse-item title="批量查询与导出" name="batch" class="panel-batch">
            <div class="floating-form-block">
              <div class="batch-toolbar">
                <span>当前选中 <strong>{{ selectedRows.length }}</strong> 条记录</span>
                <el-switch v-model="forceReanalyze" active-text="强制重算" inactive-text="优先缓存" />
              </div>
              <div class="batch-actions">
                <el-button type="success" :disabled="!selectedRows.length" :loading="processing" @click="analyzeSelected">更新冲突数</el-button>
                <el-button type="primary" :disabled="!selectedRows.length" :loading="processing" @click="exportByAction('analyze_export_selected', 'conflict_report.csv')">导出查询报告</el-button>
                <el-button type="warning" :disabled="!selectedRows.length" :loading="processing" @click="exportByAction('export_conflict_kml', 'conflict_sites.kml')">导出冲突 KML</el-button>
                <el-button plain :disabled="!selectedRows.length" :loading="processing" @click="exportByAction('export_boundary_points', 'boundary_points.csv')">边界点 CSV</el-button>
                <el-button plain :disabled="!selectedRows.length" :loading="processing" @click="exportByAction('export_boundary_kmz', 'boundary.kmz')">边界范围 KMZ</el-button>
              </div>
              <p v-if="!selectedRows.length" class="hint-text">请先在「记录」页选择文件。</p>
            </div>
          </el-collapse-item>
            </el-collapse>
          </el-scrollbar>
        </el-tab-pane>

        <el-tab-pane name="overlap">
          <template #label>
            <span>叠加 <span v-if="overlapRows.length" class="tab-count">{{ overlapRows.length }}</span></span>
          </template>
          <el-scrollbar class="floating-menu-scroll">
            <el-collapse v-model="activeOverlapPanels">
          <el-collapse-item title="文件间要素叠加" name="overlap" class="panel-overlap">
            <div v-if="overlapRows.length" class="floating-form-block">
              <el-input v-model="overlapKeyword" placeholder="按文件名或要素名称筛选" clearable />

              <h4 class="floating-subtitle">按文件组合聚合</h4>
              <div class="gis-info-cards overlap-info-cards">
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
            <div v-else class="result-empty">选择两条或更多记录后，地图会自动检查不同文件间的要素叠加。</div>
          </el-collapse-item>
            </el-collapse>
          </el-scrollbar>
        </el-tab-pane>

        <el-tab-pane name="records">
          <template #label>
            <span>记录 <span class="tab-count">{{ rows.length }}</span></span>
          </template>
          <el-scrollbar class="floating-menu-scroll">
            <el-collapse v-model="activeRecordPanels">
          <el-collapse-item title="记录选择与操作" name="records" class="panel-records">
            <div class="floating-form-block records-content">
              <div class="records-toolbar">
                <div>
                  <span class="section-kicker">文件管理</span>
                  <strong>已上传记录</strong>
                </div>
                <el-button text :loading="loading" @click="loadRows">刷新</el-button>
              </div>
              <div class="floating-row">
                <el-button
                  type="success"
                  plain
                  :disabled="selectedRows.length !== 1"
                  @click="openProjectLinkDialog"
                >关联/新建项目选址</el-button>
                <span class="muted-text">选择一条记录后关联项目选址</span>
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
              <el-table ref="recordsTableRef" :data="rows" v-loading="loading" stripe size="small" max-height="420" @selection-change="onSelectionChange">
                <el-table-column type="selection" width="42" />
                <el-table-column prop="title" label="文件名" min-width="145" show-overflow-tooltip />
                <el-table-column prop="conflict_count" label="冲突" width="66">
                  <template #default="scope">
                    <el-tag :type="scope.row.conflict_count > 0 ? 'danger' : 'success'" effect="light">
                      {{ scope.row.conflict_count }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="98" fixed="right">
                  <template #default="scope">
                    <div class="record-op-actions">
                      <el-button link type="success" :loading="processing" @click="analyzeSingle(scope.row)">查询</el-button>
                      <el-dropdown trigger="click">
                        <el-button link type="primary">更多</el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item @click="openFile(scope.row)">打开源文件</el-dropdown-item>
                            <el-dropdown-item @click="beginRename(scope.row)">重命名</el-dropdown-item>
                            <el-dropdown-item divided @click="deleteRecord(scope.row)">删除记录</el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
              <div v-if="renameTarget" class="rename-editor">
                <strong>重命名：{{ renameTarget.title }}</strong>
                <div class="rename-editor-row">
                  <el-input
                    v-model="renameDraft[renameTarget.id]"
                    :placeholder="renameTarget.title"
                    size="small"
                    @keyup.enter="renameRecord(renameTarget)"
                  />
                  <el-button size="small" type="primary" :loading="processing" @click="renameRecord(renameTarget)">保存</el-button>
                  <el-button size="small" @click="renameTarget = null">取消</el-button>
                </div>
              </div>
            </div>
          </el-collapse-item>
            </el-collapse>
          </el-scrollbar>
        </el-tab-pane>

        <el-tab-pane name="conflicts">
          <template #label>
            <span title="文物保护范围冲突">冲突 <span v-if="latestConflicts.length" class="tab-count">{{ latestConflicts.length }}</span></span>
          </template>
          <el-scrollbar class="floating-menu-scroll">
            <el-collapse v-model="activeConflictPanels">
          <el-collapse-item title="冲突详情" name="conflicts" class="panel-conflicts">
            <div v-if="latestConflicts.length" class="floating-form-block">
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
          <div v-else class="result-empty">选择记录并运行冲突分析后，结果会显示在这里。</div>
          </el-collapse-item>
            </el-collapse>
          </el-scrollbar>
        </el-tab-pane>
      </el-tabs>
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
const uploadSelection = ref([])
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
const renameTarget = ref(null)
const menuVisible = ref(true)
const activeMenuTab = ref('workspace')
const activeWorkspacePanels = ref(['upload'])
const activeOverlapPanels = ref(['overlap'])
const activeRecordPanels = ref(['records'])
const activeConflictPanels = ref(['conflicts'])

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

function onUploadSelectionChange(event) {
  uploadSelection.value = Array.from(event.target?.files || [])
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

function beginRename(row) {
  renameTarget.value = row
  renameDraft[row.id] = row.title
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
    renameTarget.value = null
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
    activeMenuTab.value = 'conflicts'
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
    activeMenuTab.value = 'conflicts'
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
    linear-gradient(165deg, var(--kml-page-start, #e0f2fe) 0%, var(--kml-page-mid, #ecfeff) 36%, var(--kml-page-end, #f8fafc) 72%, var(--kml-page-bottom, #f1f5f9) 100%);
  overflow: hidden;
}

:global(:root[data-theme='dark']) .kml-fullscreen-page {
  --kml-page-start: #102a43;
  --kml-page-mid: #12344e;
  --kml-page-end: #0e1a2b;
  --kml-page-bottom: #0b1728;
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
  min-height: 42px;
  padding: 0 15px 0 11px;
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 14px;
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.2);
  backdrop-filter: blur(12px);
  font-weight: 650;
}

.menu-toggle-mark {
  display: inline-grid;
  width: 24px;
  height: 24px;
  margin-right: 8px;
  place-items: center;
  border-radius: 8px;
  background: linear-gradient(145deg, #0ea5e9, #2563eb);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}

.kml-floating-menu {
  position: absolute;
  left: 16px;
  top: 16px;
  bottom: 16px;
  width: min(410px, calc(100vw - 32px));
  z-index: 28;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 20px;
  background: color-mix(in srgb, var(--surface) 96%, transparent);
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.24), 0 3px 12px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(18px);
  animation: menu-fade-in 220ms ease-out;
}

.floating-menu-header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  min-height: 91px;
  padding: 16px 18px 14px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    radial-gradient(circle at 94% 0%, rgba(14, 165, 233, 0.14), transparent 42%),
    color-mix(in srgb, var(--surface) 92%, var(--bg));
}

.menu-heading {
  min-width: 0;
}

.menu-eyebrow {
  display: block;
  margin-bottom: 5px;
  color: #0284c7;
  font-size: 10px;
  font-weight: 750;
  letter-spacing: 0.12em;
}

.floating-menu-header h3 {
  margin: 0;
  color: var(--text);
  font-size: 17px;
  font-weight: 750;
  letter-spacing: 0.01em;
}

.floating-menu-header p {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 11px;
}

.menu-close-button {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  color: var(--muted);
  font-size: 24px;
}

.floating-menu-tabs {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.floating-menu-tabs :deep(.el-tabs__header) {
  flex: 0 0 auto;
  margin: 0;
  padding: 0 12px;
  background: color-mix(in srgb, var(--surface) 96%, var(--bg));
}

.floating-menu-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.floating-menu-tabs :deep(.el-tabs__item) {
  height: 46px;
  padding: 0 9px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
}

.floating-menu-tabs :deep(.el-tabs__item.is-active) {
  color: #0284c7;
}

.floating-menu-tabs :deep(.el-tabs__active-bar) {
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, #0ea5e9, #2563eb);
}

.floating-menu-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
}

.floating-menu-tabs :deep(.el-tab-pane) {
  height: 100%;
}

.tab-count {
  display: inline-grid;
  min-width: 18px;
  height: 18px;
  margin-left: 3px;
  padding: 0 4px;
  place-items: center;
  border-radius: 9px;
  background: color-mix(in srgb, #0ea5e9 14%, var(--surface));
  color: #0284c7;
  font-size: 10px;
  line-height: 1;
}

.floating-menu-scroll {
  height: 100%;
  padding: 12px;
}

.floating-menu-scroll :deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}

.floating-menu-scroll :deep(.el-collapse) {
  border: 0;
  background: transparent;
}

.floating-menu-scroll :deep(.el-collapse-item) {
  margin-bottom: 10px;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 80%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--surface) 94%, var(--bg));
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.floating-menu-scroll :deep(.el-collapse-item.is-active) {
  border-color: color-mix(in srgb, #0ea5e9 42%, var(--line));
  box-shadow: 0 5px 16px rgba(15, 23, 42, 0.06);
}

.floating-menu-scroll :deep(.el-collapse-item__header) {
  height: 46px;
  padding: 0 14px;
  border: 0;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  font-weight: 650;
}

.floating-menu-scroll :deep(.el-collapse-item__wrap) {
  border: 0;
  background: transparent;
}

.floating-menu-scroll :deep(.el-collapse-item__content) {
  padding: 2px 13px 14px;
}

.upload-picker {
  position: relative;
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 70px;
  padding: 11px 12px;
  border: 1px dashed color-mix(in srgb, #0284c7 44%, var(--line));
  border-radius: 12px;
  background: color-mix(in srgb, #0ea5e9 6%, var(--surface));
  cursor: pointer;
  transition: border-color 150ms ease, background 150ms ease;
}

.upload-picker:hover {
  border-color: #0284c7;
  background: color-mix(in srgb, #0ea5e9 10%, var(--surface));
}

.upload-picker-icon {
  display: grid;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  background: linear-gradient(145deg, #0ea5e9, #2563eb);
  color: white;
  font-size: 23px;
  font-weight: 300;
  line-height: 1;
}

.upload-picker > span:nth-child(2) {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.upload-picker strong,
.switch-copy strong {
  color: var(--text);
  font-size: 12px;
  font-weight: 650;
}

.upload-picker small,
.switch-copy small {
  color: var(--muted);
  font-size: 10px;
  line-height: 1.45;
}

.upload-picker input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}

.upload-picker:focus-within {
  outline: 2px solid color-mix(in srgb, #0284c7 55%, transparent);
  outline-offset: 2px;
}

.upload-file-browse {
  padding: 6px 8px;
  border: 1px solid color-mix(in srgb, #0ea5e9 24%, var(--line));
  border-radius: 7px;
  background: color-mix(in srgb, #0ea5e9 13%, var(--surface));
  color: #0369a1;
  font-size: 10px;
  font-weight: 650;
}

.upload-options-row,
.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 43px;
  padding: 9px 10px;
  border: 1px solid color-mix(in srgb, var(--line) 75%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--surface) 92%, var(--bg));
}

.switch-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.batch-toolbar > span {
  color: var(--muted);
  font-size: 11px;
}

.batch-toolbar > span strong {
  color: #0284c7;
  font-size: 15px;
}

.upload-submit {
  width: 100%;
  min-height: 38px;
  border: 0;
  border-radius: 10px;
  background: linear-gradient(135deg, #0284c7, #2563eb);
  box-shadow: 0 7px 16px rgba(2, 132, 199, 0.2);
  font-weight: 650;
}

.batch-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}

.batch-actions :deep(.el-button) {
  width: 100%;
  min-width: 0;
  min-height: 34px;
  margin: 0;
  padding: 0 7px;
  border-radius: 9px;
  font-size: 11px;
}

.batch-actions :deep(.el-button:first-child) {
  grid-column: 1 / -1;
}

.records-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.records-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.records-toolbar > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.records-toolbar strong {
  color: var(--text);
  font-size: 13px;
}

.section-kicker {
  color: #0284c7;
  font-size: 9px;
  font-weight: 750;
  letter-spacing: 0.1em;
}

.record-op-actions {
  gap: 4px;
}

.rename-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border: 1px solid color-mix(in srgb, #0ea5e9 30%, var(--line));
  border-radius: 10px;
  background: color-mix(in srgb, #0ea5e9 5%, var(--surface));
}

.rename-editor > strong {
  overflow: hidden;
  color: var(--text);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rename-editor-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 6px;
}

.result-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-empty {
  padding: 24px 12px;
  color: var(--muted);
  text-align: center;
  font-size: 12px;
}

.overlap-info-cards {
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
  font-size: calc(12rem / 14);
  color: var(--muted);
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
  font-size: calc(12rem / 14);
  color: var(--text);
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
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 7px 8px;
  background: color-mix(in srgb, var(--surface) 90%, var(--bg));
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.gis-info-card .label {
  font-size: calc(11rem / 14);
  color: var(--muted);
  line-height: 1.2;
}

.gis-info-card strong {
  font-size: calc(15rem / 14);
  color: var(--text);
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
  color: var(--muted);
  font-size: calc(12rem / 14);
}

.hint-text {
  margin: 0;
  color: var(--muted);
  font-size: calc(12rem / 14);
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
  background: var(--surface);
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

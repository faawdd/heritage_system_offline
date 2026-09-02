<template>
  <section class="project-detail" v-loading="loading">
    <header class="page-header">
      <div class="title-row">
        <h1>{{ detail.project_name || '项目详情' }}</h1>
        <el-tag :type="statusTagType" effect="dark">{{ detail.status_label || '-' }}</el-tag>
        <el-tag v-if="guide.path_label" :type="pathTagType" effect="plain">{{ guide.path_label }}</el-tag>
        <el-tag v-if="detail.has_high_level_overlap" type="danger">涉及自治区及以上级别文物</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="goList">返回列表</el-button>
        <el-button type="primary" :loading="loading" @click="loadDetail">刷新</el-button>
      </div>
    </header>

    <div class="card">
      <el-descriptions :column="4" size="small" border>
        <el-descriptions-item label="项目单位">{{ detail.company_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来函日期">{{ detail.incoming_doc_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="收文日期">{{ detail.receive_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="现场勘查日期">{{ detail.field_check_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="县局请示文号">{{ detail.shanshan_request_num || '-' }}</el-descriptions-item>
        <el-descriptions-item label="市局复函文号">{{ detail.city_reply_num || '-' }}</el-descriptions-item>
        <el-descriptions-item label="考古请示文号">{{ detail.archaeology_request_num || '-' }}</el-descriptions-item>
        <el-descriptions-item label="给项目方复函号">{{ detail.final_reply_to_company || '-' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="card">
      <el-steps :active="activeStepIndex" align-center finish-status="success">
        <el-step
          v-for="step in guide.steps || []"
          :key="step.key"
          :title="step.title"
          :description="step.state === 'skipped' ? '本流程不涉及' : step.description"
          :status="elStepStatus(step)"
        />
      </el-steps>
    </div>

    <div class="detail-body">
      <main class="detail-main">
        <div class="card">
          <div class="card-title">
            <h3>当前待办</h3>
            <span class="advice">{{ guide.advice }}</span>
          </div>

          <el-empty
            v-if="!todos.length"
            :description="guide.is_archived ? '项目已办结归档，无待办事项' : '当前无可执行动作'"
            :image-size="60"
          />

          <div v-for="todo in todos" :key="todo.action" class="todo-card">
            <div class="todo-head">
              <strong>{{ todo.label }}</strong>
              <el-button
                :type="todo.kind === 'spatial' ? 'warning' : 'primary'"
                :disabled="!todo.enabled"
                :loading="processing"
                @click="runTodo(todo)"
              >执行</el-button>
            </div>
            <p class="todo-desc">{{ todo.description }}</p>

            <el-alert
              v-for="blocker in todo.blockers"
              :key="blocker"
              :title="blocker"
              type="warning"
              :closable="false"
              show-icon
              class="blocker"
            />

            <div class="field-grid" v-if="todo.fields?.length">
              <div v-for="field in todo.fields" :key="field.name" class="field-item">
                <label>
                  {{ field.label }}
                  <span v-if="field.required" class="required">*</span>
                </label>
                <el-checkbox
                  v-if="field.type === 'checkbox'"
                  v-model="formState[todo.action][field.name]"
                >{{ field.hint || '是' }}</el-checkbox>
                <el-date-picker
                  v-else-if="field.type === 'date'"
                  v-model="formState[todo.action][field.name]"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="选择日期"
                  style="width: 100%"
                />
                <el-input-number
                  v-else-if="field.type === 'number'"
                  v-model="formState[todo.action][field.name]"
                  :min="1"
                  :max="5000"
                  style="width: 100%"
                />
                <el-input
                  v-else
                  v-model="formState[todo.action][field.name]"
                  :type="field.type === 'textarea' ? 'textarea' : 'text'"
                  :rows="2"
                  :placeholder="field.placeholder"
                />
                <span v-if="field.hint && field.type !== 'checkbox'" class="hint">{{ field.hint }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <h3>叠加核验结果</h3>
            <div>
              <el-button v-if="detail.kml_record_id" link type="primary" @click="openKmlCheckPage">
                在 KML 叠加检查中打开
              </el-button>
              <el-button link type="primary" @click="linkDialogVisible = true">关联已有叠加检查记录</el-button>
            </div>
          </div>

          <el-alert
            v-if="!detail.kml_file_path"
            title="尚未上传项目选址KML/KMZ，请先在下方「附件与文档」上传后再执行核验"
            type="info"
            :closable="false"
            show-icon
          />

          <template v-else>
            <div class="stats-row">
              <div class="stat"><span>核验时间</span><strong>{{ detail.spatial_check_at || '尚未核验' }}</strong></div>
              <div class="stat"><span>缓冲阈值</span><strong>{{ detail.spatial_check_threshold_m }} 米</strong></div>
              <div class="stat"><span>项目要素</span><strong>{{ detail.spatial_feature_count || 0 }} 个</strong></div>
              <div class="stat">
                <span>涉及文物</span>
                <strong :class="{ danger: detail.is_overlap_artifact }">{{ overlapRows.length }} 处</strong>
              </div>
            </div>

            <el-table v-if="overlapRows.length" :data="overlapRows" size="small" border max-height="280">
              <el-table-column prop="heritage_name" label="文物名称" min-width="160" />
              <el-table-column label="保护级别" width="190">
                <template #default="{ row }">
                  <el-tag :type="row.is_high_level_protected ? 'danger' : 'warning'" size="small">
                    {{ row.site_level_label || '-' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="zone_type" label="叠加关系" width="140" />
              <el-table-column prop="distance_m" label="距离(米)" width="100" />
              <el-table-column prop="feature_name" label="项目要素" min-width="140" />
            </el-table>
            <el-empty
              v-else-if="detail.spatial_check_at"
              description="核验未发现涉及已登记文物"
              :image-size="60"
            />

            <div class="map-box" v-if="detail.kml_record_id">
              <KmlOverlayMap :selected-records="mapRecords" :conflict-rows="detail.map_conflicts || []" />
            </div>
          </template>
        </div>

        <div class="card">
          <h3>附件与文档</h3>
          <div class="action-row">
            <el-select v-model="upload.file_type" style="width: 230px">
              <el-option label="项目选址(KML/KMZ)" value="kml" />
              <el-option label="现场勘查照片" value="field_photo" />
              <el-option label="杂项ZIP" value="misc_zip" />
              <el-option label="考古调查报告PDF" value="archaeology_report" />
              <el-option label="坎儿井保护加固方案PDF" value="kanerjing_plan" />
            </el-select>
            <input ref="fileInputRef" type="file" @change="onFileChange" />
            <el-input v-model="upload.note" placeholder="附件说明（可选）" style="max-width: 220px" />
            <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
            <el-button v-if="detail.misc_zip_url" @click="downloadMiscZip">下载杂项ZIP</el-button>
          </div>

          <div class="attach-list">
            <el-tag v-if="detail.kml_file_path" type="success" size="small">选址KML 已上传</el-tag>
            <el-tag v-if="detail.archaeology_report_path" type="success" size="small">考古报告 已上传</el-tag>
            <el-tag v-if="detail.kanerjing_protection_plan_path" type="success" size="small">坎儿井方案 已上传</el-tag>
            <el-tag size="small">现场照片 {{ (detail.field_photos || []).length }} 张</el-tag>
          </div>

          <div class="photo-grid" v-if="(detail.field_photos || []).length">
            <a v-for="photo in detail.field_photos" :key="photo.id" :href="photo.photo_url" target="_blank">
              <img :src="photo.photo_url" :alt="photo.note || '现场照片'" />
            </a>
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <h3>补充信息</h3>
            <el-button :loading="processing" @click="saveExtraInfo">保存补充信息</el-button>
          </div>
          <div class="field-grid">
            <div v-for="field in extraFields" :key="field.name" class="field-item">
              <label>{{ field.label }}</label>
              <el-checkbox v-if="field.type === 'checkbox'" v-model="extraState[field.name]">
                {{ field.hint || '是' }}
              </el-checkbox>
              <el-input
                v-else
                v-model="extraState[field.name]"
                :type="field.type === 'textarea' ? 'textarea' : 'text'"
                :rows="2"
                :placeholder="field.placeholder"
              />
              <span v-if="field.hint && field.type !== 'checkbox'" class="hint">{{ field.hint }}</span>
            </div>
          </div>
        </div>

        <div class="card">
          <h3>公文生成</h3>
          <OfficialDocumentGenerator :project-id="projectId" :project-detail="detail" />
        </div>
      </main>

      <aside class="detail-side card">
        <h3>办理记录</h3>
        <el-timeline v-if="timelineEvents.length">
          <el-timeline-item
            v-for="(event, index) in timelineEvents"
            :key="event.id || index"
            :timestamp="event.created_at || '-'"
            :type="index === 0 ? 'primary' : 'info'"
          >
            <div class="timeline-title">{{ event.action_label || event.action || '流程操作' }}</div>
            <div class="timeline-detail">
              <span>操作人：{{ event.operator || '-' }}</span>
              <span v-if="event.status_after">{{ event.status_before || '-' }} → {{ event.status_after }}</span>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无办理记录" :image-size="60" />
      </aside>
    </div>

    <el-dialog v-model="linkDialogVisible" title="关联已有 KML 叠加检查记录" width="640px" @open="loadKmlRecords">
      <el-table
        :data="kmlRecords"
        size="small"
        border
        highlight-current-row
        max-height="360"
        @current-change="(row) => (selectedKmlRecord = row)"
      >
        <el-table-column prop="title" label="记录名称" min-width="200" />
        <el-table-column prop="feature_count" label="要素数" width="90" />
        <el-table-column prop="conflict_count" label="冲突数" width="90" />
        <el-table-column prop="created_at" label="上传时间" width="160" />
      </el-table>
      <template #footer>
        <el-button @click="linkDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedKmlRecord" :loading="processing" @click="submitLinkRecord">
          关联到本项目
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import {
  fetchProjectDetail,
  linkProjectKmlRecord,
  runProjectWorkflowAction,
  uploadProjectFile,
  verifyProjectSpatialSafety
} from '../../api/projectApi'
import { fetchGisKmlRecords } from '../../api/gisApi'
import KmlOverlayMap from '../../components/gis/KmlOverlayMap.vue'
import OfficialDocumentGenerator from '../../components/projects/OfficialDocumentGenerator.vue'

const route = useRoute()
const router = useRouter()

const projectId = route.params.projectId
const loading = ref(false)
const uploading = ref(false)
const processing = ref(false)
const selectedFile = ref(null)
const fileInputRef = ref(null)

const detail = reactive({})
const guide = reactive({ steps: [], todos: [], advice: '', extra_info_form: { fields: [] } })
const formState = reactive({})
const extraState = reactive({})
const upload = reactive({ file_type: 'kml', note: '' })

const linkDialogVisible = ref(false)
const kmlRecords = ref([])
const selectedKmlRecord = ref(null)

const todos = computed(() => guide.todos || [])
const extraFields = computed(() => guide.extra_info_form?.fields || [])
const overlapRows = computed(() => detail.overlapped_relics_info || [])
const timelineEvents = computed(() => detail.operation_logs || [])

const mapRecords = computed(() => (
  detail.kml_record_id
    ? [{ id: detail.kml_record_id, title: detail.project_name || '项目选址' }]
    : []
))

const statusTagType = computed(() => {
  if (String(detail.status || '').startsWith('60')) return 'success'
  if (detail.has_high_level_overlap) return 'danger'
  if (detail.is_overlap_artifact) return 'warning'
  return 'info'
})

const pathTagType = computed(() => {
  if (guide.path === 'ARCHAEOLOGY_FLOW') return 'warning'
  if (guide.path === 'PENDING') return 'info'
  return 'success'
})

const activeStepIndex = computed(() => {
  const steps = guide.steps || []
  const index = steps.findIndex((step) => step.state === 'current')
  return index >= 0 ? index : steps.length
})

function elStepStatus(step) {
  if (step.state === 'done') return 'success'
  if (step.state === 'current') return 'process'
  if (step.state === 'skipped') return 'finish'
  return 'wait'
}

function goList() {
  router.push('/projects')
}

function openKmlCheckPage() {
  router.push({ path: '/gis/kml-management', query: { record: detail.kml_record_id } })
}

function onFileChange(event) {
  selectedFile.value = event.target.files?.[0] || null
}

function syncFormState() {
  Object.keys(formState).forEach((key) => delete formState[key])
  todos.value.forEach((todo) => {
    formState[todo.action] = {}
    ;(todo.fields || []).forEach((field) => {
      formState[todo.action][field.name] = field.value
    })
  })

  Object.keys(extraState).forEach((key) => delete extraState[key])
  extraFields.value.forEach((field) => {
    extraState[field.name] = field.value
  })
}

async function loadDetail() {
  loading.value = true
  try {
    const result = await fetchProjectDetail(projectId)
    if (!result.success) {
      throw new Error(result.message || '加载项目详情失败')
    }
    Object.keys(detail).forEach((key) => delete detail[key])
    Object.assign(detail, result.data || {})
    Object.assign(guide, result.data?.guide || {})
    syncFormState()
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function validateTodo(todo) {
  const values = formState[todo.action] || {}
  const missing = (todo.fields || [])
    .filter((field) => {
      if (!field.required) return false
      const value = values[field.name]
      return value === '' || value === null || value === undefined
    })
    .map((field) => field.label)

  if (missing.length) {
    ElMessage.warning(`请先填写：${missing.join('、')}`)
    return false
  }
  return true
}

async function runSpatialVerify(thresholdM) {
  processing.value = true
  try {
    const result = await verifyProjectSpatialSafety(projectId, thresholdM)
    if (!result.success) {
      throw new Error(result.message || '空间核验失败')
    }
    const data = result.data || {}
    ElMessage.success(
      data.is_overlap_artifact
        ? `核验完成：涉及 ${(data.overlapped_relics_info || []).length} 处文物`
        : '核验完成：未涉及已登记文物'
    )
    await loadDetail()
  } catch (error) {
    ElMessage.error(error?.message || '空间核验失败')
  } finally {
    processing.value = false
  }
}

async function runTodo(todo) {
  if (!validateTodo(todo)) {
    return
  }

  if (todo.kind === 'spatial') {
    await runSpatialVerify(formState[todo.action]?.threshold_m)
    return
  }

  processing.value = true
  try {
    const result = await runProjectWorkflowAction(projectId, {
      action: todo.action,
      ...(formState[todo.action] || {})
    })
    if (!result.success) {
      throw new Error(result.message || '流程动作执行失败')
    }
    ElMessage.success(`${todo.label} 已完成`)
    await loadDetail()
  } catch (error) {
    ElMessage.error(error?.message || '流程动作执行失败')
  } finally {
    processing.value = false
  }
}

async function saveExtraInfo() {
  processing.value = true
  try {
    const result = await runProjectWorkflowAction(projectId, {
      action: 'update_extra_info',
      ...extraState
    })
    if (!result.success) {
      throw new Error(result.message || '保存失败')
    }
    ElMessage.success('补充信息已保存')
    await loadDetail()
  } catch (error) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    processing.value = false
  }
}

async function submitUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('file_type', upload.file_type)
  if (upload.note) {
    formData.append('note', upload.note)
  }

  uploading.value = true
  try {
    const result = await uploadProjectFile(projectId, formData)
    if (!result.success) {
      throw new Error(result.message || '上传失败')
    }
    ElMessage.success(
      upload.file_type === 'kml' ? '选址KML已上传，并同步生成叠加检查记录' : '上传成功'
    )
    selectedFile.value = null
    if (fileInputRef.value) {
      fileInputRef.value.value = ''
    }
    upload.note = ''
    await loadDetail()
  } catch (error) {
    ElMessage.error(error?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

function downloadMiscZip() {
  if (detail.misc_zip_url) {
    window.open(detail.misc_zip_url, '_blank')
  }
}

async function loadKmlRecords() {
  try {
    const result = await fetchGisKmlRecords()
    kmlRecords.value = result?.rows || result?.data?.rows || []
  } catch (error) {
    ElMessage.error(error?.message || '加载叠加检查记录失败')
  }
}

async function submitLinkRecord() {
  if (!selectedKmlRecord.value) {
    return
  }

  try {
    await ElMessageBox.confirm(
      '关联后本项目的选址范围将改用该叠加检查记录的KML文件，是否继续？',
      '关联确认',
      { confirmButtonText: '确认关联', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  processing.value = true
  try {
    const result = await linkProjectKmlRecord(projectId, selectedKmlRecord.value.id)
    if (!result.success) {
      throw new Error(result.message || '关联失败')
    }
    ElMessage.success('已关联，请执行叠加核验刷新结论')
    linkDialogVisible.value = false
    selectedKmlRecord.value = null
    await loadDetail()
  } catch (error) {
    ElMessage.error(error?.message || '关联失败')
  } finally {
    processing.value = false
  }
}

watch(() => guide.todos, syncFormState)

loadDetail()
</script>

<style scoped>
.project-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.title-row h1 {
  margin: 0;
  font-size: 22px;
}

.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
}

.card h3 {
  margin: 0 0 12px;
  font-size: 16px;
}

.card-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.card-title h3 {
  margin: 0;
}

.advice {
  color: #64748b;
  font-size: 13px;
}

.detail-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 14px;
  align-items: start;
}

.detail-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.todo-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
  background: #f8fafc;
}

.todo-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.todo-desc {
  margin: 6px 0 10px;
  color: #64748b;
  font-size: 13px;
}

.blocker {
  margin-bottom: 8px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

.field-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-item label {
  font-size: 13px;
  color: #334155;
}

.required {
  color: #ef4444;
}

.hint {
  font-size: 12px;
  color: #94a3b8;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
}

.stat span {
  font-size: 12px;
  color: #64748b;
}

.stat strong {
  font-size: 16px;
}

.stat strong.danger {
  color: #ef4444;
}

.map-box {
  height: 420px;
  margin-top: 12px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}

.map-box :deep(.kml-overlay-map-wrap),
.map-box :deep(.kml-overlay-map) {
  height: 100%;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.attach-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.photo-grid img {
  width: 100%;
  height: 90px;
  object-fit: cover;
  border-radius: 6px;
}

.detail-side {
  position: sticky;
  top: 12px;
  max-height: calc(100vh - 40px);
  overflow-y: auto;
}

.timeline-title {
  font-weight: 600;
  font-size: 13px;
}

.timeline-detail {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: #64748b;
  font-size: 12px;
}

@media (max-width: 1100px) {
  .detail-body {
    grid-template-columns: 1fr;
  }

  .detail-side {
    position: static;
    max-height: none;
  }
}
</style>

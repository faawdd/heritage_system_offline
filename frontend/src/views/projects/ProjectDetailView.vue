<template>
  <section class="workflow-page" v-loading="loading">
    <header class="page-header">
      <h1>建设项目流程详情</h1>
      <p>流程导航、当前步骤内容与时间轴记录三栏联动</p>
    </header>

    <div class="toolbar card">
      <el-button @click="goList">返回列表</el-button>
      <el-button type="primary" :loading="loading" @click="loadDetail">刷新</el-button>
    </div>

    <div class="card header-card">
      <div class="header-grid">
        <div><span>项目名称</span><strong>{{ detail.project_name || '-' }}</strong></div>
        <div><span>项目编号</span><strong>{{ detail.project_code || detail.id || '-' }}</strong></div>
        <div><span>状态</span><strong>{{ detail.status_label || '-' }}</strong></div>
        <div><span>负责人</span><strong>{{ detail.owner_name || detail.operator || '-' }}</strong></div>
        <div><span>项目位置</span><strong>{{ detail.location_name || detail.address || '-' }}</strong></div>
        <div><span>项目类型</span><strong>{{ detail.project_type || '-' }}</strong></div>
        <div><span>建设单位</span><strong>{{ detail.company_name || '-' }}</strong></div>
        <div><span>文号</span><strong>{{ detail.shanshan_request_num || detail.city_reply_num || '-' }}</strong></div>
        <div><span>收文日期</span><strong>{{ detail.receive_date || '-' }}</strong></div>
      </div>
    </div>

    <div class="workflow-three-pane">
      <aside class="pane-left card">
        <h3>流程导航</h3>
        <ul class="step-nav">
          <li
            v-for="(step, index) in navSteps"
            :key="step.key"
            class="step-item"
            :class="stepClass(index)"
            @click="activeStep = step.key"
          >
            <span class="dot"></span>
            <span>{{ step.label }}</span>
          </li>
        </ul>
      </aside>

      <main class="pane-middle">
        <div class="card pane-card" v-show="activeStep === 'receive'">
          <h3>接收请示 / 收文登记</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="项目名称">{{ detail.project_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="企业单位">{{ detail.company_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="来函日期">{{ detail.incoming_doc_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="收文日期">{{ detail.receive_date || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="card pane-card" v-show="activeStep === 'survey'">
          <h3>空间核验 / 现场勘查</h3>
          <div class="action-row">
            <el-input v-model="workflow.field_check_date" placeholder="勘查日期 YYYY-MM-DD" style="max-width: 220px" />
            <el-button
              type="warning"
              :disabled="!controls.verify_spatial"
              :loading="processing"
              @click="runSpatialVerify"
            >执行空间核验</el-button>
          </div>
        </div>

        <div class="card pane-card" v-show="activeStep === 'approval'">
          <h3>上报市局</h3>
          <div class="workflow-grid compact">
            <el-input v-model="workflow.shanshan_request_num" placeholder="县局请示文号" />
            <el-input v-model="workflow.archaeology_request_num" placeholder="考古请示文号（后续可用）" />
            <el-button type="primary" :loading="processing" @click="executeAction('submit_city_request')">提交市局上报</el-button>
          </div>
        </div>

        <div class="card pane-card" v-show="activeStep === 'reply'">
          <h3>复函项目方</h3>
          <div class="workflow-grid compact">
            <el-input v-model="workflow.city_reply_num" placeholder="市局复函号（有则填写）" />
            <el-input v-model="workflow.final_reply_to_company" placeholder="给企业最终复函号" />
            <el-button type="primary" :loading="processing" @click="executeAction('record_city_reply')">录入复函结果</el-button>
          </div>
        </div>

        <div class="card pane-card" v-show="activeStep === 'decision'">
          <h3>涉及性与可行性判定</h3>
          <el-radio-group v-model="decisionType" class="decision-group">
            <el-radio label="NO_HERITAGE">不涉及文物</el-radio>
            <el-radio label="IMMOVABLE_HERITAGE">涉及不可移动文物</el-radio>
            <el-radio label="PROTECTION_ZONE">涉及保护范围</el-radio>
            <el-radio label="CONTROL_ZONE">涉及建设控制地带</el-radio>
            <el-radio label="UNDERGROUND_HERITAGE">涉及地下文物</el-radio>
            <el-radio label="NEED_MORE_INVESTIGATION">需要进一步调查</el-radio>
          </el-radio-group>
          <div class="action-row">
            <el-button type="primary" @click="applyDecisionBranch">应用后续流程建议</el-button>
            <span class="hint">当前建议动作：{{ workflow.action || '未选择' }}</span>
          </div>
          <div class="hint top-space">{{ detail.workflow_advice || '请先执行空间核验，再依据文物级别判断后续流程。' }}</div>
        </div>

        <div class="card pane-card" v-show="activeStep === 'followup'">
          <h3>考古调查与批复</h3>
          <div class="workflow-grid compact">
            <el-input v-model="workflow.archaeology_request_num" placeholder="考古请示文号" />
            <el-input v-model="workflow.region_approval_num" placeholder="自治区批复文号" />
            <el-button type="primary" :loading="processing" @click="executeAction('submit_archaeology_request')">发起后续流程</el-button>
          </div>
        </div>

        <div class="card pane-card" v-show="activeStep === 'archive'">
          <h3>办结归档</h3>
          <div class="action-row">
            <el-button type="primary" :loading="processing" @click="executeAction('archive_case')">办结归档</el-button>
          </div>
        </div>

        <div class="card pane-card">
          <h3>附件与文档</h3>
          <div class="action-row">
            <el-select v-model="upload.file_type" style="width: 220px">
              <el-option label="请示文件(KML/KMZ)" value="kml" />
              <el-option label="现场照片" value="field_photo" />
              <el-option label="杂项ZIP" value="misc_zip" />
              <el-option label="考古报告PDF" value="archaeology_report" />
            </el-select>
            <input type="file" @change="onFileChange" />
            <el-input v-model="upload.note" placeholder="附件说明（可选）" style="max-width: 240px" />
            <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
            <el-button v-if="detail.misc_zip_url" type="success" @click="downloadMiscZip">下载杂项ZIP</el-button>
          </div>

          <OfficialDocumentGenerator :project-id="projectId" :project-detail="detail" />
        </div>

        <div class="card pane-card">
          <h3>流程动作执行</h3>
          <div class="workflow-grid compact">
            <el-select v-model="workflow.action" placeholder="选择流程动作" style="width: 280px">
              <el-option label="提交现场勘查完成" value="complete_field_check" />
              <el-option label="录入县局请示并提交市局" value="submit_city_request" />
              <el-option label="发起考古流转" value="submit_archaeology_request" />
              <el-option label="录入考古与批复结果" value="record_archaeology_reply" />
              <el-option label="录入复函结果（含直接复函）" value="record_city_reply" />
              <el-option label="办结归档" value="archive_case" />
            </el-select>
            <el-button type="primary" :loading="processing" @click="runWorkflowAction">执行流程动作</el-button>
          </div>
        </div>
      </main>

      <aside class="pane-right card">
        <h3>时间轴</h3>
        <el-timeline>
          <el-timeline-item
            v-for="(event, index) in timelineEvents"
            :key="`${event.created_at || index}-${event.action_label || index}`"
            :timestamp="event.created_at || '-'"
            :type="index === 0 ? 'primary' : 'info'"
          >
            <div class="timeline-title">{{ event.action_label || event.event_title || '流程操作' }}</div>
            <div class="timeline-detail">
              <span>操作人：{{ event.operator || '-' }}</span>
              <span>所属环节：{{ event.stageLabel || '流程处理' }}</span>
              <span v-if="event.status_before || event.status_after">状态：{{ event.status_before || '-' }} → {{ event.status_after || '-' }}</span>
            </div>
          </el-timeline-item>
        </el-timeline>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import {
  fetchProjectControls,
  fetchProjectDetail,
  runProjectWorkflowAction,
  uploadProjectFile,
  verifyProjectSpatialSafety
} from '../../api/projectApi'
import OfficialDocumentGenerator from '../../components/projects/OfficialDocumentGenerator.vue'

const route = useRoute()
const router = useRouter()

const projectId = route.params.projectId
const loading = ref(false)
const uploading = ref(false)
const processing = ref(false)
const selectedFile = ref(null)
const activeStep = ref('receive')
const decisionType = ref('NO_HERITAGE')

const detail = reactive({})
const controls = reactive({})
const upload = reactive({
  file_type: 'kml',
  note: ''
})
const workflow = reactive({
  action: '',
  field_check_date: '',
  shanshan_request_num: '',
  city_reply_num: '',
  archaeology_request_num: '',
  region_approval_num: '',
  city_final_reply_num: '',
  final_reply_to_company: ''
})

function goList() {
  router.push('/projects')
}

function onFileChange(event) {
  const file = event.target.files?.[0]
  selectedFile.value = file || null
}

function fillReactive(target, source) {
  Object.keys(target).forEach((key) => {
    delete target[key]
  })
  Object.keys(source || {}).forEach((key) => {
    target[key] = source[key]
  })
}

const baseStepMeta = [
  { key: 'receive', label: '接收请示 / 收文登记' },
  { key: 'survey', label: '空间核验 / 现场勘查' },
  { key: 'decision', label: '涉及性与可行性判定' },
  { key: 'approval', label: '上报市局' },
  { key: 'followup', label: '考古调查与批复' },
  { key: 'reply', label: '复函项目方' },
  { key: 'archive', label: '办结归档' }
]

const actionStepMap = {
  create: 'receive',
  upload_kml: 'survey',
  verify_spatial_safety: 'decision',
  complete_field_check: 'survey',
  submit_city_request: 'approval',
  submit_archaeology_request: 'followup',
  record_archaeology_reply: 'followup',
  record_city_reply: 'reply',
  archive_case: 'archive',
  generate_official_document: 'reply'
}

const stepLabelMap = {
  receive: '接收请示 / 收文登记',
  survey: '空间核验 / 现场勘查',
  decision: '涉及性与可行性判定',
  approval: '上报市局',
  followup: '考古调查与批复',
  reply: '复函项目方',
  archive: '办结归档'
}

const navSteps = computed(() => {
  const overlap = Boolean(detail.is_overlap_artifact)
  const feasible = Boolean(detail.is_feasible_by_level)
  const keys = ['receive', 'survey', 'decision']

  if (overlap && feasible) {
    keys.push('approval', 'followup')
  }
  keys.push('reply', 'archive')

  return keys.map((key, index) => ({
    key,
    label: `${index + 1}. ${stepLabelMap[key]}`
  }))
})

function statusRaw() {
  return String(detail.status || detail.status_label || '').trim()
}

function detectStepKeyFromStatus() {
  const status = statusRaw()
  if (status.includes('60_')) return 'archive'
  if (status.includes('50_')) return 'reply'
  if (status.includes('45_')) return 'followup'
  if (status.includes('40_')) return 'approval'
  if (status.includes('30_')) return 'survey'
  if (status.includes('20_') || status.includes('21_')) return 'decision'
  return 'receive'
}

const currentStepIndex = computed(() => {
  const key = detectStepKeyFromStatus()
  const index = navSteps.value.findIndex((step) => step.key === key)
  if (index >= 0) {
    return index
  }

  if (key === 'followup' && !navSteps.value.some((step) => step.key === 'followup')) {
    return Math.max(0, navSteps.value.findIndex((step) => step.key === 'reply'))
  }
  if (key === 'approval' && !navSteps.value.some((step) => step.key === 'approval')) {
    return Math.max(0, navSteps.value.findIndex((step) => step.key === 'reply'))
  }
  return 0
})

function stepClass(index) {
  if (index < currentStepIndex.value) return 'is-done'
  if (index === currentStepIndex.value) return 'is-active'
  return 'is-pending'
}

const timelineEvents = computed(() => {
  return [...(detail.operation_logs || [])].sort((a, b) => {
    const t1 = new Date(a?.created_at || 0).getTime()
    const t2 = new Date(b?.created_at || 0).getTime()
    return t2 - t1
  }).map((event) => {
    const stageKey = actionStepMap[event?.action] || detectStepKeyFromStatus()
    return {
      ...event,
      stageKey,
      stageLabel: stepLabelMap[stageKey] || '流程处理'
    }
  })
})

async function loadDetail() {
  loading.value = true
  try {
    const [detailRes, controlsRes] = await Promise.all([
      fetchProjectDetail(projectId),
      fetchProjectControls(projectId)
    ])
    if (!detailRes.success) {
      throw new Error(detailRes.message || '加载项目详情失败')
    }
    if (!controlsRes.success) {
      throw new Error(controlsRes.message || '加载按钮权限失败')
    }
    fillReactive(detail, detailRes.data || {})
    fillReactive(controls, controlsRes.controls || {})
    const detected = detectStepKeyFromStatus()
    activeStep.value = navSteps.value.some((step) => step.key === detected)
      ? detected
      : (navSteps.value[0]?.key || 'receive')

    if (!workflow.action) {
      applyDecisionBranch(false)
    }
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function applyDecisionBranch(showMessage = true) {
  const overlap = Boolean(detail.is_overlap_artifact)
  const feasible = Boolean(detail.is_feasible_by_level)

  if (!overlap || decisionType.value === 'NO_HERITAGE') {
    workflow.action = 'record_city_reply'
  } else if (feasible) {
    workflow.action = 'submit_city_request'
  } else {
    workflow.action = 'record_city_reply'
  }

  if (showMessage) {
    ElMessage.success(`已应用分支建议：${workflow.action || '未匹配动作'}`)
  }
}

async function executeAction(action) {
  workflow.action = action
  await runWorkflowAction()
}

async function submitUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('file_type', upload.file_type)
  if (upload.file_type === 'field_photo' && upload.note) {
    formData.append('note', upload.note)
  }

  uploading.value = true
  try {
    const result = await uploadProjectFile(projectId, formData)
    if (!result.success) {
      throw new Error(result.message || '上传失败')
    }
    ElMessage.success('上传成功')
    selectedFile.value = null
    await loadDetail()
  } catch (error) {
    ElMessage.error(error?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function runSpatialVerify() {
  processing.value = true
  try {
    const result = await verifyProjectSpatialSafety(projectId)
    if (!result.success) {
      throw new Error(result.message || '空间核验失败')
    }
    ElMessage.success('空间核验完成')
    await loadDetail()
  } catch (error) {
    ElMessage.error(error?.message || '空间核验失败')
  } finally {
    processing.value = false
  }
}

async function runWorkflowAction() {
  if (!workflow.action) {
    ElMessage.warning('请选择流程动作')
    return
  }

  processing.value = true
  try {
    const payload = { ...workflow }
    const result = await runProjectWorkflowAction(projectId, payload)
    if (!result.success) {
      throw new Error(result.message || '流程动作执行失败')
    }
    ElMessage.success('流程动作执行成功')
    await loadDetail()
  } catch (error) {
    ElMessage.error(error?.message || '流程动作执行失败')
  } finally {
    processing.value = false
  }
}

function downloadMiscZip() {
  if (!detail.misc_zip_url) {
    ElMessage.warning('当前项目没有可下载的杂项ZIP')
    return
  }
  window.open(detail.misc_zip_url, '_blank')
}

loadDetail()
</script>

<style scoped>
.workflow-page {
  display: grid;
  gap: 14px;
}

.header-card {
  padding: 12px 14px;
}

.header-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 14px;
}

.header-grid div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
}

.header-grid span {
  color: #64748b;
}

.workflow-three-pane {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 300px;
  gap: 12px;
  min-height: 620px;
}

.pane-left,
.pane-right {
  padding: 12px;
  overflow: auto;
}

.pane-left h3,
.pane-right h3 {
  margin: 0 0 10px;
  font-size: 15px;
}

.pane-middle {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.pane-card {
  padding: 12px;
}

.pane-card h3 {
  margin: 0 0 12px;
  font-size: 15px;
}

.step-nav {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  font-size: 13px;
}

.step-item .dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #94a3b8;
}

.step-item.is-active {
  border-color: #60a5fa;
  background: #eaf3ff;
  color: #0f3d73;
}

.step-item.is-active .dot {
  background: #3b82f6;
}

.step-item.is-done {
  border-color: #86efac;
  background: #effdf3;
}

.step-item.is-done .dot {
  background: #16a34a;
}

.step-item.is-pending {
  color: #64748b;
}

.timeline-title {
  font-weight: 600;
  font-size: 13px;
}

.timeline-detail {
  margin-top: 4px;
  display: grid;
  gap: 3px;
  font-size: 12px;
  color: #64748b;
}

.decision-group {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
}

.hint {
  color: #64748b;
  font-size: 13px;
}

.workflow-grid.compact {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.doc-actions {
  margin-top: 12px;
}

@media (max-width: 1450px) {
  .workflow-three-pane {
    grid-template-columns: 220px minmax(0, 1fr);
  }

  .pane-right {
    grid-column: 1 / -1;
  }
}

@media (max-width: 980px) {
  .header-grid {
    grid-template-columns: 1fr;
  }

  .workflow-three-pane {
    grid-template-columns: 1fr;
  }

  .workflow-grid.compact {
    grid-template-columns: 1fr;
  }
}
</style>

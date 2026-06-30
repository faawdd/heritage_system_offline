<template>
  <section>
    <header class="page-header">
      <h1>项目详情</h1>
      <p>流程状态、文件归档、空间核验与流转动作</p>
    </header>

    <div class="toolbar card">
      <el-button @click="goList">返回列表</el-button>
      <el-button type="primary" :loading="loading" @click="loadDetail">刷新</el-button>
    </div>

    <div class="card" v-loading="loading">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="项目名称">{{ detail.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="企业单位">{{ detail.company_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来函日期">{{ detail.incoming_doc_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="收文日期">{{ detail.receive_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="当前状态">{{ detail.status_label || '-' }}</el-descriptions-item>
        <el-descriptions-item label="涉及文物">{{ detail.is_overlap_artifact ? '是' : '否' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="card">
      <h3>文件上传</h3>
      <div class="action-row">
        <el-select v-model="upload.file_type" style="width: 220px">
          <el-option label="KML/KMZ" value="kml" />
          <el-option label="现场照片" value="field_photo" />
          <el-option label="杂项ZIP" value="misc_zip" />
          <el-option label="考古报告PDF" value="archaeology_report" />
        </el-select>
        <input type="file" @change="onFileChange" />
        <el-input v-model="upload.note" placeholder="现场照片备注（可选）" style="max-width: 240px" />
        <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
        <el-button
          v-if="detail.misc_zip_url"
          type="success"
          @click="downloadMiscZip"
        >下载杂项ZIP</el-button>
      </div>
    </div>

    <div class="card">
      <h3>空间核验与流程操作</h3>
      <div class="action-row">
        <el-button
          type="warning"
          :disabled="!controls.verify_spatial"
          :loading="processing"
          @click="runSpatialVerify"
        >执行空间核验</el-button>
      </div>

      <div class="workflow-grid">
        <el-select v-model="workflow.action" placeholder="选择流程动作" style="width: 280px">
          <el-option label="提交现场勘查完成" value="complete_field_check" />
          <el-option label="录入县局请示并提交市局" value="submit_city_request" />
          <el-option label="录入市局复函" value="record_city_reply" />
          <el-option label="发起考古流转" value="submit_archaeology_request" />
          <el-option label="录入考古与批复结果" value="record_archaeology_reply" />
          <el-option label="办结归档" value="archive_case" />
        </el-select>
        <el-input v-model="workflow.field_check_date" placeholder="现场勘查日期 YYYY-MM-DD" />
        <el-input v-model="workflow.shanshan_request_num" placeholder="县局请示文号" />
        <el-input v-model="workflow.city_reply_num" placeholder="市局复函号" />
        <el-input v-model="workflow.archaeology_request_num" placeholder="考古请示文号" />
        <el-input v-model="workflow.region_approval_num" placeholder="自治区批复文号" />
        <el-input v-model="workflow.city_final_reply_num" placeholder="市局最终复函号" />
        <el-input v-model="workflow.final_reply_to_company" placeholder="给企业最终复函号" />
        <el-button type="primary" :loading="processing" @click="runWorkflowAction">执行流程动作</el-button>
      </div>
    </div>

    <div class="card">
      <h3>操作日志</h3>
      <el-table :data="detail.operation_logs || []" stripe>
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column prop="action_label" label="动作" min-width="180" />
        <el-table-column prop="status_before" label="前状态" width="130" />
        <el-table-column prop="status_after" label="后状态" width="130" />
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import {
  fetchProjectControls,
  fetchProjectDetail,
  runProjectWorkflowAction,
  uploadProjectFile,
  verifyProjectSpatialSafety
} from '../../api/projectApi'

const route = useRoute()
const router = useRouter()

const projectId = route.params.projectId
const loading = ref(false)
const uploading = ref(false)
const processing = ref(false)
const selectedFile = ref(null)

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
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
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

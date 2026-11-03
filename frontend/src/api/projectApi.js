import client from './client'
import { MAP_REQUEST_TIMEOUT, requestMapData } from '../utils/networkRequest'

export async function fetchProjectList(params = {}) {
  const response = await client.get('/api/v1/projects/', {
    params: {
      q: params.keyword || '',
      status: params.status || '',
      workflow_path: params.workflowPath || ''
    }
  })
  return response.data
}

export async function fetchProjectDetail(projectId) {
  const response = await client.get(`/api/v1/projects/${projectId}/`)
  return response.data
}

export async function createProject(payload) {
  const response = await client.post('/api/v1/projects/create/', payload)
  return response.data
}

export async function uploadProjectFile(projectId, formData) {
  const response = await client.post(`/api/v1/projects/${projectId}/upload/`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}

export async function downloadProjectAllFilesArchive(projectId) {
  return client.get(`/api/v1/projects/${projectId}/download-all-files/`, {
    responseType: 'blob'
  })
}

export async function deleteProject(projectId, confirmName) {
  const response = await client.post(`/api/v1/projects/${projectId}/delete/`, {
    confirm_name: confirmName
  })
  return response.data
}

const SPATIAL_JOB_POLL_MS = 1500
const SPATIAL_JOB_MAX_WAIT_MS = 60 * 60 * 1000
const SPATIAL_JOB_MAX_POLL_FAILURES = 20

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// 核验在服务端后台运行，前端仅轮询进度，避免大文件分析超过请求超时。
async function runSpatialVerifyJob(projectId, params, { onProgress } = {}) {
  const base = `/api/v1/projects/${projectId}/verify-spatial-safety/`
  // 同一项目已有进行中的任务时服务端会复用，因此启动请求可以安全重试。
  const started = await requestMapData(
    () => client.post(base, null, { params: { ...params, async: '1' }, timeout: MAP_REQUEST_TIMEOUT }),
    { retries: 2 }
  )
  let job = started.data?.data
  if (!started.data?.success || !job?.job_id) {
    throw new Error(started.data?.message || '空间核验任务启动失败')
  }

  const deadline = Date.now() + SPATIAL_JOB_MAX_WAIT_MS
  let failures = 0
  while (true) {
    onProgress?.(job)
    if (job.status === 'succeeded') return { success: true, data: job.result }
    if (job.status === 'failed') throw new Error(job.error || '空间核验失败')
    if (Date.now() > deadline) throw new Error('空间核验耗时过长，请稍后刷新页面查看结果')
    await sleep(SPATIAL_JOB_POLL_MS)
    try {
      const response = await client.get(`${base}jobs/${job.job_id}/`, { timeout: MAP_REQUEST_TIMEOUT })
      failures = 0
      if (!response.data?.success) throw new Error(response.data?.message || '查询核验进度失败')
      job = response.data.data
    } catch (error) {
      if (error?.response?.status === 404) throw new Error('核验任务已过期，请刷新页面确认结果后重试')
      failures += 1
      // 弱网下偶发的进度查询失败不影响后台任务，继续轮询。
      if (failures >= SPATIAL_JOB_MAX_POLL_FAILURES) {
        throw new Error('网络不稳定，无法获取核验进度。核验仍在后台执行，请稍后刷新页面查看结果')
      }
    }
  }
}

export function verifyProjectSpatialSafety(projectId, thresholdM, options) {
  return runSpatialVerifyJob(projectId, thresholdM ? { threshold_m: thresholdM } : {}, options)
}

export function verifyPreliminarySpatialSafety(projectId, thresholdM, options) {
  const params = { preliminary: '1' }
  if (thresholdM) params.threshold_m = thresholdM
  return runSpatialVerifyJob(projectId, params, options)
}

export async function linkProjectKmlRecord(projectId, kmlRecordId) {
  const response = await client.post(`/api/v1/projects/${projectId}/link-kml-record/`, {
    kml_record_id: kmlRecordId
  })
  return response.data
}

export async function deleteProjectDocument(projectId, documentId) {
  const response = await client.post(`/api/v1/projects/${projectId}/documents/${documentId}/delete/`)
  return response.data
}

export async function downloadProjectDocumentsArchive(projectId) {
  return client.get(`/api/v1/projects/${projectId}/documents/archive/`, {
    responseType: 'blob'
  })
}

export async function runProjectWorkflowAction(projectId, payload) {
  const response = await client.post(`/api/v1/projects/${projectId}/workflow-action/`, payload)
  return response.data
}

export async function fetchProjectControls(projectId) {
  const response = await client.get(`/api/v1/projects/${projectId}/controls/`)
  return response.data
}

export async function fetchNextDocNum(year) {
  const response = await client.get('/api/v1/projects/next-shanshan-doc/', {
    params: { year }
  })
  return response.data
}

export async function generateProjectOfficialDocument(projectId, payload) {
  return client.post(`/api/v1/projects/${projectId}/documents/generate/`, payload, {
    responseType: 'blob'
  })
}

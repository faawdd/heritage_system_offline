import client from './client'
import { KML_ACTION_TIMEOUT, MAP_REQUEST_TIMEOUT, requestMapData } from '../utils/networkRequest.js'

function extractFilenameFromDisposition(disposition) {
  if (!disposition) return ''
  const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utfMatch?.[1]) {
    try {
      return decodeURIComponent(utfMatch[1])
    } catch (_error) {
      return utfMatch[1]
    }
  }
  const normalMatch = disposition.match(/filename="?([^";]+)"?/i)
  return normalMatch?.[1] || ''
}

export async function fetchGisKmlRecords() {
  const response = await requestMapData(() => client.get('/api/v1/gis/kml-records/', { timeout: MAP_REQUEST_TIMEOUT }))
  return response.data
}

export async function fetchGisKmlRecordKmlContent(recordId, { signal } = {}) {
  const response = await requestMapData(
    () => client.get(`/api/v1/gis/kml-records/${recordId}/kml-content/`, { signal, timeout: MAP_REQUEST_TIMEOUT }),
    { signal }
  )
  return response.data
}

export async function fetchGisKmlBatchKmlContent(recordIds = [], { signal } = {}) {
  const response = await requestMapData(() => client.post('/api/v1/gis/kml-records/batch-kml-content/', {
    record_ids: Array.isArray(recordIds) ? recordIds : []
  }, { signal, timeout: MAP_REQUEST_TIMEOUT }), { signal })
  return response.data
}

async function postBlobAware(url, formData, options = {}) {
  let response
  try {
    response = await client.post(url, formData, {
      ...options,
      timeout: KML_ACTION_TIMEOUT,
      responseType: 'blob'
    })
  } catch (error) {
    const failedResponse = error?.response
    if (failedResponse?.headers?.['content-type']?.includes('application/json') && failedResponse.data instanceof Blob) {
      const payload = JSON.parse(await failedResponse.data.text())
      if (payload.message) error.message = payload.message
    }
    throw error
  }

  const contentType = response.headers['content-type'] || ''
  if (contentType.includes('application/json')) {
    const text = await response.data.text()
    return JSON.parse(text)
  }

  return {
    success: true,
    download: {
      blob: response.data,
      filename: extractFilenameFromDisposition(response.headers['content-disposition']) || 'export.dat'
    }
  }
}

export async function submitGisKmlManagementAction(formData, options = {}) {
  return postBlobAware('/api/v1/gis/kml-management/action/', formData, options)
}

const KML_JOB_POLL_MS = 1500
const KML_JOB_MAX_WAIT_MS = 60 * 60 * 1000
const KML_JOB_MAX_POLL_FAILURES = 20

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// 大文件叠加检查在服务端后台运行，前端轮询进度，避免网关 504 超时。
export async function runGisKmlAnalyzeJob(formData, { onProgress } = {}) {
  formData.set('action', 'analyze_selected')
  formData.set('async', '1')
  const started = await submitGisKmlManagementAction(formData)
  let job = started?.data
  if (!started?.success || !job?.job_id) {
    throw new Error(started?.message || '叠加检查任务启动失败')
  }

  const deadline = Date.now() + KML_JOB_MAX_WAIT_MS
  let failures = 0
  while (true) {
    onProgress?.(job)
    if (job.status === 'succeeded') return { success: true, ...job.result }
    if (job.status === 'failed') throw new Error(job.error || '叠加检查失败')
    if (Date.now() > deadline) throw new Error('叠加检查耗时过长，请稍后刷新页面查看结果')
    await sleep(KML_JOB_POLL_MS)
    try {
      const response = await client.get(`/api/v1/gis/kml-management/jobs/${job.job_id}/`, { timeout: MAP_REQUEST_TIMEOUT })
      failures = 0
      if (!response.data?.success) throw new Error(response.data?.message || '查询检查进度失败')
      job = response.data.data
    } catch (error) {
      if (error?.response?.status === 404) throw new Error('检查任务已过期，请重新执行')
      failures += 1
      if (failures >= KML_JOB_MAX_POLL_FAILURES) {
        throw new Error('网络不稳定，无法获取检查进度。检查仍在后台执行，请稍后重试')
      }
    }
  }
}

export async function submitOvkmlConvert(formData) {
  const response = await client.post('/api/v1/gis/ovkml-convert/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}

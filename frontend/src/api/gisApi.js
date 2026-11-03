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

export async function submitOvkmlConvert(formData) {
  const response = await client.post('/api/v1/gis/ovkml-convert/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}

import client from './client'

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
  const response = await client.get('/api/v1/gis/kml-records/')
  return response.data
}

export async function fetchGisKmlRecordKmlContent(recordId) {
  const response = await client.get(`/api/v1/gis/kml-records/${recordId}/kml-content/`)
  return response.data
}

async function postBlobAware(url, formData) {
  const response = await client.post(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    responseType: 'blob'
  })

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

export async function submitGisKmlManagementAction(formData) {
  return postBlobAware('/api/v1/gis/kml-management/action/', formData)
}

export async function submitKmlProcessConvert(formData) {
  return postBlobAware('/api/v1/gis/kml-process-convert/', formData)
}

export async function submitOvkmlConvert(formData) {
  const response = await client.post('/api/v1/gis/ovkml-convert/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}

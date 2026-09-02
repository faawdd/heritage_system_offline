import client from '../client'

export async function loginSystem(payload) {
  const response = await client.post('/api/v1/system/login/', payload)
  return response.data
}

export async function refreshSystemToken(refreshToken) {
  const response = await client.post('/api/v1/system/refresh/', {
    refresh: refreshToken
  })
  return response.data
}

export async function logoutSystem() {
  const response = await client.post('/api/v1/system/logout/')
  return response.data
}

export async function enterDjangoAdmin() {
  const response = await client.post('/api/v1/system/admin-entry/')
  return response.data
}

export async function fetchSystemProfile() {
  const response = await client.get('/api/v1/system/profile/')
  return response.data
}

export async function updateSystemProfile(payload) {
  const response = await client.patch('/api/v1/system/profile/', payload)
  return response.data
}

export async function changeSystemPassword(payload) {
  const response = await client.post('/api/v1/system/profile/change-password/', payload)
  return response.data
}

export async function fetchSystemUsers(params = {}) {
  const response = await client.get('/api/v1/system/users/', { params })
  return response.data
}

export async function createSystemUser(payload) {
  const response = await client.post('/api/v1/system/users/', payload)
  return response.data
}

export async function updateSystemUser(userId, payload) {
  const response = await client.patch(`/api/v1/system/users/${userId}/`, payload)
  return response.data
}

export async function deleteSystemUser(userId) {
  const response = await client.delete(`/api/v1/system/users/${userId}/`)
  return response.data
}

export async function fetchSystemRoles() {
  const response = await client.get('/api/v1/system/roles/')
  return response.data
}

export async function fetchSystemPermissions() {
  const response = await client.get('/api/v1/system/permissions/')
  return response.data
}

export async function fetchSystemMenus() {
  const response = await client.get('/api/v1/system/menus/')
  return response.data
}

export async function createSystemMenu(payload) {
  const response = await client.post('/api/v1/system/menus/', payload)
  return response.data
}

export async function updateSystemMenu(menuId, payload) {
  const response = await client.patch(`/api/v1/system/menus/${menuId}/`, payload)
  return response.data
}

export async function deleteSystemMenu(menuId) {
  const response = await client.delete(`/api/v1/system/menus/${menuId}/`)
  return response.data
}

export async function fetchDeepSeekConfig() {
  const response = await client.get('/api/v1/system/ai-config/deepseek/')
  return response.data
}

export async function updateDeepSeekConfig(payload) {
  const response = await client.put('/api/v1/system/ai-config/deepseek/', payload)
  return response.data
}

export async function startSipuBoundaryImport(payload) {
  const response = await client.post('/api/v1/system/sipu-boundary-import/start/', payload)
  return response.data
}

export async function fetchSipuBoundaryImportStatus(jobId) {
  const response = await client.get(`/api/v1/system/sipu-boundary-import/status/${jobId}/`)
  return response.data
}

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

export async function fetchDataSyncOptions() {
  const response = await client.get('/api/v1/system/data-sync/options/')
  return response.data
}

export async function exportDataSyncPackage({ datasets = [], includeMedia = true } = {}) {
  const formData = new FormData()
  datasets.forEach((item) => formData.append('datasets', item))
  formData.set('include_media', includeMedia ? '1' : '0')

  const response = await client.post('/api/v1/system/data-sync/export/', formData, {
    responseType: 'blob',
    timeout: 30 * 60 * 1000
  })

  const contentType = response.headers['content-type'] || ''
  if (contentType.includes('application/json')) {
    return JSON.parse(await response.data.text())
  }

  return {
    success: true,
    download: {
      blob: response.data,
      filename: extractFilenameFromDisposition(response.headers['content-disposition']) || 'heritage-sync.zip'
    }
  }
}

export async function importDataSyncPackage({ file, datasets = [], mode = 'merge', importMedia = true }) {
  const formData = new FormData()
  formData.set('package', file)
  datasets.forEach((item) => formData.append('datasets', item))
  formData.set('mode', mode)
  formData.set('import_media', importMedia ? '1' : '0')

  const response = await client.post('/api/v1/system/data-sync/import/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30 * 60 * 1000
  })
  return response.data
}

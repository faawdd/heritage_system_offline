import client from './client'

export async function fetchHeritageMapPoints() {
  const response = await client.get('/api/v1/heritage/map-points/')
  return response.data
}

export async function fetchHeritageStatsMeta() {
  const response = await client.get('/api/v1/heritage/stats/meta/')
  return response.data
}

export async function fetchHeritageClassificationStats(params = {}) {
  const response = await client.get('/api/v1/heritage/classification-stats/', { params })
  return response.data
}

export async function fetchHeritageDetail(siteId) {
  const response = await client.get(`/api/v1/heritage/${siteId}/detail/`)
  return response.data
}

export async function fetchHeritagePreview(params = {}) {
  const response = await client.get('/api/v1/heritage/preview/', { params })
  return response.data
}

export async function fetchHeritageSiteManageList(params = {}) {
  const response = await client.get('/api/v1/heritage/sites/', { params })
  return response.data
}

export async function patchHeritageSiteManage(siteId, payload) {
  const response = await client.patch(`/api/v1/heritage/sites/${siteId}/`, payload)
  return response.data
}

export async function importHeritageSiteManage(file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await client.post('/api/v1/heritage/sites/import/', formData)
  return response.data
}

export async function exportHeritageSiteManage(params = {}) {
  const response = await client.get('/api/v1/heritage/sites/export/', {
    params,
    responseType: 'blob'
  })
  return response
}

export async function exportHeritageBoundary(siteId, payload) {
  const response = await client.post(`/api/v1/heritage/${siteId}/boundary-export/`, payload, {
    responseType: 'blob'
  })
  return response
}

export async function fetchImmovableHeritageList(params = {}) {
  const response = await client.get('/api/v1/heritage/immovable/', { params })
  return response.data
}

export async function fetchImmovableCollectMeta() {
  const response = await client.get('/api/v1/heritage/immovable/collect/')
  return response.data
}

export async function createImmovableCollect(formData) {
  const response = await client.post('/api/v1/heritage/immovable/collect/', formData)
  return response.data
}

export async function patchImmovableHeritage(siteId, payload) {
  const response = await client.patch(`/api/v1/heritage/immovable/${siteId}/`, payload)
  return response.data
}

export async function deleteImmovableHeritage(siteId) {
  const response = await client.delete(`/api/v1/heritage/immovable/${siteId}/`)
  return response.data
}

export async function importImmovableHeritage(file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await client.post('/api/v1/heritage/immovable/import/', formData)
  return response.data
}

export async function fetchAndImportSipuImmovable(payload = {}) {
  const response = await client.post('/api/v1/heritage/immovable/sipu-fetch-import/', payload, {
    timeout: 180000
  })
  return response.data
}

export async function exportImmovableHeritage(params = {}) {
  const response = await client.get('/api/v1/heritage/immovable/export/', {
    params,
    responseType: 'blob'
  })
  return response
}

export async function fetchKanerjingList(params = {}) {
  const response = await client.get('/api/v1/heritage/kanerjing/', { params })
  return response.data
}

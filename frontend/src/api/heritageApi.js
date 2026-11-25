import client from './client'
import { MAP_REQUEST_TIMEOUT, requestMapData } from '../utils/networkRequest.js'
import { loadHeritageMapData } from '../utils/heritageMapLoader.js'

export async function fetchHeritageMapPoints({ signal, geometry = 'none', onPoints, onGeometry } = {}) {
  return loadHeritageMapData({
    signal, geometry, onPoints, onGeometry,
    async fetchPage(view, cursor, pageSignal) {
      const response = await requestMapData(
        () => client.get('/api/v1/heritage/map-points/', {
          params: { view, cursor }, signal: pageSignal, timeout: MAP_REQUEST_TIMEOUT
        }),
        { signal: pageSignal }
      )
      return response.data
    }
  })
}

export async function fetchHeritageStatsMeta() {
  const response = await client.get('/api/v1/heritage/stats/meta/')
  return response.data
}

export async function fetchHeritageClassificationStats(params = {}) {
  const response = await client.get('/api/v1/heritage/classification-stats/', { params })
  return response.data
}

export async function fetchHeritageClassificationDetail(params = {}) {
  const response = await client.get('/api/v1/heritage/classification-stats/detail/', { params })
  return response.data
}

export async function exportHeritageClassificationDetail(params = {}) {
  const response = await client.get('/api/v1/heritage/classification-stats/export/', {
    params,
    responseType: 'blob'
  })
  return response
}

export async function fetchHeritageDetail(siteId) {
  const response = await client.get(`/api/v1/heritage/${siteId}/detail/`)
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

export async function uploadHeritageTwoLineFile(siteId, file, zoneType = 'auto') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('zone_type', zoneType)
  const response = await client.post(`/api/v1/heritage/sites/${siteId}/two-line-file/`, formData)
  return response.data
}

export async function deleteHeritageTwoLineFile(siteId) {
  const response = await client.delete(`/api/v1/heritage/sites/${siteId}/two-line-file/`)
  return response.data
}

export async function uploadHeritageBodyBoundaryFile(siteId, file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await client.post(`/api/v1/heritage/sites/${siteId}/body-boundary/`, formData)
  return response.data
}

export async function deleteHeritageBodyBoundary(siteId) {
  const response = await client.delete(`/api/v1/heritage/sites/${siteId}/body-boundary/`)
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

export async function exportHeritageSiteCoordinates(params = {}) {
  const response = await client.get('/api/v1/heritage/sites/coordinates-export/', {
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

export async function fetchImmovableHeritageDetail(siteId) {
  const response = await client.get(`/api/v1/heritage/immovable/${siteId}/`)
  return response.data
}

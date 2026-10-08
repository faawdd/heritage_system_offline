import client from '../client'

export async function fetchOfflineTileSets() {
  const response = await client.get('/api/v1/gis/offline-tiles/')
  return response.data
}

export async function uploadOfflineTileSet(file, name = '', scheme = 'xyz') {
  const formData = new FormData()
  formData.set('file', file)
  formData.set('name', name)
  formData.set('scheme', scheme)
  const response = await client.post('/api/v1/gis/offline-tiles/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30 * 60 * 1000
  })
  return response.data
}

export async function deleteOfflineTileSet(tileSetId) {
  const response = await client.delete(`/api/v1/gis/offline-tiles/${tileSetId}/`)
  return response.data
}
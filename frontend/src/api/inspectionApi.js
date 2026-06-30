import client from './client'

export async function fetchInspectionStats() {
  const response = await client.get('/api/v1/inspections/stats/')
  return response.data
}

export async function fetchInspections(params = {}) {
  const response = await client.get('/api/v1/inspections/', { params })
  return response.data
}

export async function patchInspection(inspectionId, payload) {
  const response = await client.patch(`/api/v1/inspections/${inspectionId}/`, payload)
  return response.data
}

export async function deleteInspection(inspectionId) {
  const response = await client.delete(`/api/v1/inspections/${inspectionId}/`)
  return response.data
}

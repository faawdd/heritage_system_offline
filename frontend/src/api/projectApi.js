import client from './client'

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

export async function verifyProjectSpatialSafety(projectId, thresholdM) {
  const params = thresholdM ? { threshold_m: thresholdM } : {}
  const response = await client.post(`/api/v1/projects/${projectId}/verify-spatial-safety/`, null, { params })
  return response.data
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

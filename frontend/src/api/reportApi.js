import client from './client'

export async function fetchReports() {
  const response = await client.get('/api/v1/reports/')
  return response.data
}

export async function generateReport(period) {
  const response = await client.post('/api/v1/reports/generate/', { period })
  return response.data
}

export async function fetchReportHtml(reportId) {
  const response = await client.get(`/api/v1/reports/${reportId}/html/`)
  return response.data
}

export async function fetchReportPreview(period) {
  const response = await client.get('/api/v1/reports/preview/', { params: { period } })
  return response.data
}

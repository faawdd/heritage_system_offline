import client from './client'

export async function fetchSystemVersion() {
  const response = await client.get('/api/v1/system/version/')
  return response.data
}

export async function fetchDashboardOverview() {
  const response = await client.get('/api/v1/dashboard/overview/')
  return response.data
}

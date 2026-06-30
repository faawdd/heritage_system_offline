import client from './client'

export async function fetchSystemVersion() {
  const response = await client.get('/api/v1/system/version/')
  return response.data
}

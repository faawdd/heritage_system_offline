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

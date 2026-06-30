import axios from 'axios'

const ACCESS_TOKEN_KEY = 'heritage_access_token'
const REFRESH_TOKEN_KEY = 'heritage_refresh_token'

const client = axios.create({
  baseURL: '/',
  withCredentials: true,
  timeout: 20000
})

let refreshPromise = null

function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || ''
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || ''
}

function saveAccessToken(token) {
  if (token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, token)
  } else {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
  }
}

function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

client.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

async function refreshAccessToken() {
  if (!refreshPromise) {
    const refresh = getRefreshToken()
    if (!refresh) {
      return null
    }

    refreshPromise = axios
      .post('/api/v1/system/refresh/', { refresh }, { withCredentials: true, timeout: 20000 })
      .then((response) => {
        const result = response.data || {}
        if (!result.success) {
          return null
        }
        const token = result.data?.access || ''
        saveAccessToken(token)
        return token
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null
      })
  }

  return refreshPromise
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status
    const originalRequest = error?.config
    const url = originalRequest?.url || ''

    if (!originalRequest || status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    if (url.includes('/api/v1/system/login/') || url.includes('/api/v1/system/refresh/')) {
      clearAuthTokens()
      return Promise.reject(error)
    }

    originalRequest._retry = true
    const token = await refreshAccessToken()
    if (!token) {
      clearAuthTokens()
      return Promise.reject(error)
    }

    originalRequest.headers = originalRequest.headers || {}
    originalRequest.headers.Authorization = `Bearer ${token}`
    return client(originalRequest)
  }
)

export default client

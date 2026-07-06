import { defineStore } from 'pinia'

import {
  fetchSystemMenus,
  fetchSystemProfile,
  loginSystem,
  logoutSystem,
  refreshSystemToken
} from '../../api/system/systemApi'

const ACCESS_TOKEN_KEY = 'heritage_access_token'
const REFRESH_TOKEN_KEY = 'heritage_refresh_token'
const USER_KEY = 'heritage_user'
const MENU_TREE_KEY = 'heritage_menu_tree'
const DESKTOP_AUTH_KEY = 'desktop_local_auth'

function safeParse(json, fallback = null) {
  if (!json) {
    return fallback
  }
  try {
    return JSON.parse(json)
  } catch (_error) {
    return fallback
  }
}

export const useAuthStore = defineStore('system_auth', {
  state: () => ({
    accessToken: localStorage.getItem(ACCESS_TOKEN_KEY) || '',
    refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) || '',
    user: safeParse(localStorage.getItem(USER_KEY), null),
    menuTree: safeParse(localStorage.getItem(MENU_TREE_KEY), []),
    initialized: false
  }),
  getters: {
    isAuthenticated(state) {
      return Boolean(state.accessToken)
    }
  },
  actions: {
    persistAuth() {
      if (this.accessToken) {
        localStorage.setItem(ACCESS_TOKEN_KEY, this.accessToken)
      } else {
        localStorage.removeItem(ACCESS_TOKEN_KEY)
      }

      if (this.refreshToken) {
        localStorage.setItem(REFRESH_TOKEN_KEY, this.refreshToken)
      } else {
        localStorage.removeItem(REFRESH_TOKEN_KEY)
      }

      if (this.user) {
        localStorage.setItem(USER_KEY, JSON.stringify(this.user))
      } else {
        localStorage.removeItem(USER_KEY)
      }

      localStorage.setItem(MENU_TREE_KEY, JSON.stringify(this.menuTree || []))
    },
    clearAuth() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      this.menuTree = []
      this.persistAuth()

      // Ensure desktop session authorization is revoked on logout.
      if (typeof window !== 'undefined') {
        if (window.sessionStorage) {
          window.sessionStorage.removeItem(DESKTOP_AUTH_KEY)
        }
        if (window.localStorage) {
          window.localStorage.removeItem(DESKTOP_AUTH_KEY)
        }
      }
    },
    async login(username, password) {
      const result = await loginSystem({ username, password })
      if (!result.success) {
        throw new Error(result.message || '登录失败')
      }

      const payload = result.data || {}
      this.accessToken = payload.access_token || ''
      this.refreshToken = payload.refresh_token || ''
      this.user = payload.user || null
      this.menuTree = payload.menus || []
      this.persistAuth()
      return result
    },
    async loadProfile() {
      if (!this.accessToken) {
        return
      }
      const result = await fetchSystemProfile()
      if (result.success) {
        this.user = result.data || null
        this.persistAuth()
      }
    },
    async loadMenus() {
      if (!this.accessToken) {
        return
      }
      const result = await fetchSystemMenus()
      if (result.success) {
        this.menuTree = result.tree || []
        this.persistAuth()
      }
    },
    async restoreSession() {
      if (this.initialized) {
        return
      }
      this.initialized = true
      if (!this.accessToken) {
        return
      }
      try {
        await this.loadProfile()
        await this.loadMenus()
      } catch (_error) {
        this.clearAuth()
      }
    },
    async tryRefreshToken() {
      if (!this.refreshToken) {
        this.clearAuth()
        return null
      }

      const result = await refreshSystemToken(this.refreshToken)
      if (!result.success) {
        this.clearAuth()
        return null
      }

      const data = result.data || {}
      this.accessToken = data.access || ''
      if (data.refresh) {
        this.refreshToken = data.refresh
      }
      this.persistAuth()
      return this.accessToken
    },
    async logout() {
      try {
        if (this.accessToken) {
          await logoutSystem()
        }
      } catch (_error) {
        // swallow logout API errors and always clear local state
      }
      this.clearAuth()
    }
  }
})

export const authTokenKeys = {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY
}

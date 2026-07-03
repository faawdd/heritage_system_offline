import { defineStore } from 'pinia'

import { fetchPublicSystemInfo } from '../../api/system/systemApi'

const DEFAULT_SYSTEM_NAME = '文物管理系统（离线版）'

function applyDocumentTitle(systemName) {
  if (typeof document === 'undefined') {
    return
  }
  document.title = systemName || DEFAULT_SYSTEM_NAME
}

export const useAppStore = defineStore('system_app_meta', {
  state: () => ({
    systemName: DEFAULT_SYSTEM_NAME,
    systemRegion: '',
    version: '',
    initialized: false,
    loading: false,
  }),
  actions: {
    async initialize() {
      if (this.loading) {
        return
      }
      if (this.initialized) {
        applyDocumentTitle(this.systemName)
        return
      }

      this.loading = true
      applyDocumentTitle(this.systemName)

      try {
        const result = await fetchPublicSystemInfo()
        if (result?.success) {
          const payload = result.data || {}
          this.systemName = String(payload.system_name || DEFAULT_SYSTEM_NAME).trim() || DEFAULT_SYSTEM_NAME
          this.systemRegion = String(payload.system_region || '').trim()
          this.version = String(payload.version || '').trim()
        }
      } catch (_error) {
        this.systemName = this.systemName || DEFAULT_SYSTEM_NAME
      } finally {
        this.initialized = true
        this.loading = false
        applyDocumentTitle(this.systemName)
      }
    },
  },
})
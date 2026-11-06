import { reactive } from 'vue'

export const updateState = reactive({
  status: 'idle',
  latestVersion: '',
  checkedAt: null,
  error: ''
})

let pendingCheck = null

export function checkDesktopUpdates() {
  if (pendingCheck) return pendingCheck
  if (!window.desktopUpdates?.check) {
    updateState.status = 'unavailable'
    updateState.error = '请在离线桌面客户端中检查更新'
    return Promise.resolve(null)
  }
  updateState.status = 'checking'
  updateState.error = ''
  pendingCheck = window.desktopUpdates.check(__APP_VERSION__)
    .then(result => {
      updateState.latestVersion = result.latestVersion
      updateState.checkedAt = result.checkedAt
      updateState.status = result.updateAvailable ? 'available' : 'current'
      return result
    })
    .catch(error => {
      updateState.status = 'error'
      updateState.error = error?.message || '无法连接更新服务器，请检查网络后重试'
      return null
    })
    .finally(() => { pendingCheck = null })
  return pendingCheck
}

export async function openUpdateDownload() {
  if (!window.desktopUpdates?.openDownload) {
    throw new Error('请在离线桌面客户端中打开下载页面')
  }
  await window.desktopUpdates.openDownload()
}

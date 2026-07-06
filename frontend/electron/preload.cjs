const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktopMeta', {
  runtime: 'electron',
})

contextBridge.exposeInMainWorld('desktopInit', {
  getState: (payload) => ipcRenderer.invoke('desktop-init:get-state', payload),
  pickDirectory: (payload) => ipcRenderer.invoke('desktop-init:pick-directory', payload),
  complete: (payload) => ipcRenderer.invoke('desktop-init:complete', payload),
  notifyFinished: () => ipcRenderer.send('desktop-init:finished'),
})

contextBridge.exposeInMainWorld('desktopData', {
  pickBackupDir: () => ipcRenderer.invoke('desktop-data:pick-backup-dir'),
  createBackup: (payload) => ipcRenderer.invoke('desktop-data:create-backup', payload),
  pickRestoreFile: () => ipcRenderer.invoke('desktop-data:pick-restore-file'),
  restoreBackup: (payload) => ipcRenderer.invoke('desktop-data:restore-backup', payload),
})

contextBridge.exposeInMainWorld('electronAPI', {
  login: async (username, password) => {
    try {
      const response = await ipcRenderer.invoke('auth:login', {
        username,
        password,
      })
      return {
        success: Boolean(response?.success),
        message: String(response?.message || (response?.success ? '登录成功' : '登录失败')),
      }
    } catch (error) {
      return {
        success: false,
        message: String(error?.message || '登录请求失败'),
      }
    }
  },
  closeLoginWindow: async () => {
    try {
      const response = await ipcRenderer.invoke('auth:close-login-window')
      return {
        success: Boolean(response?.success),
        message: String(response?.message || (response?.success ? '窗口已关闭' : '关闭失败')),
      }
    } catch (error) {
      return {
        success: false,
        message: String(error?.message || '关闭窗口请求失败'),
      }
    }
  },
  logoutToLogin: async () => {
    try {
      const response = await ipcRenderer.invoke('auth:logout-to-login')
      return {
        success: Boolean(response?.success),
        message: String(response?.message || (response?.success ? '已退出' : '退出失败')),
      }
    } catch (error) {
      return {
        success: false,
        message: String(error?.message || '退出请求失败'),
      }
    }
  },
})

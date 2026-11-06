const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktopMeta', {
  runtime: 'electron'
})

contextBridge.exposeInMainWorld('desktopSetup', {
  complete: (payload) => ipcRenderer.invoke('desktop-setup:complete', payload)
})

contextBridge.exposeInMainWorld('desktopAuth', {
  loginSucceeded: () => ipcRenderer.invoke('desktop-auth:login-succeeded'),
  requireLogin: () => ipcRenderer.invoke('desktop-auth:require-login')
})

contextBridge.exposeInMainWorld('desktopUpdates', {
  check: (currentVersion) => ipcRenderer.invoke('desktop-updates:check', currentVersion),
  openDownload: () => ipcRenderer.invoke('desktop-updates:open-download')
})
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktopMeta', {
  runtime: 'electron'
})

contextBridge.exposeInMainWorld('desktopSetup', {
  complete: (payload) => ipcRenderer.invoke('desktop-setup:complete', payload)
})

contextBridge.exposeInMainWorld('desktopAuth', {
  loginSucceeded: () => ipcRenderer.invoke('desktop-auth:login-succeeded')
})
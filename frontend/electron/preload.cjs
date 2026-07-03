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

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

const { app, BrowserWindow, dialog, ipcMain, Menu } = require('electron')
const path = require('path')
const fs = require('fs')
const { spawn } = require('child_process')
const http = require('http')
const net = require('net')

const BACKEND_HOST = process.env.BACKEND_HOST || '127.0.0.1'
const BACKEND_PORT = Number(process.env.BACKEND_PORT || 18000)
const CONFIG_FILE_NAME = 'desktop-config.json'

let backendProcess = null
let backendLogStream = null
let mainWindow = null
let initWizardWindow = null
let runtimeConfig = null

function getConfigPath() {
  return path.join(app.getPath('userData'), CONFIG_FILE_NAME)
}

function getDefaultConfig() {
  return {
    initialized: false,
    dataDir: path.join(app.getPath('userData'), 'data'),
    logDir: app.getPath('logs'),
    backendPort: BACKEND_PORT,
  }
}

function loadDesktopConfig() {
  const defaults = getDefaultConfig()
  const configPath = getConfigPath()

  if (!fs.existsSync(configPath)) {
    return defaults
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(configPath, 'utf-8'))
    return {
      ...defaults,
      ...parsed,
      backendPort: Number(parsed.backendPort || defaults.backendPort),
    }
  } catch (error) {
    return defaults
  }
}

function saveDesktopConfig(config) {
  const merged = {
    ...getDefaultConfig(),
    ...config,
  }

  const configPath = getConfigPath()
  fs.mkdirSync(path.dirname(configPath), { recursive: true })
  fs.writeFileSync(configPath, JSON.stringify(merged, null, 2), 'utf-8')
}

function testDirectoryWritable(dirPath) {
  try {
    fs.mkdirSync(dirPath, { recursive: true })
    const testFile = path.join(dirPath, `.write-test-${Date.now()}.tmp`)
    fs.writeFileSync(testFile, 'ok', 'utf-8')
    fs.unlinkSync(testFile)
    return { ok: true, message: '可写' }
  } catch (error) {
    return { ok: false, message: String(error?.message || error) }
  }
}

function checkPortAvailable(port, host = BACKEND_HOST) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', (error) => {
      if (error && error.code === 'EADDRINUSE') {
        resolve(false)
        return
      }
      resolve(false)
    })

    server.once('listening', () => {
      server.close(() => resolve(true))
    })

    server.listen(port, host)
  })
}

async function findAvailablePort(startPort, maxOffset = 20) {
  const normalized = Number(startPort || BACKEND_PORT)
  for (let offset = 0; offset <= maxOffset; offset += 1) {
    const port = normalized + offset
    const available = await checkPortAvailable(port)
    if (available) {
      return port
    }
  }
  return null
}

async function buildInitState(config) {
  const normalized = {
    ...getDefaultConfig(),
    ...config,
    backendPort: Number(config?.backendPort || BACKEND_PORT),
  }

  const dataDirCheck = testDirectoryWritable(normalized.dataDir)
  const logDirCheck = testDirectoryWritable(normalized.logDir)
  const requestedPortFree = await checkPortAvailable(normalized.backendPort)
  const suggestedPort = requestedPortFree
    ? normalized.backendPort
    : await findAvailablePort(normalized.backendPort + 1)

  return {
    config: normalized,
    checks: {
      dataDir: {
        path: normalized.dataDir,
        ok: dataDirCheck.ok,
        message: dataDirCheck.message,
      },
      logDir: {
        path: normalized.logDir,
        ok: logDirCheck.ok,
        message: logDirCheck.message,
      },
      backendPort: {
        requested: normalized.backendPort,
        ok: requestedPortFree,
        message: requestedPortFree ? '可用' : '端口已被占用',
        suggested: suggestedPort,
      },
    },
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function canConnect(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume()
      resolve(res.statusCode >= 200 && res.statusCode < 500)
    })

    req.on('error', () => resolve(false))
    req.setTimeout(1200, () => {
      req.destroy()
      resolve(false)
    })
  })
}

async function waitForBackendReady(port, timeoutMs = 30000) {
  const healthUrl = `http://${BACKEND_HOST}:${port}/api/v1/health/`
  const deadline = Date.now() + timeoutMs

  while (Date.now() < deadline) {
    if (await canConnect(healthUrl)) {
      return true
    }
    await sleep(400)
  }

  return false
}

function resolveDevPython() {
  const repoRoot = path.resolve(__dirname, '..', '..')
  const venvPython = process.platform === 'win32'
    ? path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(repoRoot, '.venv', 'bin', 'python')

  if (fs.existsSync(venvPython)) {
    return venvPython
  }

  return process.platform === 'win32' ? 'python' : 'python3'
}

function ensureLogStream(logDir) {
  fs.mkdirSync(logDir, { recursive: true })
  const logPath = path.join(logDir, 'backend.log')
  backendLogStream = fs.createWriteStream(logPath, { flags: 'a' })
}

function closeLogStream() {
  if (!backendLogStream) {
    return
  }

  backendLogStream.end()
  backendLogStream = null
}

function startBackend(config) {
  ensureLogStream(config.logDir)

  const backendEnv = {
    ...process.env,
    BACKEND_HOST: BACKEND_HOST,
    BACKEND_PORT: String(config.backendPort),
    HERITAGE_DATA_DIR: config.dataDir,
    HERITAGE_LOG_DIR: config.logDir,
    DJANGO_DEBUG: '1',
    DJANGO_FORCE_HTTPS: '0',
    DJANGO_WEB_BASE_URL: `http://${BACKEND_HOST}:${config.backendPort}`,
  }

  if (app.isPackaged) {
    const backendFileName = process.platform === 'win32' ? 'heritage_backend.exe' : 'heritage_backend'
    const backendPath = path.join(process.resourcesPath, 'backend', backendFileName)

    if (!fs.existsSync(backendPath)) {
      throw new Error(`未找到后端可执行文件: ${backendPath}`)
    }

    backendProcess = spawn(backendPath, [], {
      cwd: path.dirname(backendPath),
      env: backendEnv,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })

    if (backendProcess.stdout && backendLogStream) {
      backendProcess.stdout.pipe(backendLogStream, { end: false })
    }
    if (backendProcess.stderr && backendLogStream) {
      backendProcess.stderr.pipe(backendLogStream, { end: false })
    }
    return
  }

  const repoRoot = path.resolve(__dirname, '..', '..')
  const pythonCmd = resolveDevPython()
  const args = ['manage.py', 'runserver', `${BACKEND_HOST}:${config.backendPort}`]

  backendProcess = spawn(pythonCmd, args, {
    cwd: repoRoot,
    env: backendEnv,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })

  if (backendProcess.stdout && backendLogStream) {
    backendProcess.stdout.pipe(backendLogStream, { end: false })
  }
  if (backendProcess.stderr && backendLogStream) {
    backendProcess.stderr.pipe(backendLogStream, { end: false })
  }
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) {
    closeLogStream()
    return
  }

  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t'])
    } else {
      backendProcess.kill('SIGTERM')
    }
  } catch (err) {
    // Ignore process cleanup failure during app shutdown.
  } finally {
    closeLogStream()
  }
}

function setupInitIpc() {
  ipcMain.handle('desktop-init:get-state', async (_event, payload = {}) => {
    const current = loadDesktopConfig()
    const merged = {
      ...current,
      ...payload,
    }
    const state = await buildInitState(merged)
    return state
  })

  ipcMain.handle('desktop-init:pick-directory', async (_event, payload = {}) => {
    const defaultPath = String(payload.currentPath || app.getPath('home'))
    const parentWindow = initWizardWindow && !initWizardWindow.isDestroyed()
      ? initWizardWindow
      : mainWindow

    const result = await dialog.showOpenDialog(parentWindow, {
      title: '选择目录',
      defaultPath,
      properties: ['openDirectory', 'createDirectory'],
    })

    if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
      return { canceled: true }
    }

    return { canceled: false, path: result.filePaths[0] }
  })

  ipcMain.handle('desktop-init:complete', async (_event, payload = {}) => {
    const current = loadDesktopConfig()
    const chosenPort = Number(payload.backendPort || current.backendPort || BACKEND_PORT)
    const merged = {
      ...current,
      dataDir: String(payload.dataDir || current.dataDir),
      logDir: String(payload.logDir || current.logDir),
      initialized: true,
      backendPort: chosenPort,
    }

    const state = await buildInitState(merged)
    if (!state.checks.dataDir.ok) {
      return { ok: false, message: `数据目录不可用：${state.checks.dataDir.message}` }
    }
    if (!state.checks.logDir.ok) {
      return { ok: false, message: `日志目录不可用：${state.checks.logDir.message}` }
    }
    if (!state.checks.backendPort.ok) {
      const suggested = state.checks.backendPort.suggested
      return {
        ok: false,
        message: suggested
          ? `端口 ${chosenPort} 已占用，建议改用 ${suggested}`
          : `端口 ${chosenPort} 已占用，且未找到可用替代端口`,
      }
    }

    saveDesktopConfig(merged)
    runtimeConfig = merged
    return { ok: true }
  })
}

function resetInitializationWizard() {
  const current = loadDesktopConfig()
  saveDesktopConfig({
    ...current,
    initialized: false,
  })

  dialog.showMessageBox({
    type: 'info',
    title: '初始化向导已重置',
    message: '系统将立即重启并重新执行初始化检测。',
    buttons: ['确定'],
  }).finally(() => {
    app.relaunch()
    app.exit(0)
  })
}

function setupApplicationMenu() {
  const template = [
    {
      label: '工具',
      submenu: [
        {
          label: '重置初始化向导',
          click: () => resetInitializationWizard(),
        },
        { type: 'separator' },
        { role: 'reload', label: '刷新' },
        { role: 'toggleDevTools', label: '开发者工具' },
      ],
    },
    {
      label: '窗口',
      submenu: [
        { role: 'minimize', label: '最小化' },
        { role: 'close', label: '关闭' },
      ],
    },
  ]

  if (process.platform === 'darwin') {
    template.unshift({
      label: app.name,
      submenu: [
        { role: 'about', label: '关于' },
        { type: 'separator' },
        { role: 'quit', label: '退出' },
      ],
    })
  }

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}

function openInitWizard() {
  return new Promise((resolve, reject) => {
    let done = false

    initWizardWindow = new BrowserWindow({
      width: 760,
      height: 620,
      resizable: false,
      minimizable: false,
      maximizable: false,
      autoHideMenuBar: true,
      webPreferences: {
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.cjs'),
      },
    })

    const wizardPath = path.join(__dirname, 'wizard.html')
    initWizardWindow.loadFile(wizardPath)

    const finish = (error) => {
      if (done) {
        return
      }
      done = true
      if (error) {
        reject(error)
      } else {
        resolve(runtimeConfig || loadDesktopConfig())
      }
    }

    ipcMain.once('desktop-init:finished', () => {
      if (initWizardWindow && !initWizardWindow.isDestroyed()) {
        initWizardWindow.close()
      }
      finish(null)
    })

    initWizardWindow.on('closed', () => {
      initWizardWindow = null
      if (!done) {
        finish(new Error('初始化向导未完成，已取消启动。'))
      }
    })
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  const effectivePort = runtimeConfig?.backendPort || BACKEND_PORT
  const startUrl = process.env.ELECTRON_START_URL || `http://${BACKEND_HOST}:${effectivePort}/`
  mainWindow.loadURL(startUrl)
}

app.whenReady().then(async () => {
  try {
    setupApplicationMenu()
    setupInitIpc()

    if (!process.env.ELECTRON_START_URL) {
      const loaded = loadDesktopConfig()
      runtimeConfig = loaded

      if (!loaded.initialized) {
        await openInitWizard()
      }

      const state = await buildInitState(runtimeConfig)
      if (!state.checks.dataDir.ok || !state.checks.logDir.ok) {
        throw new Error('初始化检测失败：数据目录或日志目录不可写。')
      }
      if (!state.checks.backendPort.ok) {
        throw new Error(`初始化检测失败：端口 ${runtimeConfig.backendPort} 被占用。`)
      }

      startBackend(runtimeConfig)

      const ok = await waitForBackendReady(runtimeConfig.backendPort)
      if (!ok) {
        throw new Error(`后端服务未在限定时间内就绪，请检查日志文件：${path.join(runtimeConfig.logDir, 'backend.log')}`)
      }
    }

    createWindow()
  } catch (error) {
    dialog.showErrorBox('离线桌面版启动失败', String(error?.message || error))
    app.quit()
  }
})

app.on('window-all-closed', () => {
  stopBackend()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopBackend()
})

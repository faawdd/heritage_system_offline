const { app, BrowserWindow, dialog, ipcMain } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const http = require('http')
const net = require('net')
const path = require('path')

const DEFAULT_BACKEND_PORT = 18000
const BACKEND_START_TIMEOUT_MS = 30000
const DEFAULT_SYSTEM_NAME = '文物综合管理平台'

let backendProcess = null
let backendSpawnError = null
let backendLogStream = null
let mainWindow = null
let loginWindow = null
let setupWindow = null
let setupResolver = null
let setupConfigPath = ''
let backendOrigin = ''
let rendererBasePath = ''
let desktopLoginPassed = false
let activeSystemName = DEFAULT_SYSTEM_NAME

function getRuntimePaths() {
  const appDir = path.join(process.resourcesPath, 'runtime', 'app')
  const dataDir = path.join(app.getPath('userData'), 'data')
  const configDir = path.join(app.getPath('userData'), 'config')
  const logDir = path.join(app.getPath('userData'), 'logs')
  const uploadDir = path.join(app.getPath('userData'), 'uploads')
  const backupDir = path.join(app.getPath('userData'), 'backups')

  for (const directory of [dataDir, configDir, logDir, uploadDir, backupDir]) {
    fs.mkdirSync(directory, { recursive: true })
  }

  return { appDir, backupDir, configDir, dataDir, logDir, uploadDir }
}

function readDesktopConfig(paths) {
  const configPath = path.join(paths.configDir, 'desktop-config.json')
  try {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
    const systemRegion = String(config.systemRegion || '').trim().slice(0, 80)
    return {
      ...config,
      systemRegion,
      systemName: `${systemRegion}${DEFAULT_SYSTEM_NAME}`
    }
  } catch (_error) {
    return { initialized: false, systemName: DEFAULT_SYSTEM_NAME, systemRegion: '' }
  }
}

function hasExistingInstallation(paths) {
  return fs.existsSync(path.join(paths.configDir, 'desktop-config.json')) ||
    fs.existsSync(path.join(paths.dataDir, 'database.sqlite3'))
}

function showSetupWizard(paths, currentConfig) {
  setupConfigPath = path.join(paths.configDir, 'desktop-config.json')
  return new Promise((resolve, reject) => {
    setupResolver = resolve
    setupWindow = new BrowserWindow({
      width: 620,
      height: 790,
      resizable: false,
      show: false,
      autoHideMenuBar: true,
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        preload: path.join(__dirname, 'preload.cjs')
      }
    })
    setupWindow.once('ready-to-show', () => setupWindow.show())
    setupWindow.once('closed', () => {
      setupWindow = null
      if (setupResolver) {
        setupResolver = null
        reject(new Error('首次配置未完成'))
      }
    })
    setupWindow.loadFile(path.join(__dirname, 'wizard.html'), {
      query: {
        systemRegion: String(currentConfig.systemRegion || '')
      }
    })
  })
}

function reservePort() {
  const tryPort = (port) => new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(port, '127.0.0.1', () => {
      server.close((error) => (error ? reject(error) : resolve(port)))
    })
  })

  return (async () => {
    for (let port = DEFAULT_BACKEND_PORT; port < DEFAULT_BACKEND_PORT + 50; port += 1) {
      try {
        return await tryPort(port)
      } catch (_error) {
        continue
      }
    }
    throw new Error('本地服务端口范围 18000–18049 均被占用，请关闭其他实例后重试。')
  })()
}

function checkBackend(port) {
  return new Promise((resolve) => {
    const request = http.get(`http://127.0.0.1:${port}/api/v1/health/`, (response) => {
      response.resume()
      resolve(response.statusCode >= 200 && response.statusCode < 500)
    })
    request.setTimeout(1000, () => request.destroy())
    request.on('error', () => resolve(false))
  })
}

async function waitForBackend(port) {
  const deadline = Date.now() + BACKEND_START_TIMEOUT_MS
  while (Date.now() < deadline) {
    if (backendSpawnError) {
      throw new Error(`本地服务启动失败：${backendSpawnError.message}`)
    }
    if (backendProcess && backendProcess.exitCode !== null) {
      throw new Error(`本地服务意外退出，退出码 ${backendProcess.exitCode}`)
    }
    if (await checkBackend(port)) {
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 400))
  }
  throw new Error('本地服务启动超时，请查看用户数据目录中的 logs/backend.log')
}

function startPackagedBackend(paths, port, desktopConfig) {
  const executable = path.join(
    paths.appDir,
    process.platform === 'win32' ? 'heritage_backend.exe' : 'heritage_backend'
  )
  if (!fs.existsSync(executable)) {
    throw new Error(`缺少本地服务运行文件：${executable}`)
  }
  if (process.platform !== 'win32') {
    // 已安装的旧包可能丢失了可执行位。
    try {
      fs.chmodSync(executable, 0o755)
    } catch (_error) {
      throw new Error(`本地服务文件没有执行权限，且无法自动修复：${executable}`)
    }
  }

  const logPath = path.join(paths.logDir, 'backend.log')
  backendLogStream = fs.createWriteStream(logPath, { flags: 'a' })
  backendProcess = spawn(executable, [], {
    cwd: paths.appDir,
    env: {
      ...process.env,
      BACKEND_HOST: '127.0.0.1',
      BACKEND_PORT: String(port),
      HERITAGE_APP_DIR: paths.appDir,
      HERITAGE_BACKUP_DIR: paths.backupDir,
      HERITAGE_CONFIG_DIR: paths.configDir,
      HERITAGE_DATA_DIR: paths.dataDir,
      HERITAGE_LOG_DIR: paths.logDir,
      HERITAGE_UPLOAD_DIR: paths.uploadDir,
      DJANGO_DEBUG: '0',
      DJANGO_FORCE_HTTPS: '0',
      SYSTEM_NAME: desktopConfig.systemName,
      SYSTEM_REGION: desktopConfig.systemRegion
    },
    stdio: ['pipe', 'pipe', 'pipe']
  })
  backendProcess.on('error', (error) => {
    backendSpawnError = error
  })
  backendProcess.stdin.on('error', () => {})
  backendProcess.stdin.end(JSON.stringify(desktopConfig.securityQuestions || []))
  backendProcess.stdout.pipe(backendLogStream)
  backendProcess.stderr.pipe(backendLogStream)
}

function createMainWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 680,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      partition: 'persist:heritage-desktop',
      preload: path.join(__dirname, 'preload.cjs')
    }
  })
  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.on('closed', () => {
    mainWindow = null
  })
  mainWindow.loadURL(url)
}

function buildMainWindowUrl() {
  return `${backendOrigin}${rendererBasePath}/dashboard?desktop_auth=1`
}

function createLoginWindow(url, systemName = DEFAULT_SYSTEM_NAME) {
  loginWindow = new BrowserWindow({
    width: 420,
    height: 600,
    useContentSize: true,
    minWidth: 420,
    maxWidth: 420,
    minHeight: 600,
    maxHeight: 600,
    resizable: false,
    maximizable: false,
    minimizable: true,
    fullscreenable: false,
    frame: true,
    show: false,
    autoHideMenuBar: true,
    title: systemName,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      partition: 'persist:heritage-desktop',
      preload: path.join(__dirname, 'preload.cjs')
    }
  })
  loginWindow.once('ready-to-show', () => loginWindow?.show())
  loginWindow.on('closed', () => {
    loginWindow = null
    if (!desktopLoginPassed) app.quit()
  })
  loginWindow.loadURL(url)
}

async function startApplication() {
  if (!app.isPackaged) {
    const loginUrl = process.env.ELECTRON_START_URL || 'http://127.0.0.1:5173/login'
    const parsedLoginUrl = new URL(loginUrl)
    backendOrigin = parsedLoginUrl.origin
    const loginPath = parsedLoginUrl.pathname.replace(/\/+$/, '')
    rendererBasePath = loginPath.endsWith('/login')
      ? loginPath.slice(0, -'/login'.length)
      : ''
    createLoginWindow(`${loginUrl}${loginUrl.includes('?') ? '&' : '?'}login_window=1`)
    return
  }

  const paths = getRuntimePaths()
  rendererBasePath = ''
  let desktopConfig = readDesktopConfig(paths)
  if (!hasExistingInstallation(paths)) {
    desktopConfig = await showSetupWizard(paths, desktopConfig)
  }
  activeSystemName = desktopConfig.systemName
  const port = await reservePort()
  startPackagedBackend(paths, port, desktopConfig)
  await waitForBackend(port)
  backendOrigin = `http://127.0.0.1:${port}`
  const loginQuery = new URLSearchParams({
    login_window: '1',
    system_name: desktopConfig.systemName
  })
  createLoginWindow(`${backendOrigin}/login?${loginQuery.toString()}`, desktopConfig.systemName)
}

ipcMain.handle('desktop-auth:login-succeeded', (event) => {
  if (!loginWindow || event.sender.id !== loginWindow.webContents.id) {
    return { success: false, message: '登录窗口无效' }
  }
  if (!backendOrigin) {
    return { success: false, message: '本地服务地址尚未准备好' }
  }

  desktopLoginPassed = true
  if (!mainWindow || mainWindow.isDestroyed()) {
    createMainWindow(buildMainWindowUrl())
  } else {
    mainWindow.show()
    mainWindow.focus()
  }
  loginWindow.close()
  return { success: true }
})

ipcMain.handle('desktop-auth:require-login', (event) => {
  if (!mainWindow || event.sender.id !== mainWindow.webContents.id || !backendOrigin) {
    return { success: false, message: '当前窗口无法返回登录界面' }
  }

  desktopLoginPassed = false
  const loginQuery = new URLSearchParams({
    login_window: '1',
    system_name: activeSystemName
  })
  createLoginWindow(`${backendOrigin}/login?${loginQuery.toString()}`, activeSystemName)
  mainWindow.close()
  return { success: true }
})

ipcMain.handle('desktop-setup:complete', async (_event, payload = {}) => {
  if (!setupResolver) {
    return { success: false, message: '当前没有待完成的首次配置' }
  }

  const systemRegion = String(payload.systemRegion || '').trim()
  const normalizedRegion = systemRegion.slice(0, 80)
  const securityQuestions = Array.isArray(payload.securityQuestions) ? payload.securityQuestions : []
  if (securityQuestions.length !== 3) {
    return { success: false, message: '请设置 3 个不同的密码保护问题及答案' }
  }
  const questionIds = securityQuestions.map((item) => String(item?.question_id || ''))
  if (new Set(questionIds).size !== 3 || securityQuestions.some((item) => !String(item?.answer || '').trim())) {
    return { success: false, message: '请选择 3 个不同的问题并填写答案' }
  }
  const desktopConfig = {
    initialized: true,
    systemName: `${normalizedRegion}${DEFAULT_SYSTEM_NAME}`,
    systemRegion: normalizedRegion,
    securityQuestionsConfigured: true,
    securityQuestions
  }
  const persistedConfig = { ...desktopConfig }
  delete persistedConfig.securityQuestions
  fs.writeFileSync(setupConfigPath, JSON.stringify(persistedConfig, null, 2), { encoding: 'utf8', mode: 0o600 })
  const resolveSetup = setupResolver
  setupResolver = null
  setupWindow?.close()
  resolveSetup(desktopConfig)
  return { success: true }
})

app.whenReady().then(() => {
  startApplication().catch((error) => {
    const backendLogPath = path.join(app.getPath('userData'), 'logs', 'backend.log')
    dialog.showErrorBox(
      '离线版启动失败',
      `${String(error.message || error)}\n\n详细日志：${backendLogPath}`
    )
    app.quit()
  })
})

app.on('before-quit', () => {
  if (backendProcess && backendProcess.exitCode === null) {
    backendProcess.kill()
  }
  backendLogStream?.end()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length > 0) return
  if (desktopLoginPassed && backendOrigin) {
    createMainWindow(buildMainWindowUrl())
    return
  }
  app.quit()
})
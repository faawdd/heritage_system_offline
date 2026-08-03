const { app, BrowserWindow, dialog, ipcMain, Menu } = require('electron')
const path = require('path')
const fs = require('fs')
const crypto = require('crypto')
const { spawn } = require('child_process')
const http = require('http')
const net = require('net')
const os = require('os')
const AdmZip = require('adm-zip')

const BACKEND_HOST = process.env.BACKEND_HOST || '127.0.0.1'
const BACKEND_PORT = Number(process.env.BACKEND_PORT || 18000)
const CONFIG_FILE_NAME = 'desktop-config.json'
const DEFAULT_SYSTEM_NAME = '文物管理系统（离线版）'

let backendProcess = null
let backendLogStream = null
let mainWindow = null
let loginWindow = null
let initWizardWindow = null
let runtimeConfig = null
let bootstrapAdminPassword = ''
let desktopLoginPassed = false

const LOCAL_ADMIN_USERNAME = 'test'
const LOCAL_ADMIN_SALT = 'b2f3a1d94c6e7f80'
const LOCAL_ADMIN_HASH = 'ff966bdaab84e50ef7b3350ed4c1b5b7ad65bd8ff8f360151e0facec47ee6621acaa478b692e9af09c36673a8b4a3b1a8949eb69cb7cd8220610946cb4e63207'
const LEGACY_LOCAL_ADMIN_USERNAME = 'admin'
const LEGACY_LOCAL_ADMIN_HASH = '3e7faae0c71b4dc6ef521af75f9db14c07edd1163db5542b81b81201e3a2eda47c0b4a36ca7be01adb5b4c70e747229b4f7ae3bef0387275f710eb9b4a884ed5'

function formatTimestamp(date = new Date()) {
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
}

function copyDirSync(fromPath, toPath) {
  fs.mkdirSync(toPath, { recursive: true })
  fs.cpSync(fromPath, toPath, { recursive: true, force: true })
}

function clearDirSync(targetPath) {
  if (fs.existsSync(targetPath)) {
    fs.rmSync(targetPath, { recursive: true, force: true })
  }
  fs.mkdirSync(targetPath, { recursive: true })
}

function getConfigPath() {
  return path.join(app.getPath('userData'), CONFIG_FILE_NAME)
}

function normalizeSystemRegion(value = '') {
  return String(value || '').trim()
}

function buildSystemName(systemRegion = '') {
  const normalizedRegion = normalizeSystemRegion(systemRegion)
  return normalizedRegion ? `${normalizedRegion}文物管理系统` : DEFAULT_SYSTEM_NAME
}

function normalizeDesktopConfig(rawConfig = {}) {
  const systemRegion = normalizeSystemRegion(rawConfig.systemRegion)
  const configuredSystemName = String(rawConfig.systemName || '').trim()

  return {
    ...rawConfig,
    backendPort: Number(rawConfig.backendPort || BACKEND_PORT),
    systemRegion,
    systemName: configuredSystemName || buildSystemName(systemRegion),
    systemNameConfigured: Boolean(rawConfig.systemNameConfigured),
  }
}

function requiresInitialization(config = {}) {
  const normalized = normalizeDesktopConfig(config)
  const dbFilePath = path.join(String(normalized.dataDir || ''), 'database.db')
  const hasDatabase = Boolean(dbFilePath) && fs.existsSync(dbFilePath)
  return !normalized.initialized || !normalized.systemNameConfigured || !hasDatabase
}

function ensureDirectoryExists(dirPath) {
  try {
    fs.mkdirSync(dirPath, { recursive: true })
  } catch (_error) {
    // Keep initialization resilient and let writable checks report concrete errors.
  }
}

function getDefaultConfig() {
  const packagedInstallRoot = path.dirname(process.execPath)
  const useInstallRootDefaults = app.isPackaged && process.platform === 'win32'
  const defaultRoot = useInstallRootDefaults ? packagedInstallRoot : app.getPath('userData')

  const defaults = {
    initialized: false,
    dataDir: path.join(defaultRoot, 'data'),
    logDir: path.join(defaultRoot, 'logs'),
    backendPort: BACKEND_PORT,
    openImportAfterInit: false,
    bootstrapAdminPassword: '',
    systemRegion: '',
    systemName: DEFAULT_SYSTEM_NAME,
    systemNameConfigured: false,
  }

  ensureDirectoryExists(defaults.dataDir)
  ensureDirectoryExists(defaults.logDir)
  return defaults
}

function loadDesktopConfig() {
  const defaults = getDefaultConfig()
  const configPath = getConfigPath()

  if (!fs.existsSync(configPath)) {
    return normalizeDesktopConfig(defaults)
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(configPath, 'utf-8'))
    return normalizeDesktopConfig({
      ...defaults,
      ...parsed,
    })
  } catch (error) {
    return normalizeDesktopConfig(defaults)
  }
}

function saveDesktopConfig(config) {
  const merged = normalizeDesktopConfig({
    ...getDefaultConfig(),
    ...config,
  })

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
  const normalized = normalizeDesktopConfig({
    ...getDefaultConfig(),
    ...config,
  })

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

  const repoRoot = path.resolve(__dirname, '..', '..')
  const appDir = app.isPackaged
    ? path.join(process.resourcesPath, 'runtime', 'app')
    : repoRoot
  const configDir = app.isPackaged
    ? path.join(process.resourcesPath, 'runtime', 'config')
    : path.join(repoRoot, 'config')

  const backendEnv = {
    ...process.env,
    BACKEND_HOST: BACKEND_HOST,
    BACKEND_PORT: String(config.backendPort),
    SYSTEM_REGION: String(config.systemRegion || ''),
    SYSTEM_NAME: String(config.systemName || DEFAULT_SYSTEM_NAME),
    HERITAGE_APP_DIR: appDir,
    HERITAGE_DATA_DIR: config.dataDir,
    HERITAGE_CONFIG_DIR: configDir,
    HERITAGE_LOG_DIR: config.logDir,
    DJANGO_DEBUG: '1',
    DJANGO_FORCE_HTTPS: '0',
    DJANGO_WEB_BASE_URL: `http://${BACKEND_HOST}:${config.backendPort}`,
  }

  const bootstrapPassword = String(bootstrapAdminPassword || config.bootstrapAdminPassword || '')
  if (bootstrapPassword) {
    backendEnv.HERITAGE_BOOTSTRAP_ADMIN_PASSWORD = bootstrapPassword
  }

  if (app.isPackaged) {
    const backendFileName = process.platform === 'win32' ? 'heritage_backend.exe' : 'heritage_backend'
    const backendPath = path.join(process.resourcesPath, 'runtime', 'app', backendFileName)

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

function sanitizeRoutePath(routePath = '/') {
  const value = String(routePath || '').trim()
  if (!value) {
    return '/'
  }
  return value.startsWith('/') ? value : `/${value}`
}

function buildRendererUrl(routePath = '/') {
  const effectivePort = runtimeConfig?.backendPort || BACKEND_PORT
  const base = process.env.ELECTRON_START_URL || `http://${BACKEND_HOST}:${effectivePort}`
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  return `${normalizedBase}${sanitizeRoutePath(routePath)}`
}

function derivePasswordHash(password, salt) {
  return crypto.scryptSync(String(password), String(salt), 64).toString('hex')
}

function safeCompareHash(left, right) {
  const leftBuffer = Buffer.from(String(left), 'utf-8')
  const rightBuffer = Buffer.from(String(right), 'utf-8')
  if (leftBuffer.length !== rightBuffer.length) {
    return false
  }
  return crypto.timingSafeEqual(leftBuffer, rightBuffer)
}

function verifyLocalAdmin(username, password) {
  const normalizedUsername = String(username || '').trim()
  const computedHash = derivePasswordHash(String(password || ''), LOCAL_ADMIN_SALT)

  if (normalizedUsername === LOCAL_ADMIN_USERNAME) {
    return safeCompareHash(computedHash, LOCAL_ADMIN_HASH)
  }

  // Backward compatibility for users who still have remembered admin/admin123.
  if (normalizedUsername === LEGACY_LOCAL_ADMIN_USERNAME) {
    return safeCompareHash(computedHash, LEGACY_LOCAL_ADMIN_HASH)
  }

  return false
}

function resolveMainEntryPath() {
  if (!runtimeConfig?.openImportAfterInit || process.env.ELECTRON_START_URL) {
    return '/dashboard?desktop_auth=1'
  }

  runtimeConfig = {
    ...runtimeConfig,
    openImportAfterInit: false,
  }
  saveDesktopConfig(runtimeConfig)
  return '/system/data-management?fromSetup=1&desktop_auth=1'
}

function createMainWindow(routePath = '/dashboard?desktop_auth=1') {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1100,
    minHeight: 700,
    title: String(runtimeConfig?.systemName || DEFAULT_SYSTEM_NAME),
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  mainWindow.once('ready-to-show', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show()
      mainWindow.focus()
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.loadURL(buildRendererUrl(routePath)).catch((error) => {
    dialog.showErrorBox('主窗口加载失败', String(error?.message || error))
  })
}

function createLoginWindow() {
  loginWindow = new BrowserWindow({
    width: 420,
    height: 500,
    minWidth: 420,
    maxWidth: 420,
    minHeight: 500,
    maxHeight: 500,
    useContentSize: true,
    resizable: false,
    minimizable: true,
    maximizable: false,
    fullscreenable: false,
    frame: false,
    autoHideMenuBar: true,
    show: false,
    title: '登录',
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  loginWindow.once('ready-to-show', () => {
    if (loginWindow && !loginWindow.isDestroyed()) {
      loginWindow.show()
      loginWindow.focus()
    }
  })

  loginWindow.on('closed', () => {
    loginWindow = null
    if (!desktopLoginPassed && !mainWindow && process.platform !== 'darwin') {
      app.quit()
    }
  })

  loginWindow.loadURL(buildRendererUrl('/login?login_window=1')).catch((error) => {
    dialog.showErrorBox('登录窗口加载失败', String(error?.message || error))
  })
}

function setupAuthIpc() {
  ipcMain.handle('auth:login', async (_event, payload = {}) => {
    try {
      const username = String(payload?.username || '').trim()
      const password = String(payload?.password || '')

      if (!username || !password) {
        return {
          success: false,
          message: '请输入用户名和密码',
        }
      }

      const verified = verifyLocalAdmin(username, password)
      if (!verified) {
        return {
          success: false,
          message: '账号或密码错误',
        }
      }

      desktopLoginPassed = true
      if (!mainWindow || mainWindow.isDestroyed()) {
        createMainWindow(resolveMainEntryPath())
      } else {
        mainWindow.show()
        mainWindow.focus()
      }

      if (loginWindow && !loginWindow.isDestroyed()) {
        loginWindow.close()
      }

      return {
        success: true,
        message: '登录成功',
      }
    } catch (error) {
      return {
        success: false,
        message: `登录校验失败: ${String(error?.message || error)}`,
      }
    }
  })

  ipcMain.handle('auth:close-login-window', async () => {
    try {
      if (loginWindow && !loginWindow.isDestroyed()) {
        loginWindow.close()
        return {
          success: true,
          message: '窗口已关闭',
        }
      }

      return {
        success: false,
        message: '登录窗口不存在',
      }
    } catch (error) {
      return {
        success: false,
        message: `关闭窗口失败: ${String(error?.message || error)}`,
      }
    }
  })

  ipcMain.handle('auth:logout-to-login', async () => {
    try {
      desktopLoginPassed = false

      if (!loginWindow || loginWindow.isDestroyed()) {
        createLoginWindow()
      } else {
        loginWindow.show()
        loginWindow.focus()
      }

      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.close()
      }

      return {
        success: true,
        message: '已退出并返回登录窗口',
      }
    } catch (error) {
      return {
        success: false,
        message: `退出失败: ${String(error?.message || error)}`,
      }
    }
  })
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
      openImportAfterInit: Boolean(payload.openImportAfterInit),
      initialized: true,
      backendPort: chosenPort,
      bootstrapAdminPassword: '',
      systemRegion: normalizeSystemRegion(payload.systemRegion || current.systemRegion),
      systemNameConfigured: true,
    }

    merged.systemName = buildSystemName(merged.systemRegion)

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

    const superAdminPassword = String(payload.superAdminPassword || '').trim()
    if (superAdminPassword.length < 6) {
      return {
        ok: false,
        message: '超级管理员密码长度不能少于 6 位',
      }
    }

    merged.bootstrapAdminPassword = superAdminPassword
    saveDesktopConfig(merged)
    runtimeConfig = merged
    bootstrapAdminPassword = superAdminPassword
    return { ok: true }
  })

  ipcMain.handle('desktop-data:pick-backup-dir', async () => {
    const parentWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null
    const result = await dialog.showOpenDialog(parentWindow, {
      title: '选择备份存放目录',
      defaultPath: app.getPath('documents'),
      properties: ['openDirectory', 'createDirectory'],
    })

    if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
      return { canceled: true }
    }

    return { canceled: false, path: result.filePaths[0] }
  })

  ipcMain.handle('desktop-data:create-backup', async (_event, payload = {}) => {
    const destinationRoot = String(payload.destinationRoot || '').trim()
    if (!destinationRoot) {
      return { ok: false, message: '请选择备份目录' }
    }

    const config = runtimeConfig || loadDesktopConfig()
    const backupName = `heritage_backup_${formatTimestamp()}.zip`
    const backupPath = path.join(destinationRoot, backupName)

    try {
      const zip = new AdmZip()

      if (fs.existsSync(config.dataDir)) {
        zip.addLocalFolder(config.dataDir, 'data')
      }

      if (fs.existsSync(config.logDir)) {
        zip.addLocalFolder(config.logDir, 'logs')
      }

      const desktopConfigPath = getConfigPath()
      if (fs.existsSync(desktopConfigPath)) {
        zip.addLocalFile(desktopConfigPath, '', 'desktop-config.json')
      }

      const metadata = {
        backup_at: new Date().toISOString(),
        data_dir: config.dataDir,
        log_dir: config.logDir,
        backend_port: config.backendPort,
      }
      zip.addFile('metadata.json', Buffer.from(JSON.stringify(metadata, null, 2), 'utf-8'))
      zip.writeZip(backupPath)

      return {
        ok: true,
        message: '备份完成',
        backupPath,
      }
    } catch (error) {
      return { ok: false, message: `备份失败: ${String(error?.message || error)}` }
    }
  })

  ipcMain.handle('desktop-data:pick-restore-file', async () => {
    const parentWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null
    const result = await dialog.showOpenDialog(parentWindow, {
      title: '选择要恢复的备份压缩包',
      defaultPath: app.getPath('documents'),
      properties: ['openFile'],
      filters: [{ name: '备份压缩包', extensions: ['zip'] }],
    })

    if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
      return { canceled: true }
    }

    return { canceled: false, path: result.filePaths[0] }
  })

  ipcMain.handle('desktop-data:restore-backup', async (_event, payload = {}) => {
    const backupPath = String(payload.backupPath || '').trim()
    if (!backupPath) {
      return { ok: false, message: '请选择备份压缩包' }
    }

    if (!fs.existsSync(backupPath)) {
      return { ok: false, message: '备份文件不存在' }
    }

    const config = runtimeConfig || loadDesktopConfig()
    const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'heritage-restore-'))
    const unpackRoot = path.join(tempRoot, 'unpack')

    try {
      const zip = new AdmZip(backupPath)
      zip.extractAllTo(unpackRoot, true)

      const dataBackupPath = path.join(unpackRoot, 'data')
      if (!fs.existsSync(dataBackupPath)) {
        throw new Error('备份压缩包缺少 data 目录')
      }

      stopBackend()
      clearDirSync(config.dataDir)
      copyDirSync(dataBackupPath, config.dataDir)

      const logsBackupPath = path.join(unpackRoot, 'logs')
      if (fs.existsSync(logsBackupPath)) {
        clearDirSync(config.logDir)
        copyDirSync(logsBackupPath, config.logDir)
      }

      dialog.showMessageBox({
        type: 'info',
        title: '恢复完成',
        message: '用户数据恢复成功，应用将自动重启。',
        buttons: ['确定'],
      }).finally(() => {
        app.relaunch()
        app.exit(0)
      })

      return { ok: true, message: '恢复完成，正在重启应用' }
    } catch (error) {
      return { ok: false, message: `恢复失败: ${String(error?.message || error)}` }
    } finally {
      if (fs.existsSync(tempRoot)) {
        fs.rmSync(tempRoot, { recursive: true, force: true })
      }
    }
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

app.whenReady().then(async () => {
  try {
    setupApplicationMenu()
    setupInitIpc()
    setupAuthIpc()

    if (!process.env.ELECTRON_START_URL) {
      const loaded = loadDesktopConfig()
      runtimeConfig = loaded

      if (requiresInitialization(loaded)) {
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

      if (runtimeConfig?.bootstrapAdminPassword) {
        runtimeConfig = {
          ...runtimeConfig,
          bootstrapAdminPassword: '',
        }
        saveDesktopConfig(runtimeConfig)
      }
      bootstrapAdminPassword = ''
    }

    createLoginWindow()
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

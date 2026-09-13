// 桌面启动链路回归（无需 GUI）：用假的 electron 运行时加载真实的 frontend/electron/main.cjs，
// 覆盖四个场景，全部使用系统临时目录，不污染仓库 data/ 与 config/：
//
//   1) first          全新安装：开初始化向导 -> 向导回传空配置不得覆盖默认目录 -> 保存配置
//                     -> （假后端进程立即退出）必须给出可诊断的启动失败信息并退出
//   2) second         配置已保存、但 database.db 尚不存在：不得再弹初始化向导（核心回归）
//   3) second-instance 已有实例正在启动（还没窗口）时重复点击图标：给“系统正在启动”提示，
//                     不重跑初始化检测
//   4) locked         单实例锁未拿到：直接退出，不建窗口、不弹框、不启动后端
//
// 用法：node scripts/dev/smoke_electron_startup.cjs

const Module = require('module')
const { spawnSync } = require('child_process')
const os = require('os')
const path = require('path')
const fs = require('fs')

const SCRIPT_PATH = __filename
const repoRoot = path.resolve(__dirname, '..', '..')
const mainCjsPath = process.env.SMOKE_MAIN_CJS
  ? path.resolve(process.env.SMOKE_MAIN_CJS)
  : path.join(repoRoot, 'frontend', 'electron', 'main.cjs')

// ---------------------------------------------------------------------------
// 子进程模式：真正加载 main.cjs 并跑一个场景，把结果以 JSON 打到 stdout
// ---------------------------------------------------------------------------

const stageArgIndex = process.argv.indexOf('--stage')

if (stageArgIndex !== -1) {
  runStageChild(process.argv[stageArgIndex + 1] || 'first')
} else {
  runAllStages()
}

function runStageChild(stage) {
  const root = path.join(os.tmpdir(), 'heritage-electron-smoke')
  const userData = path.join(root, 'userData')
  const resourcesPath = path.join(root, 'resources')
  const appDir = path.join(resourcesPath, 'runtime', 'app')
  const backendExePath = path.join(appDir, 'heritage_backend.exe')
  const dataDir = path.join(appDir, 'data')
  const logDir = path.join(appDir, 'logs')
  const databasePath = path.join(dataDir, 'database.db')
  const configPath = path.join(userData, 'desktop-config.json')

  if (stage === 'first') {
    fs.rmSync(root, { recursive: true, force: true })
  }

  fs.mkdirSync(appDir, { recursive: true })
  fs.mkdirSync(userData, { recursive: true })

  // 用 node.exe 充当“后端可执行文件”：它会在没有脚本时很快自行退出，
  // 正好用来验证“后端进程提前退出”时启动失败信息是否可诊断。
  fs.copyFileSync(process.execPath, backendExePath)

  // 预置一行日志，验证启动失败对话框会带上 backend.log 末尾内容。
  fs.mkdirSync(logDir, { recursive: true })
  fs.appendFileSync(path.join(logDir, 'backend.log'), '[BOOTSTRAP-SENTINEL] previous run failed\n')

  const summary = {
    stage,
    wizardWindows: 0,
    loginWindows: 0,
    errorBoxes: [],
    messageBoxes: [],
    quitCalled: false,
    databaseExists: false,
  }

  const windows = []
  const handlers = new Map()
  const listeners = new Map()
  const appListeners = new Map()
  let quitCalled = false
  let resolveReady
  const whenReadyPromise = new Promise((resolve) => {
    resolveReady = resolve
  })

  class FakeBrowserWindow {
    constructor(options = {}) {
      this.options = options
      this.destroyed = false
      this.minimized = false
      this.onceHandlers = {}
      this.onHandlers = {}
      windows.push(this)
    }

    loadFile(filePath) {
      this.target = String(filePath)
      return Promise.resolve()
    }

    loadURL(url) {
      this.target = String(url)
      return Promise.resolve()
    }

    once(event, cb) {
      this.onceHandlers[event] = cb
      return this
    }

    on(event, cb) {
      this.onHandlers[event] = cb
      return this
    }

    show() {}

    focus() {}

    restore() {
      this.minimized = false
    }

    isMinimized() {
      return this.minimized
    }

    isDestroyed() {
      return this.destroyed
    }

    close() {
      this.destroyed = true
      // 真实 Electron 的 'closed' 事件是异步的，这里保持一致。
      setImmediate(() => {
        if (this.onHandlers.closed) {
          this.onHandlers.closed()
        }
      })
    }

    destroy() {
      this.destroyed = true
    }
  }

  const fakeElectron = {
    app: {
      name: 'heritage_backend',
      isPackaged: true,
      getPath(name) {
        return name === 'userData' ? userData : path.join(root, 'userdir', name)
      },
      getAppPath() {
        return appDir
      },
      requestSingleInstanceLock() {
        return process.env.SMOKE_NO_SINGLE_INSTANCE_LOCK === '1' ? false : true
      },
      on(event, cb) {
        const list = appListeners.get(event) || []
        list.push(cb)
        appListeners.set(event, list)
      },
      whenReady() {
        return whenReadyPromise
      },
      quit() {
        quitCalled = true
      },
      relaunch() {},
      exit() {},
    },
    BrowserWindow: FakeBrowserWindow,
    dialog: {
      showErrorBox(title, content) {
        summary.errorBoxes.push({ title, content: String(content == null ? '' : content) })
      },
      showMessageBox(options) {
        summary.messageBoxes.push(options)
        return Promise.resolve({ response: 0 })
      },
      showOpenDialog() {
        return Promise.resolve({ canceled: true, filePaths: [] })
      },
    },
    ipcMain: {
      handle(channel, fn) {
        handlers.set(channel, fn)
      },
      on(channel, fn) {
        const list = listeners.get(channel) || []
        list.push(fn)
        listeners.set(channel, list)
      },
      once(channel, fn) {
        listeners.set(channel, [fn])
      },
    },
    Menu: {
      buildFromTemplate() {
        return {}
      },
      setApplicationMenu() {},
    },
  }

  const stubPath = path.join(__dirname, 'electron-smoke-stub.js')
  require.cache[stubPath] = {
    id: stubPath,
    filename: stubPath,
    loaded: true,
    exports: fakeElectron,
    children: [],
    paths: [],
  }
  const originalResolve = Module._resolveFilename
  Module._resolveFilename = function (request, ...rest) {
    if (request === 'electron') {
      return stubPath
    }
    return originalResolve.call(this, request, ...rest)
  }

  process.resourcesPath = resourcesPath
  try {
    process.execPath = backendExePath
  } catch (_error) {
    Object.defineProperty(process, 'execPath', { value: backendExePath, configurable: true })
  }

  require(mainCjsPath)

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

  async function waitUntil(predicate, timeoutMs, label) {
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
      if (predicate()) {
        return
      }
      await sleep(50)
    }
    throw new Error(`timeout waiting for ${label}`)
  }

  function collectWindows() {
    summary.wizardWindows = windows.filter((win) => String(win.target || '').endsWith('wizard.html')).length
    summary.loginWindows = windows.filter((win) => String(win.target || '').includes('/login')).length
  }

  function emit(channel) {
    const list = listeners.get(channel) || []
    listeners.set(channel, [])
    list.forEach((fn) => fn())
  }

  async function main() {
    resolveReady()

    if (stage === 'first') {
      await waitUntil(
        () => windows.some((win) => String(win.target || '').endsWith('wizard.html')),
        8000,
        'wizard window',
      )
      await waitUntil(() => handlers.has('desktop-init:get-state'), 8000, 'ipc handlers')

      const getState = handlers.get('desktop-init:get-state')
      const complete = handlers.get('desktop-init:complete')

      // 1) 向导渲染进程首次加载时会把自己那份（dataDir/logDir 为空串）配置整份回传
      const legacyState = await getState(null, {
        dataDir: '',
        logDir: '',
        backendPort: 18000,
        systemRegion: '',
        systemName: '文物管理系统（离线版）',
      })
      summary.legacyGetState = {
        dataDir: legacyState.config.dataDir,
        logDir: legacyState.config.logDir,
        dataDirOk: legacyState.checks.dataDir.ok,
        logDirOk: legacyState.checks.logDir.ok,
        dataDirMessage: legacyState.checks.dataDir.message,
      }

      // 2) 修复后的向导只回传非空字段，效果必须与上面一致
      const state = await getState(null, { backendPort: 18000 })
      summary.trimmedGetState = {
        dataDir: state.config.dataDir,
        dataDirOk: state.checks.dataDir.ok,
      }

      // 3) 用户填完向导并保存
      summary.completeResult = await complete(null, {
        backendPort: 18000,
        dataDir: state.config.dataDir,
        logDir: state.config.logDir,
        systemRegion: '',
        superAdminPassword: 'admin12345',
        openImportAfterInit: false,
      })
      summary.savedConfig = fs.existsSync(configPath) ? JSON.parse(fs.readFileSync(configPath, 'utf-8')) : null

      emit('desktop-init:finished')
      await sleep(3000)
    } else if (stage === 'locked') {
      await sleep(1500)
    } else if (stage === 'second-instance') {
      await sleep(1500)
      const list = appListeners.get('second-instance') || []
      list.forEach((fn) => fn())
      await sleep(300)
    } else {
      // 第二次启动：配置已保存，但数据库文件缺失（首次启动后端没能创建它）
      await sleep(3000)
    }

    finish()
  }

  function finish(error) {
    collectWindows()
    summary.quitCalled = quitCalled
    summary.databaseExists = fs.existsSync(databasePath)
    if (error) {
      summary.fatal = String((error && error.stack) || error)
    }
    console.log(JSON.stringify(summary, null, 2))
    process.exit(error ? 1 : 0)
  }

  main().catch(finish)
}

// ---------------------------------------------------------------------------
// 主进程模式：依次跑四个场景并汇总断言
// ---------------------------------------------------------------------------

function runAllStages() {
  const scenarios = [
    { stage: 'first', env: {}, timeoutMs: 60000 },
    { stage: 'second', env: {}, timeoutMs: 60000 },
    { stage: 'second-instance', env: {}, timeoutMs: 60000 },
    { stage: 'locked', env: { SMOKE_NO_SINGLE_INSTANCE_LOCK: '1' }, timeoutMs: 60000 },
  ]

  const results = []
  let current = ''

  function expect(name, condition, detail = '') {
    results.push({ scenario: current, name, ok: Boolean(condition), detail: condition ? '' : detail })
  }

  function runChild(scenario) {
    const child = spawnSync(process.execPath, [SCRIPT_PATH, '--stage', scenario.stage], {
      env: { ...process.env, ...scenario.env },
      encoding: 'utf-8',
      timeout: scenario.timeoutMs,
    })
    if (child.error) {
      throw new Error(`spawn failed: ${child.error.message}`)
    }
    const stdout = String(child.stdout || '').trim()
    const jsonStart = stdout.indexOf('{')
    if (jsonStart === -1) {
      throw new Error(`child produced no JSON.\nstdout:\n${stdout}\nstderr:\n${child.stderr}`)
    }
    return JSON.parse(stdout.slice(jsonStart))
  }

  for (const scenario of scenarios) {
    current = scenario.stage
    let summary
    try {
      summary = runChild(scenario)
    } catch (error) {
      expect(`${scenario.stage}: child run`, false, String(error.message || error))
      continue
    }

    if (summary.fatal) {
      expect(`${scenario.stage}: child run`, false, summary.fatal)
      continue
    }

    const errorText = summary.errorBoxes.map((box) => box.content).join('\n')

    if (scenario.stage === 'first') {
      expect('first: 打开初始化向导', summary.wizardWindows === 1, `wizardWindows=${summary.wizardWindows}`)
      expect(
        'first: 向导回传空目录不覆盖默认 dataDir',
        summary.legacyGetState && summary.legacyGetState.dataDirOk === true && summary.legacyGetState.dataDir,
        JSON.stringify(summary.legacyGetState),
      )
      expect(
        'first: 向导回传空目录不覆盖默认 logDir',
        summary.legacyGetState && summary.legacyGetState.logDirOk === true,
        JSON.stringify(summary.legacyGetState),
      )
      expect(
        'first: 只回传非空字段同样通过校验',
        summary.trimmedGetState && summary.trimmedGetState.dataDirOk === true,
        JSON.stringify(summary.trimmedGetState),
      )
      expect(
        'first: 保存的配置已初始化且保留默认目录',
        summary.savedConfig &&
          summary.savedConfig.initialized === true &&
          summary.savedConfig.dataDir === (summary.legacyGetState || {}).dataDir,
        JSON.stringify(summary.savedConfig),
      )
      expect('first: 数据库文件确实不存在（模拟后端未创建）', summary.databaseExists === false)
      expect('first: 后端退出时给出失败对话框', summary.errorBoxes.length === 1, errorText)
      expect('first: 失败信息含退出码', errorText.includes('后端进程已退出'), errorText)
      expect('first: 失败信息含日志路径与末尾日志', errorText.includes('日志文件') && errorText.includes('BOOTSTRAP-SENTINEL'), errorText)
      expect('first: 失败信息提示可重试且无需重新初始化', errorText.includes('无需再次初始化'), errorText)
      expect('first: 失败后退出应用', summary.quitCalled === true)
    }

    if (scenario.stage === 'second') {
      expect('second: database.db 缺失时不再弹初始化向导', summary.wizardWindows === 0, `wizardWindows=${summary.wizardWindows}`)
      expect('second: 仍给出可诊断的后端失败信息', errorText.includes('后端进程已退出'), errorText)
      expect('second: 失败后退出应用', summary.quitCalled === true)
    }

    if (scenario.stage === 'second-instance') {
      expect('second-instance: 不重跑初始化向导', summary.wizardWindows === 0, `wizardWindows=${summary.wizardWindows}`)
      const titles = summary.messageBoxes.map((box) => box.title)
      expect('second-instance: 提示“系统正在启动”', titles.includes('系统正在启动'), JSON.stringify(titles))
    }

    if (scenario.stage === 'locked') {
      expect('locked: 直接退出', summary.quitCalled === true)
      expect('locked: 不建任何窗口', summary.wizardWindows === 0 && summary.loginWindows === 0)
      expect('locked: 不弹错误框', summary.errorBoxes.length === 0, errorText)
      expect('locked: 不弹提示框', summary.messageBoxes.length === 0, JSON.stringify(summary.messageBoxes))
    }
  }

  const passed = results.filter((item) => item.ok).length
  console.log('')
  for (const item of results) {
    if (!item.ok) {
      console.log(`[FAIL] ${item.name}`)
      if (item.detail) {
        console.log(`       ${item.detail.replace(/\n/g, '\n       ')}`)
      }
    } else {
      console.log(`[ ok ] ${item.name}`)
    }
  }
  console.log('')
  console.log(`ELECTRON-STARTUP SUMMARY: ${passed}/${results.length} passed`)

  fs.rmSync(path.join(os.tmpdir(), 'heritage-electron-smoke'), { recursive: true, force: true })
  process.exit(passed === results.length ? 0 : 1)
}

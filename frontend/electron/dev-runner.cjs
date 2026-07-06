const { spawn, spawnSync } = require('child_process')
const http = require('http')
const path = require('path')
const fs = require('fs')

const repoRoot = path.resolve(__dirname, '..', '..')
const frontendRoot = path.resolve(__dirname, '..')

let viteProcess = null
let backendProcess = null
let electronProcess = null

function parseIntOr(defaultValue, raw) {
  const parsed = Number(raw)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : defaultValue
}

function normalizeBasePath(rawPath) {
  const value = String(rawPath || '/static/frontend').trim()
  if (!value) {
    return '/static/frontend'
  }
  if (value === '/') {
    return '/'
  }
  const withLeadingSlash = value.startsWith('/') ? value : `/${value}`
  return withLeadingSlash.endsWith('/') ? withLeadingSlash.slice(0, -1) : withLeadingSlash
}

const viteHost = process.env.HERITAGE_DESKTOP_VITE_HOST || '127.0.0.1'
const vitePort = parseIntOr(5173, process.env.HERITAGE_DESKTOP_VITE_PORT)
const backendHost = process.env.HERITAGE_DESKTOP_BACKEND_HOST || '127.0.0.1'
const backendPort = parseIntOr(18000, process.env.HERITAGE_DESKTOP_BACKEND_PORT)
const devBasePath = normalizeBasePath(process.env.HERITAGE_DESKTOP_DEV_BASE_PATH || '/static/frontend')

const viteOrigin = `http://${viteHost}:${vitePort}`
const backendOrigin = `http://${backendHost}:${backendPort}`
const viteStartUrl = process.env.HERITAGE_DESKTOP_ELECTRON_START_URL || `${viteOrigin}${devBasePath}`

function resolveElectronBinaryPath() {
  try {
    const resolved = require('electron')
    if (!resolved) {
      return null
    }
    return fs.existsSync(resolved) ? resolved : null
  } catch (_error) {
    return null
  }
}

function runSyncCommand(cmd, args, cwd) {
  return spawnSync(cmd, args, {
    cwd,
    env: {
      ...process.env,
    },
    stdio: 'inherit',
    shell: process.platform === 'win32',
  })
}

function ensureElectronRuntimeReady() {
  const directPath = resolveElectronBinaryPath()
  if (directPath) {
    return directPath
  }

  console.warn('[desktop:dev] Electron runtime appears missing/corrupted, trying npm rebuild electron...')
  const rebuildResult = runSyncCommand('npm', ['rebuild', 'electron'], frontendRoot)
  if (rebuildResult.status === 0) {
    const rebuiltPath = resolveElectronBinaryPath()
    if (rebuiltPath) {
      return rebuiltPath
    }
  }

  console.warn('[desktop:dev] npm rebuild did not recover Electron, trying npm install electron --no-save...')
  const installResult = runSyncCommand('npm', ['install', 'electron@^32.2.1', '--no-save'], frontendRoot)
  if (installResult.status === 0) {
    const installedPath = resolveElectronBinaryPath()
    if (installedPath) {
      return installedPath
    }
  }

  return null
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

async function waitUntil(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await canConnect(url)) {
      return true
    }
    await new Promise((resolve) => setTimeout(resolve, 400))
  }
  return false
}

function resolveDevPython() {
  const venvPython = process.platform === 'win32'
    ? path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(repoRoot, '.venv', 'bin', 'python')

  if (fs.existsSync(venvPython)) {
    return venvPython
  }

  return process.platform === 'win32' ? 'python' : 'python3'
}

function spawnWithInheritedLogs(cmd, args, cwd, env = {}, options = {}) {
  return spawn(cmd, args, {
    cwd,
    env: {
      ...process.env,
      ...env,
    },
    stdio: 'inherit',
    shell: options.shell ?? (process.platform === 'win32'),
  })
}

function cleanup() {
  for (const child of [electronProcess, backendProcess, viteProcess]) {
    if (!child || child.killed) {
      continue
    }

    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(child.pid), '/f', '/t'])
      } else {
        child.kill('SIGTERM')
      }
    } catch (err) {
      // Ignore cleanup errors.
    }
  }
}

async function run() {
  viteProcess = spawnWithInheritedLogs('npm', ['run', 'dev', '--', '--host', viteHost, '--port', String(vitePort)], frontendRoot)

  const pythonCmd = resolveDevPython()
  backendProcess = spawnWithInheritedLogs(
    pythonCmd,
    ['manage.py', 'runserver', `${backendHost}:${backendPort}`],
    repoRoot,
    {
      DJANGO_DEBUG: '1',
      DJANGO_FORCE_HTTPS: '0',
      DJANGO_WEB_BASE_URL: backendOrigin,
    }
  )

  const [viteReady, backendReady] = await Promise.all([
    waitUntil(`${viteOrigin}${devBasePath}/`, 30000),
    waitUntil(`${backendOrigin}/api/v1/health/`, 30000),
  ])

  if (!viteReady || !backendReady) {
    console.error('[desktop:dev] 启动失败：Vite 或 Django 未就绪。')
    cleanup()
    process.exit(1)
  }

  const electronBinaryPath = ensureElectronRuntimeReady()
  if (!electronBinaryPath) {
    console.error('[desktop:dev] Electron runtime is still unavailable after recovery attempts.')
    console.error('[desktop:dev] Try: rm -rf frontend/node_modules/electron && cd frontend && npm install')
    cleanup()
    process.exit(1)
  }

  electronProcess = spawnWithInheritedLogs(
    electronBinaryPath,
    ['.'],
    frontendRoot,
    {
      ELECTRON_START_URL: viteStartUrl,
      BACKEND_HOST: backendHost,
      BACKEND_PORT: String(backendPort),
    },
    {
      shell: false,
    }
  )

  electronProcess.on('exit', (code) => {
    cleanup()
    process.exit(code || 0)
  })
}

process.on('SIGINT', () => {
  cleanup()
  process.exit(130)
})
process.on('SIGTERM', () => {
  cleanup()
  process.exit(143)
})

run().catch((err) => {
  console.error('[desktop:dev] 未捕获错误:', err)
  cleanup()
  process.exit(1)
})

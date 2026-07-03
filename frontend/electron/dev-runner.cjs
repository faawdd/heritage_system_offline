const { spawn } = require('child_process')
const http = require('http')
const path = require('path')
const fs = require('fs')

const repoRoot = path.resolve(__dirname, '..', '..')
const frontendRoot = path.resolve(__dirname, '..')

let viteProcess = null
let backendProcess = null
let electronProcess = null

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

function spawnWithInheritedLogs(cmd, args, cwd, env = {}) {
  return spawn(cmd, args, {
    cwd,
    env: {
      ...process.env,
      ...env,
    },
    stdio: 'inherit',
    shell: process.platform === 'win32',
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
  viteProcess = spawnWithInheritedLogs('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173'], frontendRoot)

  const pythonCmd = resolveDevPython()
  backendProcess = spawnWithInheritedLogs(
    pythonCmd,
    ['manage.py', 'runserver', '127.0.0.1:18000'],
    repoRoot,
    {
      DJANGO_DEBUG: '1',
      DJANGO_FORCE_HTTPS: '0',
      DJANGO_WEB_BASE_URL: 'http://127.0.0.1:18000',
    }
  )

  const [viteReady, backendReady] = await Promise.all([
    waitUntil('http://127.0.0.1:5173', 30000),
    waitUntil('http://127.0.0.1:18000/api/v1/health/', 30000),
  ])

  if (!viteReady || !backendReady) {
    console.error('[desktop:dev] 启动失败：Vite 或 Django 未就绪。')
    cleanup()
    process.exit(1)
  }

  electronProcess = spawnWithInheritedLogs(
    'npx',
    ['electron', '.'],
    frontendRoot,
    {
      ELECTRON_START_URL: 'http://127.0.0.1:5173',
      BACKEND_HOST: '127.0.0.1',
      BACKEND_PORT: '18000',
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

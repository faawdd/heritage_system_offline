const DOWNLOAD_URL = 'https://beichenhome.top:9081/offline2/'
const STATUS_URL = `${DOWNLOAD_URL}status/`
const REQUEST_TIMEOUT_MS = 12000
const CHECK_TIMEOUT_MS = 45000
const POLL_INTERVAL_MS = 1000

function parseVersion(value) {
  if (typeof value !== 'string') throw new Error('版本号格式无效')
  const normalized = value.trim().replace(/-\d+-g[0-9a-f]+$/i, '')
  const match = /^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/.exec(normalized)
  if (!match) throw new Error(`无法识别版本号：${value}`)
  const numbers = match.slice(1, 4).map(Number)
  if (!numbers.every(Number.isSafeInteger)) throw new Error(`无法识别版本号：${value}`)
  const prerelease = match[4] ? match[4].split('.') : []
  if (prerelease.some(part => /^\d+$/.test(part) && (part.length > 1 && part.startsWith('0') || !Number.isSafeInteger(Number(part))))) {
    throw new Error(`无法识别版本号：${value}`)
  }
  return { numbers, prerelease }
}

function compareVersions(left, right) {
  const a = parseVersion(left)
  const b = parseVersion(right)
  for (let i = 0; i < 3; i++) {
    if (a.numbers[i] !== b.numbers[i]) return a.numbers[i] > b.numbers[i] ? 1 : -1
  }
  if (!a.prerelease.length || !b.prerelease.length) {
    return Number(!a.prerelease.length) - Number(!b.prerelease.length)
  }
  for (let i = 0; i < Math.max(a.prerelease.length, b.prerelease.length); i++) {
    const x = a.prerelease[i]
    const y = b.prerelease[i]
    if (x === undefined || y === undefined) return x === undefined ? -1 : 1
    if (x === y) continue
    const xNumeric = /^\d+$/.test(x)
    const yNumeric = /^\d+$/.test(y)
    if (xNumeric && yNumeric) return Number(x) > Number(y) ? 1 : -1
    if (xNumeric !== yNumeric) return xNumeric ? -1 : 1
    return x > y ? 1 : -1
  }
  return 0
}

async function request(fetchFn, url) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const response = await fetchFn(url, {
      method: 'GET', cache: 'no-store', credentials: 'omit', redirect: 'error', signal: controller.signal
    })
    if (!response.ok) throw new Error(`更新服务器返回 HTTP ${response.status}`)
    if (url === DOWNLOAD_URL) {
      await response.text()
      return null
    }
    return { data: await response.json(), serverDate: Date.parse(response.headers.get('date')) }
  } catch (error) {
    if (error?.name === 'AbortError') throw new Error('连接更新服务器超时，请稍后重试')
    throw error
  } finally {
    clearTimeout(timer)
  }
}

async function checkForUpdates(currentVersion, fetchFn, options = {}) {
  parseVersion(currentVersion)
  const now = options.now || Date.now
  const sleep = options.sleep || (ms => new Promise(resolve => setTimeout(resolve, ms)))
  const deadline = now() + CHECK_TIMEOUT_MS
  await request(fetchFn, DOWNLOAD_URL)
  await sleep(POLL_INTERVAL_MS)

  while (now() < deadline) {
    const { data, serverDate } = await request(fetchFn, STATUS_URL)
    if (!data || typeof data !== 'object') throw new Error('更新服务器返回了无效状态')
    if (data.checking === true) {
      await sleep(POLL_INTERVAL_MS)
      continue
    }
    if (data.last_check_ok !== true) throw new Error('下载站最近一次更新检查失败，请稍后重试')
    if (!Number.isFinite(data.last_check_at) || !Number.isFinite(data.check_interval)) {
      throw new Error('更新服务器未提供有效的检查时间')
    }
    const referenceTime = Number.isFinite(serverDate) ? serverDate : now()
    const ageSeconds = (referenceTime / 1000) - data.last_check_at
    if (ageSeconds > Math.max(75, data.check_interval + 15)) {
      await sleep(POLL_INTERVAL_MS)
      continue
    }
    const comparison = compareVersions(data.tag, currentVersion)
    return { latestVersion: data.tag, updateAvailable: comparison > 0, checkedAt: data.last_check_at }
  }
  throw new Error('下载站更新检查超时，请稍后重试')
}

module.exports = { DOWNLOAD_URL, STATUS_URL, compareVersions, checkForUpdates }

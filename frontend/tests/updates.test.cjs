const test = require('node:test')
const assert = require('node:assert/strict')
const { checkForUpdates, compareVersions, DOWNLOAD_URL, STATUS_URL } = require('../electron/updates.cjs')

function response(data, date = 'Fri, 06 Nov 2026 12:00:00 GMT') {
  return {
    ok: true,
    headers: { get: () => date },
    text: async () => 'release page',
    json: async () => data
  }
}

function status(overrides = {}) {
  return {
    tag: 'v2.2.8',
    checking: false,
    last_check_ok: true,
    last_check_at: Date.parse('Fri, 06 Nov 2026 12:00:00 GMT') / 1000,
    check_interval: 60,
    ...overrides
  }
}

test('compares release, prerelease and git-describe versions numerically', () => {
  assert.equal(compareVersions('v2.10.0', 'v2.9.9'), 1)
  assert.equal(compareVersions('v2.2.8', 'v2.2.8-rc.2'), 1)
  assert.equal(compareVersions('v2.2.8-rc.10', 'v2.2.8-rc.2'), 1)
  assert.equal(compareVersions('v2.2.7', 'v2.2.7-3-gabcdef0'), 0)
  assert.equal(compareVersions('v2.2.5', 'v2.2.7'), -1)
  assert.throws(() => compareVersions('latest', 'v2.2.7'), /版本号/)
})

test('triggers release sync, then checks status without credentials', async () => {
  const calls = []
  const result = await checkForUpdates('v2.2.7', async (url, options) => {
    calls.push({ url, options })
    return response(status())
  }, { sleep: async () => {} })
  assert.deepEqual(calls.map(call => call.url), [DOWNLOAD_URL, STATUS_URL])
  assert.equal(calls[0].options.credentials, 'omit')
  assert.equal(calls[0].options.redirect, 'error')
  assert.deepEqual(result, { latestVersion: 'v2.2.8', updateAvailable: true, checkedAt: status().last_check_at })
})

test('waits for the upstream check and does not report an older release as new', async () => {
  let requests = 0
  const result = await checkForUpdates('v2.2.7', async url => {
    if (url === DOWNLOAD_URL) return response({})
    requests++
    return response(requests === 1 ? status({ checking: true }) : status({ tag: 'v2.2.5' }))
  }, { sleep: async () => {} })
  assert.equal(requests, 2)
  assert.equal(result.updateAvailable, false)
})

test('surfaces network, upstream and invalid version errors', async () => {
  await assert.rejects(checkForUpdates('v2.2.7', async () => { throw new Error('offline') }), /offline/)
  await assert.rejects(checkForUpdates('v2.2.7', async () => {
    throw Object.assign(new Error('aborted'), { name: 'AbortError' })
  }), /超时/)
  await assert.rejects(checkForUpdates('v2.2.7', async () => ({ ok: false, status: 503 })), /HTTP 503/)
  await assert.rejects(checkForUpdates('v2.2.7', async url =>
    response(url === STATUS_URL ? status({ last_check_ok: false }) : {}), { sleep: async () => {} }), /检查失败/)
  await assert.rejects(checkForUpdates('v2.2.7', async url =>
    response(url === STATUS_URL ? status({ tag: '' }) : {}), { sleep: async () => {} }), /版本号/)
})

test('times out rather than reporting a stale server version as current', async () => {
  let time = Date.parse('Fri, 06 Nov 2026 12:00:00 GMT')
  await assert.rejects(checkForUpdates('v2.2.7', async url =>
    response(url === STATUS_URL ? status({ last_check_at: time / 1000 - 1000 }) : {}),
  { now: () => time, sleep: async ms => { time += ms } }), /超时/)
})

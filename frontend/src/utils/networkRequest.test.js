import assert from 'node:assert/strict'
import test from 'node:test'
import { KML_ACTION_TIMEOUT, MAP_REQUEST_TIMEOUT, requestMapData } from './networkRequest.js'

test('map reads and KML operations no longer use the global 20 second timeout', () => {
  assert.equal(MAP_REQUEST_TIMEOUT, 60000)
  assert.equal(KML_ACTION_TIMEOUT, 600000)
})

test('transient timeout retries at most twice and returns the recovered response', async () => {
  let calls = 0
  const result = await requestMapData(async () => {
    if (++calls < 3) throw Object.assign(new Error('timeout'), { code: 'ECONNABORTED' })
    return { success: true }
  }, { retryDelay: 0 })
  assert.deepEqual(result, { success: true })
  assert.equal(calls, 3)
})

test('persistent network failures surface after three attempts', async () => {
  let calls = 0
  const error = Object.assign(new Error('offline'), { code: 'ERR_NETWORK' })
  await assert.rejects(requestMapData(async () => {
    calls += 1
    throw error
  }, { retryDelay: 0 }), (actual) => actual === error)
  assert.equal(calls, 3)
})

test('authorization, invalid input and cancellation errors are never retried', async () => {
  for (const error of [
    { response: { status: 400 } }, { response: { status: 401 } },
    { response: { status: 403 } }, { response: { status: 404 } },
    { code: 'ERR_CANCELED' }
  ]) {
    let calls = 0
    await assert.rejects(requestMapData(async () => {
      calls += 1
      throw error
    }, { retryDelay: 0 }))
    assert.equal(calls, 1)
  }
})

test('cancelling during retry backoff stops the next request immediately', async () => {
  const controller = new AbortController()
  let calls = 0
  const promise = requestMapData(async () => {
    calls += 1
    throw Object.assign(new Error('offline'), { code: 'ERR_NETWORK' })
  }, { signal: controller.signal, retryDelay: 10000 })
  setTimeout(() => controller.abort(), 0)
  await assert.rejects(promise, { name: 'AbortError' })
  assert.equal(calls, 1)
})

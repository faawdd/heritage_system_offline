import assert from 'node:assert/strict'
import test from 'node:test'
import { kmlRecordKey, loadKmlRecords } from './kmlLoader.js'

const records = (count) => Array.from({ length: count }, (_, i) => ({ id: i + 1, created_at: 'v1' }))
const response = (ids) => ({ success: true, data: { items: ids.map((id) => ({ record_id: id, kml_text: `<kml>${id}</kml>` })) } })
const noSingle = async () => assert.fail('unexpected individual download')

test('cached KML is delivered without any network access, including after rename', async () => {
  const row = { ...records(1)[0], title: 'renamed' }
  const cache = new Map([[kmlRecordKey(row), 'cached']])
  const delivered = []
  await loadKmlRecords([row], {
    cache, fetchBatch: noSingle, fetchSingle: noSingle,
    onResult: (item) => delivered.push(item)
  })
  assert.equal(delivered[0].text, 'cached')
  assert.equal(delivered.length, 1)
})

test('uncached downloads use batches of at most four and at most two concurrent requests', async () => {
  let active = 0
  let peak = 0
  const batches = []
  const delivered = []
  await loadKmlRecords(records(13), {
    cache: new Map(), fetchSingle: noSingle,
    async fetchBatch(ids) {
      batches.push(ids)
      peak = Math.max(peak, ++active)
      await new Promise((resolve) => setTimeout(resolve, 5))
      active -= 1
      return response(ids)
    },
    onResult: (item) => delivered.push(item)
  })
  assert.equal(peak, 2)
  assert.ok(batches.every((ids) => ids.length <= 4))
  assert.equal(delivered.length, 13)
  assert.ok(delivered.every((item) => !item.error))
})

test('a completed batch renders before a slower batch finishes', async () => {
  let releaseSlow
  const slow = new Promise((resolve) => { releaseSlow = resolve })
  let firstDelivered
  const first = new Promise((resolve) => { firstDelivered = resolve })
  const delivered = []
  const loading = loadKmlRecords(records(8), {
    cache: new Map(), fetchSingle: noSingle,
    async fetchBatch(ids) {
      if (ids[0] === 1) await slow
      return response(ids)
    },
    onResult(item) {
      delivered.push(item.row.id)
      firstDelivered()
    }
  })
  await first
  assert.equal(delivered[0], 5)
  releaseSlow()
  await loading
  assert.equal(delivered.length, 8)
})

test('network batch failure does not cause an amplified round of single requests', async () => {
  const delivered = []
  await loadKmlRecords(records(4), {
    cache: new Map(), fetchSingle: noSingle,
    fetchBatch: async () => { throw Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }) },
    onResult: (item) => delivered.push(item)
  })
  assert.equal(delivered.length, 4)
  assert.ok(delivered.every((item) => item.error?.code === 'ECONNABORTED'))
})

test('partial failures remain explicit while successful records are cached', async () => {
  const cache = new Map()
  const delivered = []
  await loadKmlRecords(records(2), {
    cache, fetchSingle: noSingle,
    fetchBatch: async () => ({
      success: true,
      data: { items: response([1]).data.items, failed_items: [{ record_id: 2, message: 'invalid KML' }] }
    }),
    onResult: (item) => delivered.push(item)
  })
  assert.equal(delivered[1].error.message, 'invalid KML')
  assert.equal(cache.size, 1)
})

test('older servers without the batch endpoint fall back to single reads', async () => {
  const delivered = []
  await loadKmlRecords(records(2), {
    cache: new Map(),
    fetchBatch: async () => { throw { response: { status: 404 } } },
    fetchSingle: async (id) => ({ success: true, data: response([id]).data.items[0] }),
    onResult: (item) => delivered.push(item)
  })
  assert.ok(delivered.every((item) => !item.error))
  assert.equal(delivered.length, 2)
})

test('changing selection cancels pending work without writing old results or cache', async () => {
  const controller = new AbortController()
  const cache = new Map()
  const delivered = []
  await loadKmlRecords(records(8), {
    cache, signal: controller.signal, fetchSingle: noSingle,
    async fetchBatch(ids, { signal }) {
      assert.equal(signal, controller.signal)
      controller.abort()
      return response(ids)
    },
    onResult: (item) => delivered.push(item)
  })
  assert.equal(delivered.length, 0)
  assert.equal(cache.size, 0)
})

test('record revision changes invalidate its text cache', async () => {
  const old = { id: 1, updated_at: 'v1' }
  const row = { id: 1, updated_at: 'v2' }
  let calls = 0
  await loadKmlRecords([row], {
    cache: new Map([[kmlRecordKey(old), 'old']]), fetchSingle: noSingle,
    async fetchBatch(ids) { calls += 1; return response(ids) },
    onResult: (item) => assert.notEqual(item.text, 'old')
  })
  assert.equal(calls, 1)
})

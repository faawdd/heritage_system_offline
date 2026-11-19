import test from 'node:test'
import assert from 'node:assert/strict'
import { loadHeritageMapData } from './heritageMapLoader.js'

test('loads point pages before geometry pages and merges each boundary', async () => {
  const calls = []
  const events = []
  const pages = {
    'points:0': { success: true, rows: [{ id: 1 }, { id: 2 }], next_cursor: 2 },
    'points:2': { success: true, rows: [{ id: 3 }], next_cursor: null },
    'geometry:0': { success: true, rows: [{ id: 1, body_boundary: [[[1, 2]]] }], next_cursor: 1 },
    'geometry:1': { success: true, rows: [{ id: 3, control_zone: [[[3, 4]]] }], next_cursor: null }
  }
  const result = await loadHeritageMapData({
    geometry: 'geometry',
    fetchPage: async (view, cursor) => { calls.push(`${view}:${cursor}`); return pages[`${view}:${cursor}`] },
    onPoints: (rows) => events.push(['points', rows.length]),
    onGeometry: (rows) => events.push(['geometry', rows[0].id])
  })
  assert.deepEqual(calls, ['points:0', 'points:2', 'geometry:0', 'geometry:1'])
  assert.deepEqual(events, [['points', 3], ['geometry', 1], ['geometry', 3]])
  assert.deepEqual(result.rows[0].body_boundary, [[[1, 2]]])
  assert.deepEqual(result.rows[2].control_zone, [[[3, 4]]])
})

test('default fetches no geometry and legacy servers need only one request', async () => {
  let calls = 0
  const result = await loadHeritageMapData({
    geometry: 'body',
    fetchPage: async () => { calls++; return { success: true, rows: [{ id: 1, body_boundary: [1] }] } }
  })
  assert.equal(calls, 1)
  assert.deepEqual(result.rows[0].body_boundary, [1])
  calls = 0
  await loadHeritageMapData({
    fetchPage: async () => { calls++; return { success: true, rows: [], next_cursor: null } }
  })
  assert.equal(calls, 1)
})

test('partial geometry failure is surfaced after points are available', async () => {
  let points
  await assert.rejects(loadHeritageMapData({
    geometry: 'body',
    onPoints: (rows) => { points = rows },
    fetchPage: async (view) => {
      if (view === 'points') return { success: true, rows: [{ id: 1 }], next_cursor: null }
      throw new Error('network failure')
    }
  }), /network failure/)
  assert.deepEqual(points, [{ id: 1 }])
})

test('invalid cursors and cancellation stop further page requests', async () => {
  await assert.rejects(loadHeritageMapData({
    fetchPage: async () => ({ success: true, rows: [], next_cursor: 0 })
  }), /分页游标无效/)
  const controller = new AbortController()
  let calls = 0
  await assert.rejects(loadHeritageMapData({
    signal: controller.signal,
    fetchPage: async () => {
      calls++
      controller.abort()
      return { success: true, rows: [], next_cursor: 1 }
    }
  }), { name: 'AbortError' })
  assert.equal(calls, 1)
})

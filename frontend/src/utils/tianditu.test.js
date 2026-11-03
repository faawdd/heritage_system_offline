import assert from 'node:assert/strict'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

test('offline basemap behavior is preserved alongside online tile retries', async (t) => {
  const server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL('../../', import.meta.url)),
    server: { middlewareMode: true, hmr: false, ws: false }
  })
  t.after(() => server.close())
  const savedStorage = globalThis.localStorage
  const savedWindow = globalThis.window
  const storage = new Map()
  const events = new EventTarget()
  globalThis.localStorage = {
    getItem: (key) => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, value)
  }
  t.after(() => {
    globalThis.localStorage = savedStorage
    globalThis.window = savedWindow
  })
  const api = await server.ssrLoadModule('/src/utils/tianditu.js')
  globalThis.window = events
  const online = { img: api.createTiandituLayerGroup('img'), vec: api.createTiandituLayerGroup('vec') }
  const offline = api.createOfflineTileLayer()
  assert.equal(api.getBasemapProvider(), 'online')
  assert.equal(api.setBasemapProvider('offline'), false)
  assert.equal(offline.getSource(), null)
  assert.equal(offline.getVisible(), false)

  storage.set('heritage_offline_tile_set', 'local-test-set')
  assert.equal(api.getBasemapProvider(), 'offline')
  api.refreshBasemapLayers(online, offline)
  assert.equal(offline.getVisible(), true)
  assert.ok(offline.getSource().getUrls()[0].startsWith('/api/v1/gis/offline-tiles/local-test-set/'))
  assert.ok(Object.values(online).flat().every((layer) => !layer.getVisible()))

  let changes = 0
  const stop = api.watchBasemapChanges(() => { changes += 1 })
  assert.equal(api.setBasemapProvider('online'), true)
  assert.equal(changes, 1)
  api.refreshBasemapLayers(online, offline, 'vec')
  assert.equal(offline.getVisible(), false)
  assert.ok(online.vec.every((layer) => layer.getVisible()))
  assert.ok(online.img.every((layer) => !layer.getVisible()))
  assert.ok(online.vec[0].getSource().getUrls()[0].startsWith('https://'))
  assert.notEqual(online.vec[0].getSource().getTileLoadFunction(), offline.getSource().getTileLoadFunction())

  stop()
  events.dispatchEvent(new Event('heritage-offline-basemap-changed'))
  assert.equal(changes, 1)
  storage.delete('heritage_offline_tile_set')
  api.refreshBasemapLayers(online, offline)
  assert.equal(offline.getSource(), null)
  assert.equal(offline.getVisible(), false)
})

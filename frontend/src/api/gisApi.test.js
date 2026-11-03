import assert from 'node:assert/strict'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

test('GIS API request configuration and blob responses', async (t) => {
  const server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL('../../', import.meta.url)),
    server: { middlewareMode: true, hmr: false, ws: false }
  })
  t.after(() => server.close())
  const previousStorage = globalThis.localStorage
  globalThis.localStorage = { getItem: () => '' }
  t.after(() => { globalThis.localStorage = previousStorage })
  const { default: client } = await server.ssrLoadModule('/src/api/client.js')
  const api = await server.ssrLoadModule('/src/api/gisApi.js')
  const originalAdapter = client.defaults.adapter
  t.after(() => { client.defaults.adapter = originalAdapter })

  await t.test('upload has ten minute timeout, forwards progress and preserves JSON results', async () => {
    const progress = () => {}
    client.defaults.adapter = async (config) => {
      assert.equal(config.timeout, 600000)
      assert.equal(config.responseType, 'blob')
      assert.equal(config.onUploadProgress, progress)
      return {
        status: 200, config, headers: { 'content-type': 'application/json' },
        data: new Blob([JSON.stringify({ success: true, data: { created_count: 1 } })])
      }
    }
    const form = new FormData()
    form.set('action', 'upload')
    const result = await api.submitGisKmlManagementAction(form, { onUploadProgress: progress })
    assert.equal(result.data.created_count, 1)
  })

  await t.test('upload network failures are surfaced without automatic replay', async () => {
    let calls = 0
    client.defaults.adapter = async () => {
      calls += 1
      throw Object.assign(new Error('network failed'), { code: 'ERR_NETWORK' })
    }
    await assert.rejects(api.submitGisKmlManagementAction(new FormData()), { code: 'ERR_NETWORK' })
    assert.equal(calls, 1)
  })

  await t.test('JSON error blobs preserve the server validation message', async () => {
    client.defaults.adapter = async (config) => {
      throw Object.assign(new Error('HTTP 400'), {
        config,
        response: {
          status: 400, headers: { 'content-type': 'application/json' },
          data: new Blob([JSON.stringify({ message: 'Invalid KML file' })])
        }
      })
    }
    await assert.rejects(api.submitGisKmlManagementAction(new FormData()), { message: 'Invalid KML file' })
  })

  await t.test('exports preserve the file blob and UTF-8 filename', async () => {
    const blob = new Blob(['export content'])
    client.defaults.adapter = async (config) => ({
      status: 200, config, data: blob,
      headers: { 'content-type': 'text/csv', 'content-disposition': "attachment; filename*=UTF-8''report%20one.csv" }
    })
    const result = await api.submitGisKmlManagementAction(new FormData())
    assert.equal(result.download.blob, blob)
    assert.equal(result.download.filename, 'report one.csv')
  })

  await t.test('batch reads use sixty second timeout and forward cancellation', async () => {
    const controller = new AbortController()
    client.defaults.adapter = async (config) => {
      assert.equal(config.timeout, 60000)
      assert.equal(config.signal, controller.signal)
      return { status: 200, config, headers: {}, data: { success: true, data: { items: [] } } }
    }
    assert.equal((await api.fetchGisKmlBatchKmlContent([1], { signal: controller.signal })).success, true)
  })
})

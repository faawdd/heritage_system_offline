import assert from 'node:assert/strict'
import test from 'node:test'
import TileState from 'ol/TileState.js'
import { createRetryingTileLoader } from './tileLoader.js'

function fixture(t) {
  const images = []
  const previous = globalThis.Image
  globalThis.Image = class {
    constructor() { images.push(this) }
  }
  t.after(() => { globalThis.Image = previous })
  const listeners = new Set()
  let state = TileState.LOADING
  const tile = {
    getImage: () => ({ crossOrigin: 'anonymous', referrerPolicy: '' }),
    getState: () => state,
    addEventListener: (_, callback) => listeners.add(callback),
    removeEventListener: (_, callback) => listeners.delete(callback),
    setState(value) {
      state = value
      for (const callback of listeners) callback()
    },
    setImage(image) { tile.image = image; tile.setState(TileState.LOADED) }
  }
  t.after(() => tile.setState(TileState.EMPTY))
  return { tile, images, listeners }
}

test('failed tile loads recover on a bounded retry', async (t) => {
  const { tile, images, listeners } = fixture(t)
  createRetryingTileLoader({ retryDelay: 0 })(tile, 'tile-url')
  assert.equal(images[0].crossOrigin, 'anonymous')
  images[0].onerror()
  await new Promise((resolve) => setTimeout(resolve, 5))
  images[1].onload()
  assert.equal(tile.getState(), TileState.LOADED)
  assert.equal(tile.image, images[1])
  assert.equal(listeners.size, 0)
})

test('hanging tiles time out after three attempts instead of blocking forever', async (t) => {
  const { tile, images, listeners } = fixture(t)
  const done = new Promise((resolve) => {
    const original = tile.setState
    tile.setState = (state) => {
      original(state)
      if (state === TileState.ERROR) resolve()
    }
  })
  createRetryingTileLoader({ timeout: 2, retryDelay: 0 })(tile, 'tile-url')
  await done
  assert.equal(images.length, 3)
  assert.equal(tile.getState(), TileState.ERROR)
  assert.equal(listeners.size, 0)
})

test('evicted tiles cancel pending retries', async (t) => {
  const { tile, images } = fixture(t)
  createRetryingTileLoader({ retryDelay: 2 })(tile, 'tile-url')
  images[0].onerror()
  tile.setState(TileState.EMPTY)
  await new Promise((resolve) => setTimeout(resolve, 10))
  assert.equal(images.length, 1)
  assert.equal(images[0].onerror, null)
})

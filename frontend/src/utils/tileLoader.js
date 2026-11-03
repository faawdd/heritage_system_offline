import TileState from 'ol/TileState.js'

export function createRetryingTileLoader({ timeout = 20000, retries = 2, retryDelay = 1000 } = {}) {
  return (tile, src) => {
    let image
    let timer
    let attempt = 0
    let stopped = false
    const cleanupImage = () => {
      clearTimeout(timer)
      if (image) {
        image.onload = null
        image.onerror = null
        image.src = ''
      }
    }
    const stop = () => {
      stopped = true
      cleanupImage()
      tile.removeEventListener('change', onChange)
    }
    const onChange = () => {
      if (tile.getState() === TileState.EMPTY) stop()
    }
    const load = () => {
      if (stopped) return
      image = new Image()
      image.crossOrigin = tile.getImage().crossOrigin
      image.referrerPolicy = tile.getImage().referrerPolicy
      image.onload = () => {
        clearTimeout(timer)
        image.onload = null
        image.onerror = null
        stopped = true
        tile.removeEventListener('change', onChange)
        tile.setImage(image)
      }
      const fail = () => {
        cleanupImage()
        if (attempt >= retries) {
          stop()
          tile.setState(TileState.ERROR)
          return
        }
        timer = setTimeout(load, retryDelay * 2 ** attempt)
        attempt += 1
      }
      image.onerror = fail
      timer = setTimeout(fail, timeout)
      image.src = src
    }
    tile.addEventListener('change', onChange)
    load()
  }
}

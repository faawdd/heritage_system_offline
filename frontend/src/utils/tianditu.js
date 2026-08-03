import TileLayer from 'ol/layer/Tile'
import XYZ from 'ol/source/XYZ'

const DEFAULT_TDT_TK = '424ac2af85564078477428c1a2b72018'
const OFFLINE_TILE_ROOT = '/static/tiles/tianditu'

function buildUrls(layerType, tk) {
  const urls = []
  for (let i = 0; i <= 7; i += 1) {
    urls.push(
      `https://t${i}.tianditu.gov.cn/${layerType}_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=${layerType}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${tk}`
    )
  }
  return urls
}

function resolveToken() {
  return import.meta.env.VITE_TDT_TK || DEFAULT_TDT_TK
}

function isElectronRuntime() {
  return typeof window !== 'undefined' && window?.desktopMeta?.runtime === 'electron'
}

function createOnlineSource(layerType, tk) {
  return new XYZ({
    urls: buildUrls(layerType, tk),
    crossOrigin: 'anonymous',
  })
}

function createOfflineSource(layerType) {
  return new XYZ({
    url: `${OFFLINE_TILE_ROOT}/${layerType}/{z}/{x}/{y}.png`,
    crossOrigin: 'anonymous',
    maxZoom: Number(import.meta.env.VITE_OFFLINE_TILE_MAX_ZOOM || 13),
  })
}

function createSource(layerType, tk) {
  return isElectronRuntime() ? createOfflineSource(layerType) : createOnlineSource(layerType, tk)
}

export function createTiandituLayerGroup(mode = 'img') {
  const tk = resolveToken()
  if (mode === 'vec') {
    return [
      new TileLayer({ source: createSource('vec', tk) }),
      new TileLayer({ source: createSource('cva', tk) })
    ]
  }
  if (mode === 'ter') {
    return [
      new TileLayer({ source: createSource('ter', tk) }),
      new TileLayer({ source: createSource('cta', tk) })
    ]
  }
  return [
    new TileLayer({ source: createSource('img', tk) }),
    new TileLayer({ source: createSource('cia', tk) })
  ]
}

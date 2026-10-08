import TileLayer from 'ol/layer/Tile'
import XYZ from 'ol/source/XYZ'

const DEFAULT_TDT_TK = '424ac2af85564078477428c1a2b72018'
const ACTIVE_TILE_SET_KEY = 'heritage_offline_tile_set'
const BASEMAP_PROVIDER_KEY = 'heritage_basemap_provider'
const ACCESS_TOKEN_KEY = 'heritage_access_token'

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

export function createTiandituLayerGroup(mode = 'img') {
  const tk = resolveToken()
  if (mode === 'vec') {
    return [
      new TileLayer({ source: new XYZ({ urls: buildUrls('vec', tk), crossOrigin: 'anonymous' }) }),
      new TileLayer({ source: new XYZ({ urls: buildUrls('cva', tk), crossOrigin: 'anonymous' }) })
    ]
  }
  if (mode === 'ter') {
    return [
      new TileLayer({ source: new XYZ({ urls: buildUrls('ter', tk), crossOrigin: 'anonymous' }) }),
      new TileLayer({ source: new XYZ({ urls: buildUrls('cta', tk), crossOrigin: 'anonymous' }) })
    ]
  }
  return [
    new TileLayer({ source: new XYZ({ urls: buildUrls('img', tk), crossOrigin: 'anonymous' }) }),
    new TileLayer({ source: new XYZ({ urls: buildUrls('cia', tk), crossOrigin: 'anonymous' }) })
  ]
}

export function getActiveOfflineTileSetId() {
  return localStorage.getItem(ACTIVE_TILE_SET_KEY) || ''
}

export function getBasemapProvider() {
  const activeTileSetId = getActiveOfflineTileSetId()
  const savedProvider = localStorage.getItem(BASEMAP_PROVIDER_KEY)
  if (savedProvider === 'offline' && activeTileSetId) return 'offline'
  if (savedProvider === 'online') return 'online'
  return activeTileSetId ? 'offline' : 'online'
}

export function setBasemapProvider(provider) {
  if (!['online', 'offline'].includes(provider)) return false
  if (provider === 'offline' && !getActiveOfflineTileSetId()) return false
  localStorage.setItem(BASEMAP_PROVIDER_KEY, provider)
  window.dispatchEvent(new CustomEvent('heritage-basemap-provider-changed'))
  return true
}

export function createOfflineTileLayer() {
  return new TileLayer({ source: null, visible: false })
}

export function refreshBasemapLayers(onlineGroups, offlineLayer, onlineMode = 'img') {
  const tileSetId = getActiveOfflineTileSetId()
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY) || ''
  const provider = getBasemapProvider()

  if (tileSetId) {
    offlineLayer.setSource(new XYZ({
      url: `/api/v1/gis/offline-tiles/${tileSetId}/{z}/{x}/{y}/?access_token=${encodeURIComponent(accessToken)}`,
      crossOrigin: 'anonymous',
      maxZoom: 30
    }))
  } else {
    offlineLayer.setSource(null)
  }
  offlineLayer.setVisible(provider === 'offline' && Boolean(tileSetId))

  Object.entries(onlineGroups).forEach(([mode, layers]) => {
    layers.forEach((layer) => layer.setVisible(provider === 'online' && mode === onlineMode))
  })
}

export function watchBasemapChanges(handler) {
  window.addEventListener('heritage-basemap-provider-changed', handler)
  window.addEventListener('heritage-offline-basemap-changed', handler)
  return () => {
    window.removeEventListener('heritage-basemap-provider-changed', handler)
    window.removeEventListener('heritage-offline-basemap-changed', handler)
  }
}

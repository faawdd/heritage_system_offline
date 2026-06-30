import TileLayer from 'ol/layer/Tile'
import XYZ from 'ol/source/XYZ'

const DEFAULT_TDT_TK = '424ac2af85564078477428c1a2b72018'

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

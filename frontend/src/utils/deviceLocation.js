// 设备定位工具：解析移动端 App 通过入口地址传入的 app_loc_* 参数，并封装浏览器实时定位。
// 坐标均为 WGS84（与天地图 CGCS2000 底图可直接叠加，无需纠偏）。

function firstValue(value) {
  return Array.isArray(value) ? value[0] : value
}

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

export function isValidLonLat(lon, lat) {
  return Number.isFinite(lon) && Number.isFinite(lat) && Math.abs(lon) <= 180 && Math.abs(lat) <= 90 && !(lon === 0 && lat === 0)
}

export function parseAppLocation(query = {}) {
  const lon = toFiniteNumber(firstValue(query.app_loc_lon))
  const lat = toFiniteNumber(firstValue(query.app_loc_lat))
  if (!isValidLonLat(lon, lat)) {
    return null
  }
  const accuracy = toFiniteNumber(firstValue(query.app_loc_accuracy))
  const ts = toFiniteNumber(firstValue(query.app_loc_ts))
  return {
    longitude: lon,
    latitude: lat,
    altitude: toFiniteNumber(firstValue(query.app_loc_alt)),
    accuracy: accuracy !== null && accuracy >= 0 ? accuracy : null,
    timestamp: ts !== null && ts > 0 ? ts : Date.now(),
    source: 'app'
  }
}

export function fromGeolocationPosition(position) {
  const coords = position?.coords || {}
  const lon = toFiniteNumber(coords.longitude)
  const lat = toFiniteNumber(coords.latitude)
  if (!isValidLonLat(lon, lat)) {
    return null
  }
  const accuracy = toFiniteNumber(coords.accuracy)
  return {
    longitude: lon,
    latitude: lat,
    altitude: toFiniteNumber(coords.altitude),
    accuracy: accuracy !== null && accuracy >= 0 ? accuracy : null,
    timestamp: toFiniteNumber(position?.timestamp) || Date.now(),
    source: 'live'
  }
}

export function isGeolocationSupported() {
  return typeof navigator !== 'undefined' && Boolean(navigator.geolocation) && (typeof window === 'undefined' || window.isSecureContext !== false)
}

export function geolocationErrorMessage(error) {
  if (!isGeolocationSupported()) {
    return '当前浏览器环境不支持实时定位'
  }
  switch (error?.code) {
    case 1:
      return '未获得定位权限，请在系统设置中允许定位'
    case 2:
      return '暂时无法获取位置，请到开阔处重试'
    case 3:
      return '定位超时，请稍后重试'
    default:
      return '定位失败，请稍后重试'
  }
}

export function formatLocationCoords(location) {
  if (!location) {
    return ''
  }
  return `${location.longitude.toFixed(6)}, ${location.latitude.toFixed(6)}`
}

export function formatLocationAccuracy(location) {
  if (!location || location.accuracy === null || location.accuracy === undefined) {
    return '精度未知'
  }
  return `±${Math.round(location.accuracy)} 米`
}

export function formatLocationTime(timestamp) {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

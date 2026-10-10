import { boundingExtent } from 'ol/extent.js'
import { fromLonLat, transformExtent } from 'ol/proj.js'

export const NATIONAL_BOUNDS = [73, 18, 135, 54]

export function validLonLat(longitude, latitude) {
  if (![longitude, latitude].every((value) =>
    (typeof value === 'number' || typeof value === 'string') && String(value).trim() !== ''
  )) return false
  const lon = Number(longitude)
  const lat = Number(latitude)
  return Number.isFinite(lon) && Number.isFinite(lat)
    && lon >= -180 && lon <= 180 && lat > -85 && lat < 85
    && !(lon === 0 && lat === 0)
}

export function nationalViewOptions() {
  return { center: fromLonLat([104, 36]), zoom: 4 }
}

export function pointsExtent(points) {
  const coordinates = points
    .filter((point) => validLonLat(point.lng ?? point.longitude, point.lat ?? point.latitude))
    .map((point) => fromLonLat([
      Number(point.lng ?? point.longitude), Number(point.lat ?? point.latitude)
    ]))
  return coordinates.length ? boundingExtent(coordinates) : null
}

export function fitMapExtent(map, extent, options = {}) {
  if (!map) return
  const validExtent = Array.isArray(extent) && extent.length === 4
    && extent.every(Number.isFinite) && extent[0] <= extent[2] && extent[1] <= extent[3]
  map.updateSize()
  map.getView().fit(
    validExtent ? extent : transformExtent(NATIONAL_BOUNDS, 'EPSG:4326', 'EPSG:3857'),
    { padding: [32, 32, 32, 32], maxZoom: validExtent ? 14 : 5, ...options }
  )
}

export function fitHeritagePoints(map, points) {
  fitMapExtent(map, pointsExtent(points))
}

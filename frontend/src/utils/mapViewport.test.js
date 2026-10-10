import assert from 'node:assert/strict'
import test from 'node:test'
import View from 'ol/View.js'
import { fromLonLat, transformExtent } from 'ol/proj.js'
import { NATIONAL_BOUNDS, fitHeritagePoints, pointsExtent, validLonLat } from './mapViewport.js'

function testMap() {
  const view = new View()
  const fit = view.fit.bind(view)
  view.fit = (extent, options) => fit(extent, { ...options, size: [800, 600] })
  return { updateSize() {}, getView: () => view }
}

test('invalid and absent coordinates cannot move the map to zero or infinity', () => {
  for (const point of [[null, null], ['', ''], [' ', 30], [true, 30], [[], 30], [0, 0], [NaN, 35], [181, 35], [110, 90]]) {
    assert.equal(validLonLat(...point), false)
  }
  assert.equal(validLonLat('116.4', '39.9'), true)
  assert.equal(pointsExtent([{ lng: 0, lat: 0 }]), null)
})

test('all regional points are included in the projected extent', () => {
  for (const points of [
    [{ lng: 87.5, lat: 44.3 }, { lng: 88.5, lat: 45.3 }],
    [{ longitude: 120, latitude: 30 }, { longitude: 121, latitude: 31 }]
  ]) {
    const extent = pointsExtent(points)
    const first = fromLonLat([points[0].lng ?? points[0].longitude, points[0].lat ?? points[0].latitude])
    const last = fromLonLat([points[1].lng ?? points[1].longitude, points[1].lat ?? points[1].latitude])
    assert.deepEqual(extent, [first[0], first[1], last[0], last[1]])
  }
})

test('empty and invalid data fits the national region', () => {
  for (const points of [[], [{ lng: 0, lat: 0 }]]) {
    const map = testMap()
    fitHeritagePoints(map, points)
    const visible = map.getView().calculateExtent([800, 600])
    const expected = transformExtent(NATIONAL_BOUNDS, 'EPSG:4326', 'EPSG:3857')
    assert.ok(visible[0] <= expected[0] && visible[2] >= expected[2])
    assert.ok(visible[1] <= expected[1] && visible[3] >= expected[3])
  }
})

test('single point is centered and zoom is capped', () => {
  const map = testMap()
  fitHeritagePoints(map, [{ lng: 116.4, lat: 39.9 }])
  assert.deepEqual(map.getView().getCenter(), fromLonLat([116.4, 39.9]))
  assert.equal(map.getView().getZoom(), 14)
})

test('updated data replaces the earlier national or regional center', () => {
  const map = testMap()
  fitHeritagePoints(map, [])
  fitHeritagePoints(map, [{ lng: 121, lat: 31 }])
  assert.deepEqual(map.getView().getCenter(), fromLonLat([121, 31]))
  fitHeritagePoints(map, [])
  assert.notDeepEqual(map.getView().getCenter(), fromLonLat([121, 31]))
})

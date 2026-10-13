<template>
  <div ref="mapEl" class="heritage-map-canvas">
    <BaseMapSwitcher />
    <div
      v-if="enableMapTools"
      class="heritage-map-tools"
      @pointerdown.stop
      @click.stop
      @dblclick.stop
    >
      <div class="heritage-measure-actions">
        <button
          type="button"
          :class="{ active: measureMode === 'distance' }"
          @click="toggleMeasureMode('distance')"
        >{{ measureMode === 'distance' ? '结束测距' : '测距' }}</button>
        <button
          type="button"
          :class="{ active: measureMode === 'area' }"
          @click="toggleMeasureMode('area')"
        >{{ measureMode === 'area' ? '结束面积测量' : '面积/周长' }}</button>
        <button type="button" class="clear-measure" :disabled="!measureText && !measurePoints.length" @click="clearMeasure">清除</button>
      </div>
      <p v-if="measureText" class="heritage-measure-text" aria-live="polite">{{ measureText }}</p>
    </div>
    <div v-if="showPointPopup" ref="pointPopupEl" class="heritage-point-popup">
      <button type="button" class="heritage-point-popup-close" aria-label="关闭" @click="closePointPopup">×</button>
      <div class="heritage-point-popup-title">{{ pointPopup.name || '未命名文物' }}</div>
      <div class="heritage-point-popup-level">{{ pointPopup.level_label || '未定级' }}</div>
      <dl>
        <div>
          <dt>经纬度</dt>
          <dd>{{ pointPopup.lng ?? '-' }}, {{ pointPopup.lat ?? '-' }}</dd>
        </div>
      </dl>
      <button type="button" class="heritage-point-popup-action" @click="emitOpenDetail">查看档案详情</button>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Feature from 'ol/Feature'
import Map from 'ol/Map'
import View from 'ol/View'
import Point from 'ol/geom/Point'
import HeatmapLayer from 'ol/layer/Heatmap'
import VectorLayer from 'ol/layer/Vector'
import LineString from 'ol/geom/LineString'
import Polygon from 'ol/geom/Polygon'
import { fromLonLat } from 'ol/proj'
import VectorSource from 'ol/source/Vector'
import { getArea, getLength } from 'ol/sphere'
import CircleStyle from 'ol/style/Circle'
import Fill from 'ol/style/Fill'
import Stroke from 'ol/style/Stroke'
import Style from 'ol/style/Style'
import Overlay from 'ol/Overlay'

import BaseMapSwitcher from '../maps/BaseMapSwitcher.vue'
import { fitHeritagePoints, nationalViewOptions, validLonLat } from '../../utils/mapViewport'
import {
  createOfflineTileLayer,
  createTiandituLayerGroup,
  refreshBasemapLayers,
  watchBasemapChanges
} from '../../utils/tianditu'

const props = defineProps({
  points: {
    type: Array,
    default: () => []
  },
  activeLevels: {
    type: Array,
    default: () => []
  },
  keyword: {
    type: String,
    default: ''
  },
  abnormalPoints: {
    type: Array,
    default: () => []
  },
  showAbnormalHeat: {
    type: Boolean,
    default: true
  },
  showPointPopup: {
    type: Boolean,
    default: false
  },
  enableMapTools: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['select', 'open-detail'])

const mapEl = ref(null)
const mapRef = ref(null)
const vectorSource = new VectorSource()
const boundarySource = new VectorSource()
const abnormalSource = new VectorSource()
const abnormalHeatSource = new VectorSource()
const measureSource = new VectorSource()
const abnormalLayerRef = ref(null)
const abnormalHeatLayerRef = ref(null)
const vectorLayerRef = ref(null)
const boundaryLayerRef = ref(null)
const pointPopupEl = ref(null)
const pointPopupOverlayRef = ref(null)
const pointPopup = ref({})
const measureMode = ref('')
const measureText = ref('')
let measurePoints = []
let mapResizeObserver = null
let mapResizeFrame = 0
let onlineBaseLayers = []
let offlineBaseLayer = null
let stopWatchingBasemap = null

const BOUNDARY_ZOOM_THRESHOLD = 16

const levelColors = {
  GB: '#e63946',
  SB: '#f4a261',
  XB: '#2a9d8f',
  DS: '#457b9d'
}

const markerStyle = (level) =>
  new Style({
    image: new CircleStyle({
      radius: 6,
      fill: new Fill({ color: levelColors[level] || '#666666' }),
      stroke: new Stroke({ color: '#ffffff', width: 2 })
    })
  })

const boundaryStyle = new Style({
  stroke: new Stroke({ color: '#2563eb', width: 2 }),
  fill: new Fill({ color: 'rgba(37, 99, 235, 0.16)' })
})

const measurePointStyle = new Style({
  image: new CircleStyle({
    radius: 5,
    fill: new Fill({ color: '#16a34a' }),
    stroke: new Stroke({ color: '#ffffff', width: 2 })
  })
})

const measureLineStyle = new Style({
  stroke: new Stroke({ color: '#22c55e', width: 2, lineDash: [8, 6] })
})

const measurePolygonStyle = new Style({
  stroke: new Stroke({ color: '#16a34a', width: 2, lineDash: [8, 6] }),
  fill: new Fill({ color: 'rgba(34, 197, 94, 0.12)' })
})

const abnormalStyle =
  new Style({
    image: new CircleStyle({
      radius: 7,
      fill: new Fill({ color: 'rgba(255, 23, 68, 0.95)' }),
      stroke: new Stroke({ color: '#ffffff', width: 2.4 })
    })
  })

function applyPoints() {
  vectorSource.clear()
  boundarySource.clear()

  const keyword = (props.keyword || '').trim()
  const rows = (props.points || []).filter((item) => {
    const levelOk = (props.activeLevels || []).includes(item.level)
    const keywordOk = !keyword || String(item.name || '').includes(keyword)
    return levelOk && keywordOk
  })

  rows.forEach((item) => {
    const longitude = item.lng ?? item.longitude
    const latitude = item.lat ?? item.latitude
    if (!validLonLat(longitude, latitude)) return
    const feature = new Feature({
      geometry: new Point(fromLonLat([Number(longitude), Number(latitude)])),
      payload: item
    })
    feature.setStyle(markerStyle(item.level))
    vectorSource.addFeature(feature)

    const rings = Array.isArray(item.body_boundary) ? item.body_boundary : []
    rings.forEach((ring) => {
      const coordinates = (Array.isArray(ring) ? ring : [])
        .filter((point) => Array.isArray(point) && validLonLat(point[0], point[1]))
        .map((point) => fromLonLat([Number(point[0]), Number(point[1])]))
      if (coordinates.length < 3) return
      const first = coordinates[0]
      const last = coordinates[coordinates.length - 1]
      if (first[0] !== last[0] || first[1] !== last[1]) {
        coordinates.push(first.slice())
      }
      const boundary = new Feature({
        geometry: new Polygon([coordinates]),
        payload: item
      })
      boundary.setStyle(boundaryStyle)
      boundarySource.addFeature(boundary)
    })
  })
  updateBoundaryZoomVisibility()
  fitHeritagePoints(mapRef.value, props.points || [])
}

function updateBoundaryZoomVisibility() {
  const zoom = mapRef.value?.getView()?.getZoom()
  const showBoundary = props.enableMapTools && Number.isFinite(zoom) && zoom >= BOUNDARY_ZOOM_THRESHOLD
  boundaryLayerRef.value?.setVisible(showBoundary)
  vectorLayerRef.value?.setVisible(!showBoundary)
}

function applyAbnormalPoints() {
  abnormalSource.clear()
  abnormalHeatSource.clear()

  ;(props.abnormalPoints || []).forEach((item) => {
    const lon = Number(item?.longitude)
    const lat = Number(item?.latitude)
    if (!validLonLat(item?.longitude, item?.latitude)) {
      return
    }
    const coordinate = fromLonLat([lon, lat])
    const pointFeature = new Feature({
      geometry: new Point(coordinate),
      payload: item,
      is_abnormal: true
    })
    pointFeature.setStyle(abnormalStyle)
    abnormalSource.addFeature(pointFeature)

    const heatFeature = new Feature({ geometry: new Point(coordinate) })
    heatFeature.set('weight', 0.85)
    abnormalHeatSource.addFeature(heatFeature)
  })

  if (abnormalHeatLayerRef.value) {
    abnormalHeatLayerRef.value.setVisible(Boolean(props.showAbnormalHeat))
  }
}

onMounted(() => {
  onlineBaseLayers = createTiandituLayerGroup('img')
  offlineBaseLayer = createOfflineTileLayer()
  const vectorLayer = new VectorLayer({ source: vectorSource })
  const boundaryLayer = new VectorLayer({ source: boundarySource })
  const abnormalLayer = new VectorLayer({ source: abnormalSource })
  const measureLayer = new VectorLayer({ source: measureSource })
  const abnormalHeatLayer = new HeatmapLayer({
    source: abnormalHeatSource,
    blur: 20,
    radius: 14,
    weight: (feature) => Number(feature.get('weight') || 0.6),
    visible: Boolean(props.showAbnormalHeat)
  })

  const map = new Map({
    target: mapEl.value,
    layers: [
      ...onlineBaseLayers,
      offlineBaseLayer,
      abnormalHeatLayer,
      boundaryLayer,
      vectorLayer,
      abnormalLayer,
      measureLayer
    ],
    view: new View(nationalViewOptions())
  })

  map.on('click', (evt) => {
    if (measureMode.value) {
      closePointPopup()
      handleMeasureClick(evt.coordinate)
      return
    }
    const feature = map.forEachFeatureAtPixel(evt.pixel, (targetFeature) =>
      targetFeature.get('payload') ? targetFeature : undefined
    )
    if (!feature) {
      closePointPopup()
      return
    }
    const payload = feature.get('payload')
    if (payload?.id) {
      emit('select', payload)
      if (props.showPointPopup) {
        pointPopup.value = payload
        pointPopupOverlayRef.value?.setPosition(evt.coordinate)
      }
    }
  })

  map.on('dblclick', (evt) => {
    if (!measureMode.value) return
    evt.preventDefault()
    finishMeasure()
  })

  mapRef.value = map
  vectorLayerRef.value = vectorLayer
  boundaryLayerRef.value = boundaryLayer
  const refreshBasemap = () => refreshBasemapLayers({ img: onlineBaseLayers }, offlineBaseLayer, 'img')
  refreshBasemap()
  stopWatchingBasemap = watchBasemapChanges(refreshBasemap)
  abnormalLayerRef.value = abnormalLayer
  abnormalHeatLayerRef.value = abnormalHeatLayer
  if (props.showPointPopup && pointPopupEl.value) {
    const pointPopupOverlay = new Overlay({
      element: pointPopupEl.value,
      autoPan: { animation: { duration: 180 } },
      positioning: 'bottom-center',
      offset: [0, -12],
      stopEvent: true
    })
    map.addOverlay(pointPopupOverlay)
    pointPopupOverlayRef.value = pointPopupOverlay
  }
  applyPoints()
  applyAbnormalPoints()

  if (typeof ResizeObserver !== 'undefined' && mapEl.value) {
    mapResizeObserver = new ResizeObserver(() => {
      cancelAnimationFrame(mapResizeFrame)
      mapResizeFrame = requestAnimationFrame(() => fitHeritagePoints(map, props.points || []))
    })
    mapResizeObserver.observe(mapEl.value)
  }
  map.getView().on('change:resolution', updateBoundaryZoomVisibility)
  requestAnimationFrame(() => fitHeritagePoints(map, props.points || []))
})

onBeforeUnmount(() => {
  stopWatchingBasemap?.()
  mapResizeObserver?.disconnect()
  cancelAnimationFrame(mapResizeFrame)
  mapRef.value?.setTarget(undefined)
})

function closePointPopup() {
  pointPopup.value = {}
  pointPopupOverlayRef.value?.setPosition(undefined)
}

function toggleMeasureMode(mode) {
  if (measureMode.value === mode) {
    finishMeasure()
    return
  }
  measurePoints = []
  measureSource.clear()
  measureMode.value = mode
  measureText.value = mode === 'distance'
    ? '测距已开启：单击添加节点，双击或点击“结束测距”完成'
    : '面积/周长测量已开启：单击添加至少 3 个节点，双击或点击“结束面积测量”完成'
}

function clearMeasure() {
  measureMode.value = ''
  measurePoints = []
  measureSource.clear()
  measureText.value = ''
}

function handleMeasureClick(coordinate) {
  measurePoints.push(coordinate.slice())
  measureSource.clear()
  measurePoints.forEach((point) => {
    const feature = new Feature({ geometry: new Point(point) })
    feature.setStyle(measurePointStyle)
    measureSource.addFeature(feature)
  })

  if (measureMode.value === 'distance') {
    if (measurePoints.length < 2) {
      measureText.value = '已设置起点，点击地图继续测距'
      return
    }
    const line = new LineString(measurePoints)
    const total = getLength(line, { projection: 'EPSG:3857' })
    const segment = getLength(new LineString(measurePoints.slice(-2)), { projection: 'EPSG:3857' })
    const lineFeature = new Feature({ geometry: line })
    lineFeature.setStyle(measureLineStyle)
    measureSource.addFeature(lineFeature)
    measureText.value = `总距离：${formatDistance(total)}；本段：${formatDistance(segment)}（双击结束）`
    return
  }

  if (measurePoints.length < 2) {
    measureText.value = '已设置起点，继续添加节点以测量面积和周长'
    return
  }
  if (measurePoints.length < 3) {
    const lineFeature = new Feature({ geometry: new LineString(measurePoints) })
    lineFeature.setStyle(measureLineStyle)
    measureSource.addFeature(lineFeature)
    measureText.value = '至少需要 3 个点才能形成测量面'
    return
  }

  const ring = [...measurePoints, measurePoints[0].slice()]
  const polygon = new Polygon([ring])
  const polygonFeature = new Feature({ geometry: polygon })
  polygonFeature.setStyle(measurePolygonStyle)
  measureSource.addFeature(polygonFeature)
  measureText.value = `面积：${formatArea(getArea(polygon, { projection: 'EPSG:3857' }))}；周长：${formatDistance(getLength(polygon, { projection: 'EPSG:3857' }))}（双击结束）`
}

function finishMeasure() {
  const mode = measureMode.value
  const minimumPoints = mode === 'area' ? 3 : 2
  if (measurePoints.length < minimumPoints) {
    measureText.value = `至少需要 ${minimumPoints} 个点才能完成${mode === 'area' ? '面积测量' : '测距'}`
    return
  }
  measureMode.value = ''
  if (mode === 'distance') {
    const distance = getLength(new LineString(measurePoints), { projection: 'EPSG:3857' })
    measureText.value = `总距离：${formatDistance(distance)}（已结束）`
    return
  }
  const polygon = new Polygon([[...measurePoints, measurePoints[0].slice()]])
  measureText.value = `面积：${formatArea(getArea(polygon, { projection: 'EPSG:3857' }))}；周长：${formatDistance(getLength(polygon, { projection: 'EPSG:3857' }))}（已结束）`
}

function formatDistance(distance) {
  if (!Number.isFinite(distance)) return '-'
  return distance >= 1000 ? `${(distance / 1000).toFixed(3)} km` : `${distance.toFixed(2)} m`
}

function formatArea(area) {
  if (!Number.isFinite(area)) return '-'
  return area >= 1000000 ? `${(area / 1000000).toFixed(3)} km²` : `${area.toFixed(2)} m²`
}

function emitOpenDetail() {
  if (pointPopup.value?.id) {
    emit('open-detail', pointPopup.value)
  }
}

watch(
  () => [props.points, props.activeLevels, props.keyword],
  () => {
    applyPoints()
  },
  { deep: true }
)

watch(
  () => [props.abnormalPoints, props.showAbnormalHeat],
  () => {
    applyAbnormalPoints()
  },
  { deep: true }
)
</script>

<style scoped>
.heritage-map-canvas {
  position: relative;
}

.heritage-map-tools {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 10;
  max-width: min(390px, calc(100% - 28px));
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.2);
  color: var(--text);
  backdrop-filter: blur(10px);
}

.heritage-measure-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.heritage-measure-actions button {
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.heritage-measure-actions button:hover,
.heritage-measure-actions button.active {
  border-color: #0284c7;
  background: color-mix(in srgb, #0ea5e9 14%, var(--surface));
  color: var(--accent);
}

.heritage-measure-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.heritage-measure-actions .clear-measure {
  margin-left: auto;
}

.heritage-measure-text {
  margin: 8px 2px 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}

.heritage-point-popup {
  position: relative;
  width: min(280px, calc(100vw - 40px));
  padding: 14px 16px 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.24);
  color: var(--text);
}

.heritage-point-popup::after {
  position: absolute;
  left: 50%;
  bottom: -7px;
  width: 12px;
  height: 12px;
  border-right: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  background: var(--surface);
  content: '';
  transform: translateX(-50%) rotate(45deg);
}

.heritage-point-popup-close {
  position: absolute;
  top: 7px;
  right: 8px;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: calc(20rem / 14);
  line-height: 20px;
}

.heritage-point-popup-close:hover {
  background: color-mix(in srgb, var(--surface) 80%, var(--line));
  color: var(--text);
}

.heritage-point-popup-title {
  padding-right: 24px;
  overflow-wrap: anywhere;
  font-size: calc(15rem / 14);
  font-weight: 700;
  line-height: 1.4;
}

.heritage-point-popup-level {
  display: inline-block;
  margin-top: 6px;
  padding: 3px 7px;
  border-radius: 4px;
  background: color-mix(in srgb, #2563eb 15%, var(--surface));
  color: var(--accent);
  font-size: calc(12rem / 14);
}

.heritage-point-popup dl {
  margin: 10px 0;
}

.heritage-point-popup dl div {
  display: flex;
  gap: 10px;
  font-size: calc(12rem / 14);
}

.heritage-point-popup dt {
  flex: 0 0 auto;
  color: var(--muted);
}

.heritage-point-popup dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.heritage-point-popup-action {
  position: relative;
  z-index: 1;
  width: 100%;
  min-height: 32px;
  border: 1px solid #2563eb;
  border-radius: 5px;
  background: #2563eb;
  color: #ffffff;
  cursor: pointer;
  font-size: calc(13rem / 14);
}

.heritage-point-popup-action:hover {
  background: #1d4ed8;
}
</style>

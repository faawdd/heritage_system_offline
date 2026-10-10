<template>
  <div ref="mapEl" class="heritage-map-canvas">
    <BaseMapSwitcher />
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
import { fromLonLat } from 'ol/proj'
import VectorSource from 'ol/source/Vector'
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
  }
})

const emit = defineEmits(['select', 'open-detail'])

const mapEl = ref(null)
const mapRef = ref(null)
const vectorSource = new VectorSource()
const abnormalSource = new VectorSource()
const abnormalHeatSource = new VectorSource()
const abnormalLayerRef = ref(null)
const abnormalHeatLayerRef = ref(null)
const pointPopupEl = ref(null)
const pointPopupOverlayRef = ref(null)
const pointPopup = ref({})
let mapResizeObserver = null
let mapResizeFrame = 0
let onlineBaseLayers = []
let offlineBaseLayer = null
let stopWatchingBasemap = null

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

  const keyword = (props.keyword || '').trim()
  const rows = (props.points || []).filter((item) => {
    const levelOk = (props.activeLevels || []).includes(item.level)
    const keywordOk = !keyword || String(item.name || '').includes(keyword)
    return levelOk && keywordOk
  })

  rows.forEach((item) => {
    if (!validLonLat(item.lng, item.lat)) return
    const feature = new Feature({
      geometry: new Point(fromLonLat([item.lng, item.lat])),
      payload: item
    })
    feature.setStyle(markerStyle(item.level))
    vectorSource.addFeature(feature)
  })
  fitHeritagePoints(mapRef.value, props.points || [])
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
  const abnormalLayer = new VectorLayer({ source: abnormalSource })
  const abnormalHeatLayer = new HeatmapLayer({
    source: abnormalHeatSource,
    blur: 20,
    radius: 14,
    weight: (feature) => Number(feature.get('weight') || 0.6),
    visible: Boolean(props.showAbnormalHeat)
  })

  const map = new Map({
    target: mapEl.value,
    layers: [...onlineBaseLayers, offlineBaseLayer, abnormalHeatLayer, vectorLayer, abnormalLayer],
    view: new View(nationalViewOptions())
  })

  map.on('click', (evt) => {
    const feature = map.forEachFeatureAtPixel(evt.pixel, (targetFeature) => targetFeature)
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

  mapRef.value = map
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

.heritage-point-popup {
  position: relative;
  width: min(280px, calc(100vw - 40px));
  padding: 14px 16px 12px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.24);
  color: #163a60;
}

.heritage-point-popup::after {
  position: absolute;
  left: 50%;
  bottom: -7px;
  width: 12px;
  height: 12px;
  border-right: 1px solid rgba(148, 163, 184, 0.42);
  border-bottom: 1px solid rgba(148, 163, 184, 0.42);
  background: #ffffff;
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
  color: #64748b;
  cursor: pointer;
  font-size: calc(20rem / 14);
  line-height: 20px;
}

.heritage-point-popup-close:hover {
  background: #eef4fa;
  color: #163a60;
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
  background: #e8f2ff;
  color: #2563eb;
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
  color: #64748b;
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

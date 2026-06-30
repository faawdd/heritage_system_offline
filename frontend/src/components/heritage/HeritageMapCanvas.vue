<template>
  <div ref="mapEl" class="heritage-map-canvas"></div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
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

import { createTiandituLayerGroup } from '../../utils/tianditu'

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
  }
})

const emit = defineEmits(['select'])

const mapEl = ref(null)
const mapRef = ref(null)
const vectorSource = new VectorSource()
const abnormalSource = new VectorSource()
const abnormalHeatSource = new VectorSource()
const abnormalLayerRef = ref(null)
const abnormalHeatLayerRef = ref(null)

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
    const feature = new Feature({
      geometry: new Point(fromLonLat([item.lng, item.lat])),
      payload: item
    })
    feature.setStyle(markerStyle(item.level))
    vectorSource.addFeature(feature)
  })
}

function applyAbnormalPoints() {
  abnormalSource.clear()
  abnormalHeatSource.clear()

  ;(props.abnormalPoints || []).forEach((item) => {
    const lon = Number(item?.longitude)
    const lat = Number(item?.latitude)
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
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
    layers: [...createTiandituLayerGroup('img'), abnormalHeatLayer, vectorLayer, abnormalLayer],
    view: new View({
      center: fromLonLat([90.21, 42.84]),
      zoom: 9
    })
  })

  map.on('click', (evt) => {
    const feature = map.forEachFeatureAtPixel(evt.pixel, (targetFeature) => targetFeature)
    if (!feature) {
      return
    }
    const payload = feature.get('payload')
    if (payload?.id) {
      emit('select', payload)
    }
  })

  mapRef.value = map
  abnormalLayerRef.value = abnormalLayer
  abnormalHeatLayerRef.value = abnormalHeatLayer
  applyPoints()
  applyAbnormalPoints()
})

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

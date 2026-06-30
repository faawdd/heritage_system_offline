<template>
  <div ref="mapEl" class="heritage-map-canvas"></div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import Feature from 'ol/Feature'
import Map from 'ol/Map'
import View from 'ol/View'
import Point from 'ol/geom/Point'
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
  }
})

const emit = defineEmits(['select'])

const mapEl = ref(null)
const mapRef = ref(null)
const vectorSource = new VectorSource()

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

onMounted(() => {
  const vectorLayer = new VectorLayer({ source: vectorSource })

  const map = new Map({
    target: mapEl.value,
    layers: [...createTiandituLayerGroup('img'), vectorLayer],
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
  applyPoints()
})

watch(
  () => [props.points, props.activeLevels, props.keyword],
  () => {
    applyPoints()
  },
  { deep: true }
)
</script>

<template>
  <div ref="mapEl" class="heritage-zone-map"></div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import Feature from 'ol/Feature'
import Map from 'ol/Map'
import View from 'ol/View'
import Point from 'ol/geom/Point'
import Polygon from 'ol/geom/Polygon'
import VectorLayer from 'ol/layer/Vector'
import { fromLonLat } from 'ol/proj'
import VectorSource from 'ol/source/Vector'
import CircleStyle from 'ol/style/Circle'
import Fill from 'ol/style/Fill'
import Stroke from 'ol/style/Stroke'
import Style from 'ol/style/Style'

import { createTiandituLayerGroup } from '../../utils/tianditu'

const props = defineProps({
  longitude: {
    type: Number,
    default: 90.21
  },
  latitude: {
    type: Number,
    default: 42.84
  },
  protectionZoneData: {
    type: Array,
    default: () => []
  },
  controlZoneData: {
    type: Array,
    default: () => []
  }
})

const mapEl = ref(null)
const source = new VectorSource()

function ringToMercator(ring) {
  if (!Array.isArray(ring)) {
    return []
  }
  return ring
    .filter((item) => Array.isArray(item) && item.length >= 2)
    .map((item) => fromLonLat([Number(item[0]), Number(item[1])]))
}

function applyMapFeatures() {
  source.clear()

  const centerFeature = new Feature({
    geometry: new Point(fromLonLat([props.longitude, props.latitude]))
  })
  centerFeature.setStyle(
    new Style({
      image: new CircleStyle({
        radius: 7,
        fill: new Fill({ color: '#0d9488' }),
        stroke: new Stroke({ color: '#ffffff', width: 2 })
      })
    })
  )
  source.addFeature(centerFeature)

  const protectionRing = ringToMercator(props.protectionZoneData)
  if (protectionRing.length >= 3) {
    const feature = new Feature({ geometry: new Polygon([protectionRing]) })
    feature.setStyle(
      new Style({
        stroke: new Stroke({ color: '#e6a23c', width: 2 }),
        fill: new Fill({ color: 'rgba(230, 162, 60, 0.15)' })
      })
    )
    source.addFeature(feature)
  }

  const controlRing = ringToMercator(props.controlZoneData)
  if (controlRing.length >= 3) {
    const feature = new Feature({ geometry: new Polygon([controlRing]) })
    feature.setStyle(
      new Style({
        stroke: new Stroke({ color: '#f56c6c', width: 2, lineDash: [8, 6] }),
        fill: new Fill({ color: 'rgba(245, 108, 108, 0.08)' })
      })
    )
    source.addFeature(feature)
  }
}

onMounted(() => {
  applyMapFeatures()
  new Map({
    target: mapEl.value,
    layers: [
      ...createTiandituLayerGroup('img'),
      new VectorLayer({ source })
    ],
    view: new View({
      center: fromLonLat([props.longitude, props.latitude]),
      zoom: 14
    })
  })
})

watch(
  () => [props.longitude, props.latitude, props.protectionZoneData, props.controlZoneData],
  () => applyMapFeatures(),
  { deep: true }
)
</script>

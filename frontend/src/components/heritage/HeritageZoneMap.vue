<template>
  <div class="heritage-zone-map-wrap">
    <div ref="mapEl" class="heritage-zone-map"></div>
    <BaseMapSwitcher />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
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

import BaseMapSwitcher from '../maps/BaseMapSwitcher.vue'
import { fitMapExtent, nationalViewOptions, validLonLat } from '../../utils/mapViewport'
import {
  createOfflineTileLayer,
  createTiandituLayerGroup,
  refreshBasemapLayers,
  watchBasemapChanges
} from '../../utils/tianditu'

const props = defineProps({
  longitude: {
    type: Number,
    default: null
  },
  latitude: {
    type: Number,
    default: null
  },
  protectionZoneData: {
    type: Array,
    default: () => []
  },
  controlZoneData: {
    type: Array,
    default: () => []
  },
  bodyBoundaryData: {
    type: Array,
    default: () => []
  }
})

const mapEl = ref(null)
const source = new VectorSource()
let mapRef = null
let onlineBaseLayers = []
let offlineBaseLayer = null
let stopWatchingBasemap = null

function ringToMercator(ring) {
  if (!Array.isArray(ring)) {
    return []
  }
  return ring
    .filter((item) => Array.isArray(item) && validLonLat(item[0], item[1]))
    .map((item) => fromLonLat([Number(item[0]), Number(item[1])]))
}

function applyMapFeatures() {
  source.clear()

  if (validLonLat(props.longitude, props.latitude)) {
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
  }

  const protectionRings = normalizeRings(props.protectionZoneData)
  for (const ring of normalizeRings(props.bodyBoundaryData)) {
    const feature = new Feature({ geometry: new Polygon([ring]) })
    feature.setStyle(new Style({
      stroke: new Stroke({ color: '#0d9488', width: 2 }),
      fill: new Fill({ color: 'rgba(13, 148, 136, 0.12)' })
    }))
    source.addFeature(feature)
  }
  for (const protectionRing of protectionRings) {
    const feature = new Feature({ geometry: new Polygon([protectionRing]) })
    feature.setStyle(
      new Style({
        stroke: new Stroke({ color: '#e6a23c', width: 2 }),
        fill: new Fill({ color: 'rgba(230, 162, 60, 0.15)' })
      })
    )
    source.addFeature(feature)
  }

  const controlRings = normalizeRings(props.controlZoneData)
  for (const controlRing of controlRings) {
    const feature = new Feature({ geometry: new Polygon([controlRing]) })
    feature.setStyle(
      new Style({
        stroke: new Stroke({ color: '#f56c6c', width: 2, lineDash: [8, 6] }),
        fill: new Fill({ color: 'rgba(245, 108, 108, 0.08)' })
      })
    )
    source.addFeature(feature)
  }
  fitMapExtent(mapRef, source.getExtent())
}

function normalizeRings(value) {
  if (!Array.isArray(value) || !value.length) return []
  const rings = Array.isArray(value[0]?.[0]) ? value : [value]
  return rings.map(ringToMercator).filter((ring) => ring.length >= 3)
}

onMounted(() => {
  applyMapFeatures()
  onlineBaseLayers = createTiandituLayerGroup('img')
  offlineBaseLayer = createOfflineTileLayer()
  mapRef = new Map({
    target: mapEl.value,
    layers: [
      ...onlineBaseLayers,
      offlineBaseLayer,
      new VectorLayer({ source })
    ],
    view: new View(nationalViewOptions())
  })
  fitMapExtent(mapRef, source.getExtent())
  const refreshBasemap = () => refreshBasemapLayers({ img: onlineBaseLayers }, offlineBaseLayer, 'img')
  refreshBasemap()
  stopWatchingBasemap = watchBasemapChanges(refreshBasemap)
})

onBeforeUnmount(() => {
  stopWatchingBasemap?.()
  mapRef?.setTarget(undefined)
})

watch(
  () => [props.longitude, props.latitude, props.protectionZoneData, props.controlZoneData, props.bodyBoundaryData],
  () => applyMapFeatures(),
  { deep: true }
)
</script>

<style scoped>
.heritage-zone-map-wrap { position: relative; width: 100%; height: 100%; min-height: 220px; }
.heritage-zone-map { width: 100%; height: 100%; min-height: 220px; }
</style>

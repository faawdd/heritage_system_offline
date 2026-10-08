<template>
  <div class="map-panel">
    <div ref="mapEl" class="map-canvas"></div>
    <BaseMapSwitcher />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import BaseMapSwitcher from './maps/BaseMapSwitcher.vue'
import {
  createOfflineTileLayer,
  createTiandituLayerGroup,
  refreshBasemapLayers,
  watchBasemapChanges
} from '../utils/tianditu'

const mapEl = ref(null)
let mapRef = null
let onlineLayers = []
let offlineLayer = null
let stopWatchingBasemap = null

function refreshBasemap() {
  if (!offlineLayer) return
  refreshBasemapLayers({ img: onlineLayers }, offlineLayer, 'img')
}

onMounted(() => {
  onlineLayers = createTiandituLayerGroup('img')
  offlineLayer = createOfflineTileLayer()
  mapRef = new Map({
    target: mapEl.value,
    layers: [...onlineLayers, offlineLayer],
    view: new View({
      center: [9826439, 4753279],
      zoom: 5
    })
  })
  refreshBasemap()
  stopWatchingBasemap = watchBasemapChanges(refreshBasemap)
})

onBeforeUnmount(() => {
  stopWatchingBasemap?.()
  mapRef?.setTarget(undefined)
})
</script>

<style scoped>
.map-panel { position: relative; }
.map-canvas { width: 100%; height: 100%; }
</style>

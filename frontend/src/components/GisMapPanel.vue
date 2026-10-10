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
import { ElMessage } from 'element-plus'
import { fetchHeritageMapPoints } from '../api/heritageApi'
import { fitHeritagePoints, nationalViewOptions } from '../utils/mapViewport'
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

onMounted(async () => {
  onlineLayers = createTiandituLayerGroup('img')
  offlineLayer = createOfflineTileLayer()
  mapRef = new Map({
    target: mapEl.value,
    layers: [...onlineLayers, offlineLayer],
    view: new View(nationalViewOptions())
  })
  refreshBasemap()
  stopWatchingBasemap = watchBasemapChanges(refreshBasemap)
  fitHeritagePoints(mapRef, [])
  try {
    const result = await fetchHeritageMapPoints()
    if (!result.success) throw new Error(result.message || '加载文物分布失败')
    fitHeritagePoints(mapRef, result.rows || [])
  } catch (error) {
    ElMessage.error(error?.message || '加载文物分布失败')
  }
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

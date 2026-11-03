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
import { isCanceledRequest, networkErrorMessage } from '../utils/networkRequest.js'
import BaseMapSwitcher from './maps/BaseMapSwitcher.vue'
import {
  createOfflineTileLayer,
  createTiandituLayerGroup,
  refreshBasemapLayers,
  watchBasemapChanges
} from '../utils/tianditu'

const mapEl = ref(null)
let mapRef = null
const mapDataController = new AbortController()
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
    const result = await fetchHeritageMapPoints({ signal: mapDataController.signal })
    if (mapDataController.signal.aborted) return
    if (!result.success) throw new Error(result.message || '加载文物分布失败')
    fitHeritagePoints(mapRef, result.rows || [])
  } catch (error) {
    if (!isCanceledRequest(error)) ElMessage.error(networkErrorMessage(error, '加载文物分布失败'))
  }
})

onBeforeUnmount(() => {
  stopWatchingBasemap?.()
  mapDataController.abort()
  mapRef?.setTarget(undefined)
})
</script>

<style scoped>
.map-panel { position: relative; }
.map-canvas { width: 100%; height: 100%; }
</style>

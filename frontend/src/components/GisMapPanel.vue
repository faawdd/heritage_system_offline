<template>
  <div class="map-panel">
    <div ref="mapEl" class="map-canvas"></div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import { createTiandituLayerGroup } from '../utils/tianditu'

const mapEl = ref(null)

onMounted(() => {
  new Map({
    target: mapEl.value,
    layers: [...createTiandituLayerGroup('img')],
    view: new View({
      center: [9826439, 4753279],
      zoom: 5
    })
  })
})
</script>

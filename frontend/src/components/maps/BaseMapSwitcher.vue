<template>
  <div class="base-map-switcher" role="group" aria-label="底图来源">
    <button
      type="button"
      :class="{ active: provider === 'online' }"
      :aria-pressed="provider === 'online'"
      @click="selectProvider('online')"
    >
      <span class="provider-indicator provider-indicator--online" aria-hidden="true"></span>
      天地图
    </button>
    <button
      type="button"
      :class="{ active: provider === 'offline' }"
      :aria-pressed="provider === 'offline'"
      :disabled="!hasOfflineTiles"
      :title="hasOfflineTiles ? '切换到本机离线地图' : '请先导入并选择离线地图切片'"
      @click="selectProvider('offline')"
    >
      <span class="provider-indicator provider-indicator--offline" aria-hidden="true"></span>
      离线地图
    </button>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { getActiveOfflineTileSetId, getBasemapProvider, setBasemapProvider } from '../../utils/tianditu'

const provider = ref(getBasemapProvider())
const hasOfflineTiles = ref(Boolean(getActiveOfflineTileSetId()))

function syncSelection() {
  hasOfflineTiles.value = Boolean(getActiveOfflineTileSetId())
  provider.value = getBasemapProvider()
}

function selectProvider(nextProvider) {
  if (setBasemapProvider(nextProvider)) syncSelection()
}

onMounted(() => {
  window.addEventListener('heritage-basemap-provider-changed', syncSelection)
  window.addEventListener('heritage-offline-basemap-changed', syncSelection)
})

onUnmounted(() => {
  window.removeEventListener('heritage-basemap-provider-changed', syncSelection)
  window.removeEventListener('heritage-offline-basemap-changed', syncSelection)
})
</script>

<style scoped>
.base-map-switcher {
  position: absolute;
  z-index: 12;
  top: 14px;
  right: 14px;
  display: inline-flex;
  gap: 3px;
  padding: 3px;
  border: 1px solid rgba(194, 207, 198, .9);
  border-radius: 6px;
  background: rgba(255, 255, 255, .96);
  box-shadow: 0 3px 12px rgba(27, 47, 35, .12);
  backdrop-filter: blur(8px);
}

button {
  display: inline-flex;
  min-height: 32px;
  align-items: center;
  gap: 7px;
  border: 0;
  border-radius: 4px;
  padding: 0 10px;
  background: transparent;
  color: #536258;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

button.active {
  background: #e8f4ed;
  color: #147a50;
  font-weight: 650;
}

button:disabled {
  cursor: not-allowed;
  opacity: .45;
}

.provider-indicator {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.provider-indicator--online { background: #3789ca; }
.provider-indicator--offline { background: #1ba36b; }
</style>
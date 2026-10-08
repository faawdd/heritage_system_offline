<template>
  <section class="tile-manager">
    <header class="page-header tile-page-header">
      <div>
        <h1>离线地图切片</h1>
        <p>管理本机地图数据，并选择地图浏览时使用的离线底图。</p>
      </div>
      <label class="upload-control" :class="{ disabled: uploading }">
        <input ref="fileInput" type="file" accept=".mbtiles,.zip" :disabled="uploading" @change="handleUpload">
        <el-button type="primary" :loading="uploading">{{ uploading ? '正在导入…' : '导入地图包' }}</el-button>
      </label>
    </header>

    <div class="tile-import-bar card top-space">
      <div class="import-options">
        <label for="tile-scheme">ZIP 行号方案</label>
        <select id="tile-scheme" v-model="zipScheme" :disabled="uploading">
          <option value="xyz">XYZ（北向上）</option>
          <option value="tms">TMS（南向上）</option>
        </select>
      </div>
      <p class="format-note">
        支持 QGIS 导出的 MBTiles 栅格地图，以及包含 <code>z/x/y.png</code> 等结构的 XYZ/TMS ZIP。导入数据仅保存在此设备。
      </p>
    </div>

    <section class="workspace card top-space" :class="{ 'has-selection': selectedTileSet }">
      <div class="catalog-pane">
        <div class="pane-heading">
          <h2>已导入地图</h2>
          <span>{{ tileSets.length }} 个数据集</span>
        </div>
        <div v-if="loading" class="empty-state">正在读取本机地图目录…</div>
        <div v-else-if="tileSets.length === 0" class="empty-state">
          <div class="empty-mark" aria-hidden="true">⌖</div>
          <strong>尚未导入地图</strong>
          <span>选择 QGIS 导出的 MBTiles 或瓦片目录 ZIP</span>
        </div>
        <ul v-else class="tile-list">
          <li v-for="tileSet in tileSets" :key="tileSet.id" class="tile-row" :class="{ active: activeTileSetId === tileSet.id }">
            <button class="tile-select" type="button" @click="activate(tileSet)">
              <span class="radio" :class="{ checked: activeTileSetId === tileSet.id }" aria-hidden="true"></span>
              <span class="tile-info">
                <strong>{{ tileSet.name }}</strong>
                <span>{{ tileSet.kind === 'mbtiles' ? 'MBTiles' : 'XYZ/TMS 目录' }} · {{ tileSet.format.toUpperCase() }}</span>
                <span>缩放 {{ tileSet.min_zoom }}–{{ tileSet.max_zoom }} · {{ tileSet.tile_count.toLocaleString() }} 张</span>
              </span>
            </button>
            <el-button class="delete-button" text type="danger" :aria-label="`删除${tileSet.name}`" @click="removeTileSet(tileSet)">删除</el-button>
          </li>
        </ul>
      </div>

      <div v-if="selectedTileSet" class="preview-pane">
        <div class="pane-heading">
          <h2>{{ selectedTileSet.name }}</h2>
          <span class="active-label">{{ activeTileSetId === selectedTileSet.id && isOfflineProvider ? '当前离线底图' : '点击左侧设为离线底图' }}</span>
        </div>
        <div ref="mapElement" class="map-preview"></div>
        <div class="map-caption">
          <span>{{ selectedTileSet.kind === 'mbtiles' ? `MBTiles · ${selectedTileSet.scheme.toUpperCase()}` : 'XYZ 目录瓦片' }}</span>
          <span v-if="selectedTileSet.bounds">范围 {{ selectedTileSet.bounds.map(value => Number(value).toFixed(3)).join(', ') }}</span>
          <span v-else>无范围元数据</span>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import XYZ from 'ol/source/XYZ'
import { fromLonLat } from 'ol/proj'

import {
  deleteOfflineTileSet,
  fetchOfflineTileSets,
  uploadOfflineTileSet
} from '../../../api/system/offlineTilesApi'
import { getBasemapProvider, setBasemapProvider } from '../../../utils/tianditu'

const ACTIVE_TILE_SET_KEY = 'heritage_offline_tile_set'
const fileInput = ref(null)
const mapElement = ref(null)
const tileSets = ref([])
const loading = ref(false)
const uploading = ref(false)
const zipScheme = ref('xyz')
const activeTileSetId = ref(localStorage.getItem(ACTIVE_TILE_SET_KEY) || '')
let previewMap = null

const selectedTileSet = computed(() => tileSets.value.find(item => item.id === activeTileSetId.value) || tileSets.value[0] || null)
const isOfflineProvider = ref(getBasemapProvider() === 'offline')

function syncBasemapProvider() {
  isOfflineProvider.value = getBasemapProvider() === 'offline'
}

async function loadTileSets() {
  loading.value = true
  try {
    const result = await fetchOfflineTileSets()
    tileSets.value = result.rows || []
    let selectionChanged = false
    if (!tileSets.value.some(item => item.id === activeTileSetId.value)) {
      activeTileSetId.value = tileSets.value[0]?.id || ''
      selectionChanged = true
    }
    if (activeTileSetId.value) {
      localStorage.setItem(ACTIVE_TILE_SET_KEY, activeTileSetId.value)
    } else {
      localStorage.removeItem(ACTIVE_TILE_SET_KEY)
    }
    if (selectionChanged) {
      window.dispatchEvent(new CustomEvent('heritage-offline-basemap-changed'))
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.message || '加载离线地图失败')
  } finally {
    loading.value = false
  }
}

async function handleUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const scheme = file.name.toLowerCase().endsWith('.zip') ? zipScheme.value : 'xyz'
    const result = await uploadOfflineTileSet(file, '', scheme)
    tileSets.value = [...tileSets.value, result.data]
    activate(result.data)
    ElMessage.success('地图切片已导入本机')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.message || '导入地图切片失败')
  } finally {
    uploading.value = false
    event.target.value = ''
  }
}

function activate(tileSet) {
  activeTileSetId.value = tileSet.id
  localStorage.setItem(ACTIVE_TILE_SET_KEY, tileSet.id)
  setBasemapProvider('offline')
  window.dispatchEvent(new CustomEvent('heritage-offline-basemap-changed'))
}

async function removeTileSet(tileSet) {
  try {
    await ElMessageBox.confirm(`删除“${tileSet.name}”及其本机切片文件？`, '删除地图数据', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await deleteOfflineTileSet(tileSet.id)
    tileSets.value = tileSets.value.filter(item => item.id !== tileSet.id)
    if (activeTileSetId.value === tileSet.id) {
      activeTileSetId.value = tileSets.value[0]?.id || ''
      if (activeTileSetId.value) localStorage.setItem(ACTIVE_TILE_SET_KEY, activeTileSetId.value)
      else localStorage.removeItem(ACTIVE_TILE_SET_KEY)
      window.dispatchEvent(new CustomEvent('heritage-offline-basemap-changed'))
    }
    ElMessage.success('地图数据已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.message || error?.message || '删除地图数据失败')
    }
  }
}

function renderPreview() {
  if (!mapElement.value || !selectedTileSet.value) return
  previewMap?.setTarget(undefined)
  const token = localStorage.getItem('heritage_access_token') || ''
  const tileSet = selectedTileSet.value
  const source = new XYZ({
    url: `/api/v1/gis/offline-tiles/${tileSet.id}/{z}/{x}/{y}/?access_token=${encodeURIComponent(token)}`,
    maxZoom: tileSet.max_zoom,
    minZoom: tileSet.min_zoom,
    crossOrigin: 'anonymous'
  })
  const layers = [new TileLayer({ source })]
  const center = tileSet.bounds?.length === 4
    ? fromLonLat([(tileSet.bounds[0] + tileSet.bounds[2]) / 2, (tileSet.bounds[1] + tileSet.bounds[3]) / 2])
    : fromLonLat([90.21, 42.84])
  previewMap = new Map({
    target: mapElement.value,
    layers,
    view: new View({ center, zoom: Math.min(Math.max(tileSet.min_zoom + 2, 3), tileSet.max_zoom) })
  })
}

watch(selectedTileSet, async () => {
  await nextTick()
  renderPreview()
})

onMounted(async () => {
  window.addEventListener('heritage-basemap-provider-changed', syncBasemapProvider)
  window.addEventListener('heritage-offline-basemap-changed', syncBasemapProvider)
  await loadTileSets()
  await nextTick()
  renderPreview()
})

onBeforeUnmount(() => {
  window.removeEventListener('heritage-basemap-provider-changed', syncBasemapProvider)
  window.removeEventListener('heritage-offline-basemap-changed', syncBasemapProvider)
  previewMap?.setTarget(undefined)
})
</script>

<style scoped>
.tile-manager { min-height: 100%; }
.tile-page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.upload-control { position: relative; flex: none; cursor: pointer; }
.upload-control.disabled { pointer-events: none; opacity: .65; }
.upload-control input { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); }
.tile-import-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.import-options { display: flex; flex: none; align-items: center; gap: 10px; color: var(--text); font-size: 13px; }
.import-options select { min-height: 34px; padding: 0 28px 0 10px; border: 1px solid var(--line); border-radius: 4px; background: var(--surface); color: var(--text); font: inherit; }
.format-note { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.6; }
.format-note code { color: var(--text); }
.workspace { display: grid; grid-template-columns: minmax(320px, 1fr); gap: 20px; }
.workspace.has-selection { grid-template-columns: minmax(280px, .78fr) minmax(360px, 1.22fr); }
.catalog-pane, .preview-pane { min-width: 0; }
.preview-pane { border-left: 1px solid var(--line); padding-left: 20px; }
.pane-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 42px; border-bottom: 1px solid var(--line); }
.pane-heading h2 { overflow: hidden; margin: 0; color: var(--text); font-size: 15px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.pane-heading > span { flex: none; color: var(--muted); font-size: 12px; }
.active-label { color: var(--success-text) !important; }
.tile-list { margin: 0; padding: 0; list-style: none; }
.tile-row { display: flex; align-items: center; gap: 8px; min-height: 84px; padding: 11px 8px 11px 2px; border-bottom: 1px solid var(--line); }
.tile-row.active { background: color-mix(in srgb, var(--accent) 12%, var(--surface)); }
.tile-select { display: flex; flex: 1; min-width: 0; align-items: flex-start; gap: 11px; border: 0; padding: 4px; background: transparent; color: var(--text); text-align: left; cursor: pointer; }
.radio { flex: none; width: 16px; height: 16px; margin-top: 2px; border: 1px solid var(--muted); border-radius: 50%; }
.radio.checked { border: 5px solid var(--accent); }
.tile-info { display: grid; min-width: 0; gap: 4px; }
.tile-info strong { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.tile-info span { color: var(--muted); font-size: 12px; }
.delete-button { flex: none; }
.empty-state { display: grid; min-height: 220px; align-content: center; justify-items: center; gap: 10px; color: var(--muted); font-size: 13px; text-align: center; }
.empty-state strong { color: var(--text); font-size: 15px; }
.empty-mark { display: grid; width: 44px; height: 44px; place-items: center; border: 1px solid var(--line); border-radius: 50%; color: var(--accent); font-size: 27px; }
.map-preview { height: min(58vh, 520px); min-height: 330px; background-color: var(--bg); background-image: linear-gradient(45deg, color-mix(in srgb, var(--line) 45%, transparent) 25%, transparent 25%), linear-gradient(-45deg, color-mix(in srgb, var(--line) 45%, transparent) 25%, transparent 25%), linear-gradient(45deg, transparent 75%, color-mix(in srgb, var(--line) 45%, transparent) 75%), linear-gradient(-45deg, transparent 75%, color-mix(in srgb, var(--line) 45%, transparent) 75%); background-size: 24px 24px; background-position: 0 0, 0 12px, 12px -12px, -12px 0; }
.map-caption { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px 18px; padding-top: 11px; color: var(--muted); font-size: 12px; }
@media (max-width: 960px) { .workspace.has-selection { grid-template-columns: 1fr; } .preview-pane { border-top: 1px solid var(--line); border-left: 0; padding: 14px 0 0; } }
@media (max-width: 600px) { .tile-page-header, .tile-import-bar { align-items: flex-start; } .workspace.has-selection { grid-template-columns: minmax(0, 1fr); } .map-preview { min-height: 280px; } }
</style>
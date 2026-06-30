<template>
  <div class="kml-overlay-map-wrap">
    <div ref="mapEl" class="kml-overlay-map"></div>
    <div class="kml-loading-mask" v-if="isKmlLoading">
      <div class="kml-loading-card">
        <div class="kml-loading-spinner"></div>
        <div>{{ loadingText }}</div>
      </div>
    </div>
    <div ref="featurePopupEl" class="kml-feature-popup" :class="{ 'is-visible': popupVisible }">
      <h4>{{ popupTitle }}</h4>
      <div class="kml-feature-popup-content">{{ popupContent }}</div>
    </div>
    <div class="kml-overlay-toolbar">
      <div class="toolbar-row">
        <span class="toolbar-label">底图</span>
        <button type="button" class="toolbar-btn" :class="{ active: baseMode === 'img' }" @click="switchBase('img')">卫星</button>
        <button type="button" class="toolbar-btn" :class="{ active: baseMode === 'vec' }" @click="switchBase('vec')">电子</button>
        <button type="button" class="toolbar-btn" :class="{ active: baseMode === 'ter' }" @click="switchBase('ter')">地形</button>
      </div>
      <div class="toolbar-row">
        <span class="toolbar-label">图层</span>
        <button type="button" class="toolbar-btn" :class="{ active: showKmlLayer }" @click="toggleKmlLayer">KML</button>
        <button type="button" class="toolbar-btn" :class="{ active: showHeritageLayer }" @click="toggleHeritageLayer">文物点</button>
        <button type="button" class="toolbar-btn" :class="{ active: showConflictLayer }" @click="toggleConflictLayer">冲突点</button>
        <button type="button" class="toolbar-btn" :class="{ active: showOverlapLayer }" @click="toggleOverlapLayer">叠加点</button>
      </div>
      <div class="toolbar-row">
        <span class="toolbar-label">分组</span>
        <select class="toolbar-select" v-model="activeConflictGroup" @change="reloadConflictLayer">
          <option value="ALL">全部</option>
          <option v-for="name in conflictGroupOptions" :key="name" :value="name">{{ name }}</option>
        </select>
        <button type="button" class="toolbar-btn" @click="focusActiveGroup">聚焦</button>
      </div>
      <div class="toolbar-row">
        <span class="toolbar-label">测距</span>
        <button type="button" class="toolbar-btn" :class="{ active: measureMode }" @click="toggleMeasureMode">{{ measureMode ? '结束测距' : '开始测距' }}</button>
        <button type="button" class="toolbar-btn" @click="clearMeasure">清除</button>
      </div>
      <div class="measure-text" v-if="measureText">{{ measureText }}</div>
      <div class="measure-text" v-if="overlapEntries.length > 0">检测到叠加 {{ overlapEntries.length }} 处</div>
    </div>
    <div class="kml-overlay-tip" v-if="tips.length > 0">
      <div v-for="(item, idx) in tips" :key="idx">{{ item }}</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { getCenter, intersects as intersectsExtent } from 'ol/extent'
import Feature from 'ol/Feature'
import OlMap from 'ol/Map'
import Overlay from 'ol/Overlay'
import View from 'ol/View'
import LineString from 'ol/geom/LineString'
import Point from 'ol/geom/Point'
import VectorLayer from 'ol/layer/Vector'
import { fromLonLat, toLonLat } from 'ol/proj'
import VectorSource from 'ol/source/Vector'
import KML from 'ol/format/KML'
import { getArea, getLength } from 'ol/sphere'
import CircleStyle from 'ol/style/Circle'
import Fill from 'ol/style/Fill'
import Stroke from 'ol/style/Stroke'
import Style from 'ol/style/Style'

import { createTiandituLayerGroup } from '../../utils/tianditu'
import { fetchGisKmlBatchKmlContent } from '../../api/gisApi'
import { fetchGisKmlRecordKmlContent } from '../../api/gisApi'
import { fetchHeritageMapPoints } from '../../api/heritageApi'

const props = defineProps({
  selectedRecords: {
    type: Array,
    default: () => []
  },
  conflictRows: {
    type: Array,
    default: () => []
  },
  focusConflict: {
    type: Object,
    default: null
  },
  focusOverlap: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['conflict-click', 'overlap-click', 'overlap-update'])

const MAX_FETCH_CONCURRENCY = 4

const mapEl = ref(null)
const tips = ref([])
const baseMode = ref('img')
const showKmlLayer = ref(true)
const showHeritageLayer = ref(true)
const showConflictLayer = ref(true)
const showOverlapLayer = ref(true)
const measureMode = ref(false)
const measureText = ref('')
const isKmlLoading = ref(false)
const loadingText = ref('正在加载KML...')
const popupVisible = ref(false)
const popupTitle = ref('')
const popupContent = ref('')
const activeConflictGroup = ref('ALL')
const conflictGroupOptions = ref([])

const kmlSource = new VectorSource()
const heritageSource = new VectorSource()
const conflictSource = new VectorSource()
const overlapSource = new VectorSource()
const measureSource = new VectorSource()
const mapRef = ref(null)
const kmlLayerRef = ref(null)
const heritageLayerRef = ref(null)
const conflictLayerRef = ref(null)
const overlapLayerRef = ref(null)
const measureLayerRef = ref(null)
const baseLayersRef = ref({ img: [], vec: [], ter: [] })
const featurePopupEl = ref(null)
const popupOverlayRef = ref(null)
let measurePoints = []
let loadToken = 0
let overlapToken = 0
const overlapEntries = ref([])
const kmlStyleCache = new Map()
const kmlTextCache = new Map()

const palette = ['#0ea5e9', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#14b8a6']

function kmlStyleByIndex(index) {
  if (kmlStyleCache.has(index)) {
    return kmlStyleCache.get(index)
  }
  const color = palette[index % palette.length]
  const style = new Style({
    image: new CircleStyle({
      radius: 5,
      fill: new Fill({ color }),
      stroke: new Stroke({ color: '#ffffff', width: 1.5 })
    }),
    stroke: new Stroke({ color, width: 2 }),
    fill: new Fill({ color: `${color}33` })
  })
  kmlStyleCache.set(index, style)
  return style
}

function conflictStyle() {
  return new Style({
    image: new CircleStyle({
      radius: 6,
      fill: new Fill({ color: '#dc2626' }),
      stroke: new Stroke({ color: '#ffffff', width: 2 })
    })
  })
}

function heritagePointStyle() {
  return new Style({
    image: new CircleStyle({
      radius: 4,
      fill: new Fill({ color: '#2563eb' }),
      stroke: new Stroke({ color: '#ffffff', width: 1.5 })
    })
  })
}

function conflictStyleByGroup(groupName) {
  const selected = activeConflictGroup.value
  if (selected === 'ALL' || selected === groupName) {
    return conflictStyle()
  }
  return new Style({
    image: new CircleStyle({
      radius: 5,
      fill: new Fill({ color: '#94a3b8' }),
      stroke: new Stroke({ color: '#ffffff', width: 2 })
    })
  })
}

function conflictActiveStyle() {
  return new Style({
    image: new CircleStyle({
      radius: 8,
      fill: new Fill({ color: '#f59e0b' }),
      stroke: new Stroke({ color: '#ffffff', width: 2 })
    })
  })
}

function overlapStyle(kind) {
  const color = kind === 'point' ? '#7c3aed' : kind === 'line' ? '#0ea5e9' : '#ef4444'
  return new Style({
    image: new CircleStyle({
      radius: 6,
      fill: new Fill({ color }),
      stroke: new Stroke({ color: '#ffffff', width: 2 })
    })
  })
}

function measurePointStyle() {
  return new Style({
    image: new CircleStyle({
      radius: 5,
      fill: new Fill({ color: '#16a34a' }),
      stroke: new Stroke({ color: '#ffffff', width: 2 })
    })
  })
}

function measureLineStyle() {
  return new Style({
    stroke: new Stroke({ color: '#22c55e', width: 2, lineDash: [8, 6] })
  })
}

function haversineMeters([lon1, lat1], [lon2, lat2]) {
  const toRad = (deg) => (deg * Math.PI) / 180
  const R = 6378137
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

function formatDistance(distance) {
  if (!Number.isFinite(distance)) {
    return '0 m'
  }
  if (distance >= 1000) {
    return `${(distance / 1000).toFixed(2)} km`
  }
  return `${distance.toFixed(1)} m`
}

async function reloadKmlLayers() {
  loadToken += 1
  const currentToken = loadToken
  kmlSource.clear()
  tips.value = []
  closeFeaturePopup()

  const selectedRecords = props.selectedRecords || []
  if (selectedRecords.length === 0) {
    reloadOverlapLayer()
    fitAll()
    return
  }

  isKmlLoading.value = true
  loadingText.value = `正在加载 ${selectedRecords.length} 个KML文件...`

  const results = new Array(selectedRecords.length)
  let doneCount = 0

  const resolvedByRecordId = new Map()
  const pendingRows = []

  selectedRecords.forEach((row, idx) => {
    const recordId = Number(row?.id)
    if (Number.isFinite(recordId) && recordId > 0) {
      pendingRows.push({ row, idx, recordId })
    }
  })

  if (pendingRows.length > 0) {
    try {
      loadingText.value = `正在批量请求 ${pendingRows.length} 个KML文件...`
      const batchResult = await fetchGisKmlBatchKmlContent(pendingRows.map((item) => item.recordId))
      if (batchResult?.success) {
        ;(batchResult.data?.items || []).forEach((item) => {
          const key = Number(item?.record_id)
          if (Number.isFinite(key)) {
            resolvedByRecordId.set(key, {
              success: true,
              text: String(item?.kml_text || '')
            })
          }
        })
        ;(batchResult.data?.failed_items || []).forEach((item) => {
          const key = Number(item?.record_id)
          if (Number.isFinite(key)) {
            resolvedByRecordId.set(key, {
              success: false,
              message: String(item?.message || '批量接口返回失败')
            })
          }
        })
      }
    } catch (_error) {
      // 批量接口失败时自动降级到单条接口，不中断加载流程。
    }
  }

  await runWithConcurrency(selectedRecords, MAX_FETCH_CONCURRENCY, async (row, idx) => {
    const recordId = row?.id
    const title = row?.title || `记录${idx + 1}`

    if (!recordId) {
      results[idx] = { idx, title, success: false, message: '无记录ID，已跳过' }
      doneCount += 1
      loadingText.value = `正在加载 ${selectedRecords.length} 个KML文件... (${doneCount}/${selectedRecords.length})`
      return
    }

    try {
      const cacheKey = [String(recordId), String(row?.title || ''), String(row?.created_at || '')].join('|')
      let text = kmlTextCache.get(cacheKey)

      if (!text) {
        const batchResolved = resolvedByRecordId.get(Number(recordId))
        if (batchResolved?.success) {
          text = batchResolved.text
        } else {
          const result = await fetchGisKmlRecordKmlContent(recordId)
          if (!result.success) {
            throw new Error(result.message || batchResolved?.message || '解析失败')
          }
          text = result.data?.kml_text || ''
        }
        if (!text) {
          throw new Error('KML 内容为空')
        }
        kmlTextCache.set(cacheKey, text)
      }

      results[idx] = { idx, title, success: true, text }
    } catch (error) {
      results[idx] = {
        idx,
        title,
        success: false,
        message: error?.message || '未知错误'
      }
    } finally {
      doneCount += 1
      loadingText.value = `正在加载 ${selectedRecords.length} 个KML文件... (${doneCount}/${selectedRecords.length})`
    }
  })

  if (currentToken !== loadToken) {
    isKmlLoading.value = false
    return
  }

  for (let i = 0; i < results.length; i += 1) {
    const item = results[i]
    if (!item.success) {
      tips.value.push(`${item.title}: 解析失败（${item.message}）`)
      continue
    }

    try {
      const features = new KML().readFeatures(item.text, {
        dataProjection: 'EPSG:4326',
        featureProjection: 'EPSG:3857'
      })
      features.forEach((feature, featureIndex) => {
        feature.set('isKmlFeature', true)
        feature.set('kmlColorIndex', item.idx)
        feature.set('sourceName', item.title)
        feature.set('featureName', String(feature.get('name') || `要素#${featureIndex + 1}`))
      })
      kmlSource.addFeatures(features)
      if (i % 1 === 0) {
        await new Promise((resolve) => setTimeout(resolve, 0))
      }
    } catch (error) {
      tips.value.push(`${item.title}: 解析失败（${error?.message || '未知错误'}）`)
    }
  }

  await reloadOverlapLayer()
  fitAll()
  isKmlLoading.value = false
}

async function runWithConcurrency(items, limit, worker) {
  const max = Math.max(1, Number(limit) || 1)
  let index = 0

  async function runOne() {
    while (index < items.length) {
      const current = index
      index += 1
      await worker(items[current], current)
    }
  }

  const runners = []
  const runnerCount = Math.min(max, items.length)
  for (let i = 0; i < runnerCount; i += 1) {
    runners.push(runOne())
  }
  await Promise.all(runners)
}

function reloadConflictLayer() {
  conflictSource.clear()
  const groups = new Set()
  const activeRows = []
  ;(props.conflictRows || []).forEach((row) => {
    const sourceName = String(row?.feature_source || '未知来源')
    groups.add(sourceName)
    if (activeConflictGroup.value === 'ALL' || activeConflictGroup.value === sourceName) {
      activeRows.push(row)
    }
  })

  conflictGroupOptions.value = Array.from(groups)
  if (
    activeConflictGroup.value !== 'ALL' &&
    conflictGroupOptions.value.includes(activeConflictGroup.value) === false
  ) {
    activeConflictGroup.value = 'ALL'
    activeRows.length = 0
    ;(props.conflictRows || []).forEach((row) => activeRows.push(row))
  }

  activeRows.forEach((row) => {
    const lon = Number(row?.site_longitude)
    const lat = Number(row?.site_latitude)
    if (Number.isNaN(lon) || Number.isNaN(lat)) {
      return
    }
    const sourceName = String(row?.feature_source || '未知来源')
    const feature = new Feature({ geometry: new Point(fromLonLat([lon, lat])) })
    feature.set('site_id', String(row?.site_id || ''))
    feature.set('site_name', String(row?.site_name || ''))
    feature.set('relation', String(row?.relation || ''))
    feature.set('distance_m', row?.distance_m)
    feature.set('sourceName', sourceName)
    feature.setStyle(conflictStyleByGroup(sourceName))
    conflictSource.addFeature(feature)
  })
  applyFocusConflictStyle()
  fitAll()
}

function normalizeKind(geometryType) {
  if (geometryType === 'Point' || geometryType === 'MultiPoint') {
    return 'point'
  }
  if (geometryType === 'LineString' || geometryType === 'MultiLineString') {
    return 'line'
  }
  return 'polygon'
}

function midpoint(a, b) {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
}

function distanceInMetersBy3857(a, b) {
  const dx = a[0] - b[0]
  const dy = a[1] - b[1]
  return Math.sqrt(dx * dx + dy * dy)
}

function buildOverlapKey(sourceA, sourceB, featureA, featureB, kind) {
  const sourcePair = [String(sourceA || ''), String(sourceB || '')].sort().join('|')
  const featurePair = [String(featureA || ''), String(featureB || '')].sort().join('|')
  return `${kind}|${sourcePair}|${featurePair}`
}

async function reloadOverlapLayer() {
  overlapToken += 1
  const currentToken = overlapToken
  overlapSource.clear()
  overlapEntries.value = []

  const features = kmlSource.getFeatures()
  if (!features || features.length < 2) {
    emit('overlap-update', [])
    return
  }

  const entries = []
  const keySet = new Set()

  const sortedRows = features
    .map((feature) => {
      const geometry = feature.getGeometry()
      if (!geometry) {
        return null
      }
      const extent = geometry.getExtent()
      return {
        feature,
        geometry,
        extent,
        minX: extent[0],
        maxX: extent[2],
        center: getCenter(extent),
        source: String(feature.get('sourceName') || ''),
        name: String(feature.get('featureName') || ''),
        kind: normalizeKind(geometry.getType())
      }
    })
    .filter(Boolean)
    .sort((a, b) => a.minX - b.minX)

  for (let i = 0; i < sortedRows.length; i += 1) {
    if (currentToken !== overlapToken) {
      return
    }
    if (i > 0 && i % 24 === 0) {
      await new Promise((resolve) => setTimeout(resolve, 0))
      if (currentToken !== overlapToken) {
        return
      }
    }

    const a = sortedRows[i]
    const geomA = a.geometry
    const sourceA = a.source
    const featureA = a.name
    const extentA = a.extent
    const centerA = a.center
    const kindA = a.kind

    for (let j = i + 1; j < sortedRows.length; j += 1) {
      const b = sortedRows[j]
      if (b.minX > a.maxX) {
        break
      }

      const geomB = b.geometry
      const sourceB = b.source
      if (!sourceA || !sourceB || sourceA === sourceB) {
        continue
      }

      const extentB = b.extent
      if (!intersectsExtent(extentA, extentB)) {
        continue
      }

      const centerB = b.center
      const kindB = b.kind
      const kind = kindA === 'point' && kindB === 'point' ? 'point' : kindA === 'polygon' || kindB === 'polygon' ? 'polygon' : 'line'

      let overlapped = false
      let distanceM = null
      if (kind === 'point') {
        const lonLatA = toLonLat(centerA)
        const lonLatB = toLonLat(centerB)
        distanceM = haversineMeters(lonLatA, lonLatB)
        overlapped = distanceM <= 1
      } else {
        const nearestOnB = geomB.getClosestPoint(centerA)
        const nearestOnA = geomA.getClosestPoint(nearestOnB)
        distanceM = distanceInMetersBy3857(nearestOnA, nearestOnB)
        overlapped = distanceM <= 1
      }

      if (!overlapped) {
        continue
      }

      const featureB = b.name
      const overlapKey = buildOverlapKey(sourceA, sourceB, featureA, featureB, kind)
      if (keySet.has(overlapKey)) {
        continue
      }
      keySet.add(overlapKey)

      entries.push({
        overlap_key: overlapKey,
        kind,
        source_a: sourceA,
        source_b: sourceB,
        feature_a: featureA,
        feature_b: featureB,
        distance_m: distanceM == null ? null : Number(distanceM.toFixed(2)),
        coordinate: midpoint(centerA, centerB)
      })
    }
  }

  if (currentToken !== overlapToken) {
    return
  }

  entries.forEach((entry, index) => {
    const marker = new Feature({ geometry: new Point(entry.coordinate) })
    marker.set('overlapIndex', index)
    marker.set('overlapKey', entry.overlap_key)
    marker.setStyle(overlapStyle(entry.kind))
    overlapSource.addFeature(marker)
  })

  overlapEntries.value = entries
  emit('overlap-update', entries)
}

function fitAll() {
  if (!mapRef.value) {
    return
  }
  const extentA = kmlSource.getExtent()
  const extentB = conflictSource.getExtent()
  const hasA = extentA && Number.isFinite(extentA[0])
  const hasB = extentB && Number.isFinite(extentB[0])

  if (!hasA && !hasB) {
    mapRef.value.getView().setCenter(fromLonLat([90.21, 42.84]))
    mapRef.value.getView().setZoom(9)
    return
  }

  let extent = hasA ? extentA.slice() : extentB.slice()
  if (hasA && hasB) {
    extent = [
      Math.min(extentA[0], extentB[0]),
      Math.min(extentA[1], extentB[1]),
      Math.max(extentA[2], extentB[2]),
      Math.max(extentA[3], extentB[3])
    ]
  }

  mapRef.value.getView().fit(extent, {
    padding: [24, 24, 24, 24],
    maxZoom: 16,
    duration: 220
  })
}

function switchBase(mode) {
  baseMode.value = mode
  const groups = baseLayersRef.value
  Object.keys(groups).forEach((key) => {
    groups[key].forEach((layer) => layer.setVisible(key === mode))
  })
}

function toggleKmlLayer() {
  showKmlLayer.value = !showKmlLayer.value
  if (kmlLayerRef.value) {
    kmlLayerRef.value.setVisible(showKmlLayer.value)
  }
}

function toggleHeritageLayer() {
  showHeritageLayer.value = !showHeritageLayer.value
  if (heritageLayerRef.value) {
    heritageLayerRef.value.setVisible(showHeritageLayer.value)
  }
}

function toggleConflictLayer() {
  showConflictLayer.value = !showConflictLayer.value
  if (conflictLayerRef.value) {
    conflictLayerRef.value.setVisible(showConflictLayer.value)
  }
}

function toggleOverlapLayer() {
  showOverlapLayer.value = !showOverlapLayer.value
  if (overlapLayerRef.value) {
    overlapLayerRef.value.setVisible(showOverlapLayer.value)
  }
}

async function loadHeritageLayer() {
  try {
    const result = await fetchHeritageMapPoints()
    const rows = result?.rows || []
    heritageSource.clear()

    rows.forEach((row) => {
      const lon = Number(row?.longitude ?? row?.lng)
      const lat = Number(row?.latitude ?? row?.lat)
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return
      }

      const feature = new Feature({ geometry: new Point(fromLonLat([lon, lat])) })
      feature.set('isHeritage', true)
      feature.set('site_id', String(row?.id || ''))
      feature.set('site_name', String(row?.name || ''))
      feature.set('site_level', String(row?.level || ''))
      feature.setStyle(heritagePointStyle())
      heritageSource.addFeature(feature)
    })
  } catch (error) {
    tips.value.push('文物点图层加载失败，已跳过显示')
  }
}

function toggleMeasureMode() {
  measureMode.value = !measureMode.value
  if (!measureMode.value) {
    measureText.value = measurePoints.length > 1 ? measureText.value : ''
  }
}

function clearMeasure() {
  measurePoints = []
  measureSource.clear()
  measureText.value = ''
}

function focusActiveGroup() {
  if (!mapRef.value) {
    return
  }
  if (activeConflictGroup.value === 'ALL') {
    fitAll()
    return
  }

  const features = conflictSource
    .getFeatures()
    .filter((item) => String(item.get('sourceName') || '') === activeConflictGroup.value)

  if (features.length === 0) {
    fitAll()
    return
  }

  let extent = features[0].getGeometry().getExtent().slice()
  for (let i = 1; i < features.length; i += 1) {
    const current = features[i].getGeometry().getExtent()
    extent = [
      Math.min(extent[0], current[0]),
      Math.min(extent[1], current[1]),
      Math.max(extent[2], current[2]),
      Math.max(extent[3], current[3])
    ]
  }

  mapRef.value.getView().fit(extent, {
    padding: [24, 24, 24, 24],
    maxZoom: 17,
    duration: 220
  })
}

function handleMeasureClick(coordinate) {
  measurePoints.push(coordinate)

  const pointFeature = new Feature({ geometry: new Point(coordinate) })
  pointFeature.setStyle(measurePointStyle())
  measureSource.addFeature(pointFeature)

  if (measurePoints.length >= 2) {
    const lineFeature = new Feature({ geometry: new LineString(measurePoints.slice()) })
    lineFeature.setStyle(measureLineStyle())
    measureSource.addFeature(lineFeature)

    let total = 0
    for (let i = 1; i < measurePoints.length; i += 1) {
      const a = toLonLat(measurePoints[i - 1])
      const b = toLonLat(measurePoints[i])
      total += haversineMeters(a, b)
    }
    measureText.value = `累计距离：${formatDistance(total)}（点击继续追加）`
  } else {
    measureText.value = '已设置起点，点击地图继续测距'
  }
}

function conflictKey(rowLike) {
  return [
    String(rowLike?.site_id || ''),
    String(rowLike?.feature_source || rowLike?.sourceName || ''),
    String(rowLike?.relation || '')
  ].join('|')
}

function applyFocusConflictStyle() {
  const focusKey = conflictKey(props.focusConflict)
  conflictSource.getFeatures().forEach((feature) => {
    const rowLike = {
      site_id: feature.get('site_id'),
      feature_source: feature.get('sourceName'),
      relation: feature.get('relation')
    }
    if (focusKey && focusKey === conflictKey(rowLike)) {
      feature.setStyle(conflictActiveStyle())
    } else {
      feature.setStyle(conflictStyleByGroup(String(feature.get('sourceName') || '未知来源')))
    }
  })
}

function focusConflictOnMap(rowLike) {
  if (!mapRef.value || !rowLike) {
    return
  }
  const targetKey = conflictKey(rowLike)
  if (!targetKey) {
    return
  }
  const target = conflictSource.getFeatures().find((feature) => {
    const item = {
      site_id: feature.get('site_id'),
      feature_source: feature.get('sourceName'),
      relation: feature.get('relation')
    }
    return conflictKey(item) === targetKey
  })
  if (!target) {
    return
  }
  const point = target.getGeometry().getCoordinates()
  mapRef.value.getView().animate({ center: point, zoom: 15, duration: 220 })
}

function focusOverlapOnMap(rowLike) {
  if (!mapRef.value || !rowLike?.overlap_key) {
    return
  }
  const target = overlapSource.getFeatures().find((item) => item.get('overlapKey') === rowLike.overlap_key)
  if (!target) {
    return
  }
  mapRef.value.getView().animate({
    center: target.getGeometry().getCoordinates(),
    zoom: 15,
    duration: 220
  })
}

function formatLength(lengthM) {
  if (!Number.isFinite(lengthM)) {
    return '-'
  }
  if (lengthM >= 1000) {
    return `${(lengthM / 1000).toFixed(3)} km`
  }
  return `${lengthM.toFixed(2)} m`
}

function formatArea(areaM2) {
  if (!Number.isFinite(areaM2)) {
    return '-'
  }
  if (areaM2 >= 1000000) {
    return `${(areaM2 / 1000000).toFixed(3)} km²`
  }
  return `${areaM2.toFixed(2)} m²`
}

function geometrySummaryText(geometry) {
  if (!geometry) {
    return '几何信息: -'
  }
  const geometryType = geometry.getType()
  if (geometryType === 'Point') {
    const lonLat = toLonLat(geometry.getCoordinates())
    return `坐标: ${lonLat[0].toFixed(6)}, ${lonLat[1].toFixed(6)}`
  }
  if (geometryType === 'LineString' || geometryType === 'MultiLineString') {
    const lengthM = getLength(geometry, { projection: 'EPSG:3857' })
    return `长度: ${formatLength(lengthM)}`
  }
  if (geometryType === 'Polygon' || geometryType === 'MultiPolygon') {
    const areaM2 = getArea(geometry, { projection: 'EPSG:3857' })
    const lengthM = getLength(geometry, { projection: 'EPSG:3857' })
    return `面积: ${formatArea(areaM2)}\n周长: ${formatLength(lengthM)}`
  }
  return `几何类型: ${geometryType}`
}

function showFeaturePopup(feature, coordinate) {
  const geometry = feature.getGeometry()
  popupTitle.value = String(feature.get('featureName') || feature.get('name') || 'KML要素')
  popupContent.value = [
    `来源: ${String(feature.get('sourceName') || '-')}`,
    geometrySummaryText(geometry)
  ].join('\n')
  popupVisible.value = true
  if (popupOverlayRef.value) {
    popupOverlayRef.value.setPosition(coordinate)
  }
}

function closeFeaturePopup() {
  popupVisible.value = false
  if (popupOverlayRef.value) {
    popupOverlayRef.value.setPosition(undefined)
  }
}

onMounted(() => {
  const imgLayers = createTiandituLayerGroup('img')
  const vecLayers = createTiandituLayerGroup('vec')
  const terLayers = createTiandituLayerGroup('ter')
  ;[...vecLayers, ...terLayers].forEach((layer) => layer.setVisible(false))

  const kmlLayer = new VectorLayer({
    source: kmlSource,
    style: (feature) => kmlStyleByIndex(Number(feature.get('kmlColorIndex') || 0))
  })
  const heritageLayer = new VectorLayer({ source: heritageSource })
  const conflictLayer = new VectorLayer({ source: conflictSource })
  const overlapLayer = new VectorLayer({ source: overlapSource })
  const measureLayer = new VectorLayer({ source: measureSource })

  const popupOverlay = new Overlay({
    element: featurePopupEl.value,
    autoPan: {
      animation: {
        duration: 180
      }
    },
    positioning: 'bottom-center',
    offset: [0, -12],
    stopEvent: false
  })

  const map = new OlMap({
    target: mapEl.value,
    overlays: [popupOverlay],
    layers: [
      ...imgLayers,
      ...vecLayers,
      ...terLayers,
      kmlLayer,
      heritageLayer,
      conflictLayer,
      overlapLayer,
      measureLayer
    ],
    view: new View({
      center: fromLonLat([90.21, 42.84]),
      zoom: 9
    })
  })

  map.on('click', (evt) => {
    const feature = map.forEachFeatureAtPixel(evt.pixel, (item) => item)
    if (feature && Number.isInteger(feature.get('overlapIndex'))) {
      const idx = feature.get('overlapIndex')
      if (idx >= 0 && idx < overlapEntries.value.length) {
        emit('overlap-click', overlapEntries.value[idx])
      }
      return
    }
    if (feature && feature.get('isHeritage')) {
      return
    }
    if (feature && feature.get('isKmlFeature')) {
      showFeaturePopup(feature, evt.coordinate)
      return
    }
    if (feature && feature.get('site_id')) {
      closeFeaturePopup()
      emit('conflict-click', {
        site_id: feature.get('site_id'),
        site_name: feature.get('site_name'),
        feature_source: feature.get('sourceName'),
        relation: feature.get('relation'),
        distance_m: feature.get('distance_m')
      })
      return
    }
    closeFeaturePopup()
    if (!measureMode.value) {
      return
    }
    handleMeasureClick(evt.coordinate)
  })

  mapRef.value = map
  kmlLayerRef.value = kmlLayer
  heritageLayerRef.value = heritageLayer
  conflictLayerRef.value = conflictLayer
  overlapLayerRef.value = overlapLayer
  measureLayerRef.value = measureLayer
  baseLayersRef.value = {
    img: imgLayers,
    vec: vecLayers,
    ter: terLayers
  }
  popupOverlayRef.value = popupOverlay

  // 初始化时按开关状态显式设置，避免图层状态与按钮状态不一致。
  kmlLayer.setVisible(showKmlLayer.value)
  heritageLayer.setVisible(showHeritageLayer.value)
  conflictLayer.setVisible(showConflictLayer.value)
  overlapLayer.setVisible(showOverlapLayer.value)

  loadHeritageLayer()
})

watch(
  () => props.selectedRecords,
  () => {
    reloadKmlLayers()
  },
  { deep: true }
)

watch(
  () => props.conflictRows,
  () => {
    reloadConflictLayer()
  },
  { deep: true }
)

watch(
  () => props.focusConflict,
  (value) => {
    applyFocusConflictStyle()
    focusConflictOnMap(value)
  },
  { deep: true }
)

watch(
  () => props.focusOverlap,
  (value) => {
    focusOverlapOnMap(value)
  },
  { deep: true }
)
</script>

<style scoped>
.kml-overlay-map-wrap {
  position: relative;
}

.kml-overlay-map {
  width: 100%;
  height: 520px;
  border-radius: 10px;
  overflow: hidden;
}

.kml-loading-mask {
  position: absolute;
  inset: 0;
  z-index: 7;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(1px);
}

.kml-loading-card {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #0f172a;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.2);
}

.kml-loading-spinner {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid #dbeafe;
  border-top-color: #2563eb;
  animation: kml-spin 0.72s linear infinite;
}

@keyframes kml-spin {
  to {
    transform: rotate(360deg);
  }
}

.kml-feature-popup {
  min-width: 220px;
  max-width: 320px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 8px 10px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.22);
  color: #0f172a;
  font-size: 12px;
  display: none;
}

.kml-feature-popup.is-visible {
  display: block;
}

.kml-feature-popup h4 {
  margin: 0 0 6px;
  font-size: 13px;
}

.kml-feature-popup-content {
  white-space: pre-line;
  line-height: 1.5;
  color: #334155;
}

.kml-overlay-tip {
  position: absolute;
  left: 12px;
  bottom: 12px;
  max-width: min(520px, calc(100% - 24px));
  background: rgba(15, 23, 42, 0.82);
  color: #f8fafc;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.45;
}

.kml-overlay-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 6;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.16);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toolbar-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.toolbar-label {
  font-size: 12px;
  color: #334155;
  min-width: 32px;
}

.toolbar-btn {
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: #fff;
  color: #1e293b;
  font-size: 12px;
  line-height: 1;
  padding: 6px 8px;
  cursor: pointer;
}

.toolbar-select {
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: #fff;
  color: #1e293b;
  font-size: 12px;
  line-height: 1;
  padding: 5px 6px;
  max-width: 170px;
}

.toolbar-btn.active {
  border-color: #1d4ed8;
  background: #dbeafe;
  color: #1e40af;
}

.measure-text {
  font-size: 12px;
  color: #0f172a;
}
</style>

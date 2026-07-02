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
    <div class="kml-legend-panel">
      <div class="legend-title">图例</div>
      <div class="legend-item">
        <span class="legend-swatch swatch-kml"></span>
        <span>普通 KML 要素</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch swatch-overlap"></span>
        <span>元素间叠加冲突</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch swatch-heritage"></span>
        <span>元素与文物点冲突</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch swatch-both"></span>
        <span>双重冲突（优先关注）</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch swatch-hatch"></span>
        <span>叠加面斜线阴影</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot dot-heritage"></span>
        <span>文物点</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot dot-conflict"></span>
        <span>冲突点</span>
      </div>
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
import MultiLineString from 'ol/geom/MultiLineString'
import Point from 'ol/geom/Point'
import Polygon from 'ol/geom/Polygon'
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
const OVERLAP_DETECT_LIMIT = 2500
const POINT_RENDER_LIMIT = 1200
const kmlFormat = new KML({ extractStyles: false })

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
const hatchPatternCache = new Map()

function kmlBaseColorByIndex(index) {
  // 使用黄金角生成高区分度色相，避免批量加载时颜色过于相近。
  const hue = Math.round((index * 137.508) % 360)
  const lightness = [46, 58, 40, 64][index % 4]
  return {
    stroke: `hsl(${hue} 82% ${lightness}%)`,
    fill: `hsl(${hue} 82% ${lightness}% / 0.2)`,
    point: `hsl(${hue} 85% ${Math.max(32, lightness - 8)}%)`
  }
}

function buildHatchPattern(patternKey, lineColor, backgroundColor) {
  if (hatchPatternCache.has(patternKey)) {
    return hatchPatternCache.get(patternKey)
  }
  if (typeof document === 'undefined') {
    return backgroundColor
  }

  const canvas = document.createElement('canvas')
  canvas.width = 12
  canvas.height = 12
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return backgroundColor
  }

  ctx.fillStyle = backgroundColor
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.strokeStyle = lineColor
  ctx.lineWidth = 1.4
  ctx.beginPath()
  ctx.moveTo(-2, 10)
  ctx.lineTo(10, -2)
  ctx.moveTo(2, 14)
  ctx.lineTo(14, 2)
  ctx.stroke()

  const pattern = ctx.createPattern(canvas, 'repeat') || backgroundColor
  hatchPatternCache.set(patternKey, pattern)
  return pattern
}

function kmlStyleByFeature(feature) {
  const index = Number(feature.get('kmlColorIndex') || 0)
  const geometryType = String(feature.getGeometry()?.getType?.() || '')
  const isOverlapConflict = Boolean(feature.get('isOverlapConflict'))
  const isHeritageConflict = Boolean(feature.get('isHeritageConflict'))

  const state = isOverlapConflict && isHeritageConflict ? 'both' : isOverlapConflict ? 'overlap' : isHeritageConflict ? 'heritage' : 'base'
  const cacheKey = `${index}|${state}|${geometryType}`
  if (kmlStyleCache.has(cacheKey)) {
    return kmlStyleCache.get(cacheKey)
  }

  const baseColor = kmlBaseColorByIndex(index)
  const overlapColor = '#d900ff'
  const heritageColor = '#ff6a00'
  const bothColor = '#ff1744'
  const highlightStroke =
    state === 'both' ? bothColor : state === 'overlap' ? overlapColor : state === 'heritage' ? heritageColor : baseColor.stroke
  const highlightFill =
    state === 'both'
      ? 'rgba(255, 23, 68, 0.2)'
      : state === 'overlap'
        ? 'rgba(217, 0, 255, 0.2)'
        : state === 'heritage'
          ? 'rgba(255, 106, 0, 0.18)'
          : baseColor.fill
  const strokeWidth = state === 'base' ? 2 : 3

  const isPolygon = geometryType === 'Polygon' || geometryType === 'MultiPolygon'
  const isPoint = geometryType === 'Point' || geometryType === 'MultiPoint'

  const fillColor =
    isPolygon && (state === 'overlap' || state === 'both')
      ? buildHatchPattern(`hatch:${state}:${highlightStroke}`, highlightStroke, 'rgba(255, 255, 255, 0.06)')
      : highlightFill
  const safeFillColor = fillColor || 'rgba(59, 130, 246, 0.18)'

  const style = new Style({
    image: new CircleStyle({
      radius: isPoint && state !== 'base' ? 6.5 : 5,
      fill: new Fill({ color: state === 'base' ? baseColor.point : highlightStroke }),
      stroke: new Stroke({ color: '#ffffff', width: state === 'base' ? 1.5 : 2.4 })
    }),
    stroke: new Stroke({
      color: highlightStroke,
      width: strokeWidth,
      lineDash: state === 'overlap' ? [8, 5] : undefined
    }),
    fill: new Fill({ color: safeFillColor })
  })
  kmlStyleCache.set(cacheKey, style)
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
  const color = kind === 'point' ? '#d900ff' : kind === 'line' ? '#ff6a00' : '#ff1744'
  return new Style({
    image: new CircleStyle({
      radius: 7,
      fill: new Fill({ color }),
      stroke: new Stroke({ color: '#ffffff', width: 2.2 })
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

function appendTipOnce(message) {
  if (!message) {
    return
  }
  if (!tips.value.includes(message)) {
    tips.value.push(message)
  }
}

function isPointGeometryType(type) {
  return type === 'Point' || type === 'MultiPoint'
}

function isLinearOrAreaGeometryType(type) {
  return (
    type === 'LineString' ||
    type === 'MultiLineString' ||
    type === 'Polygon' ||
    type === 'MultiPolygon'
  )
}

function chooseRenderPerfLevel(featureCount, fileCount) {
  if (featureCount > 12000 || fileCount >= 8) {
    return 3
  }
  if (featureCount > 5000 || fileCount >= 4) {
    return 2
  }
  if (featureCount > 2000) {
    return 1
  }
  return 0
}

function simplifyToleranceByLevel(level) {
  if (level >= 3) {
    return 4
  }
  if (level >= 2) {
    return 2
  }
  if (level >= 1) {
    return 0.8
  }
  return 0
}

function optimizeFeaturesForRender(features = [], fileCount = 1) {
  const perfLevel = chooseRenderPerfLevel(features.length, fileCount)
  const tolerance = simplifyToleranceByLevel(perfLevel)
  const pointFeatures = []
  const nonPointFeatures = []

  features.forEach((feature) => {
    const geometry = feature?.getGeometry?.()
    const geometryType = geometry?.getType?.() || ''

    if (isPointGeometryType(geometryType)) {
      pointFeatures.push(feature)
      return
    }

    if (tolerance > 0 && geometry && isLinearOrAreaGeometryType(geometryType)) {
      try {
        const simplified = geometry.simplify(tolerance)
        if (simplified) {
          nonPointFeatures.push(cloneKmlFeatureWithGeometry(feature, simplified))
          return
        }
      } catch (_error) {
        // 简化失败时回退原始几何，避免中断渲染。
      }
    }

    nonPointFeatures.push(feature)
  })

  if (pointFeatures.length <= POINT_RENDER_LIMIT || perfLevel === 0) {
    return {
      features: [...nonPointFeatures, ...pointFeatures],
      perfLevel,
      hiddenPointCount: 0,
      simplifiedTolerance: tolerance,
    }
  }

  const step = Math.max(1, Math.ceil(pointFeatures.length / POINT_RENDER_LIMIT))
  const sampledPoints = pointFeatures.filter((_, idx) => idx % step === 0)

  return {
    features: [...nonPointFeatures, ...sampledPoints],
    perfLevel,
    hiddenPointCount: Math.max(0, pointFeatures.length - sampledPoints.length),
    simplifiedTolerance: tolerance,
  }
}

function cloneKmlFeatureWithGeometry(feature, geometry) {
  const cloned = feature.clone()
  cloned.setGeometry(geometry)
  return cloned
}

function isClosedRingCoordinates(coords, thresholdM = 1) {
  if (!Array.isArray(coords) || coords.length < 3) {
    return false
  }
  const first = coords[0]
  const last = coords[coords.length - 1]
  if (!first || !last || first.length < 2 || last.length < 2) {
    return false
  }
  return distanceInMetersBy3857(first, last) <= thresholdM
}

function closeRingCoordinates(coords) {
  if (!Array.isArray(coords) || coords.length < 3) {
    return []
  }
  const first = coords[0]
  const last = coords[coords.length - 1]
  if (!first || !last) {
    return []
  }
  if (distanceInMetersBy3857(first, last) <= 1) {
    return coords
  }
  return [...coords, first.slice()]
}

function convertClosedLinesToPolygonFeatures(features = []) {
  const converted = []
  for (const feature of features) {
    const geometry = feature?.getGeometry?.()
    if (!geometry) {
      continue
    }

    const geometryType = geometry.getType()
    if (geometryType === 'LineString') {
      const coords = geometry.getCoordinates()
      if (isClosedRingCoordinates(coords, 200)) {
        const closed = closeRingCoordinates(coords)
        converted.push(cloneKmlFeatureWithGeometry(feature, new Polygon([closed])))
        continue
      }
      converted.push(feature)
      continue
    }

    if (geometryType === 'MultiLineString') {
      const lines = geometry.getCoordinates()
      const remainLines = []

      lines.forEach((line) => {
        if (isClosedRingCoordinates(line, 200)) {
          const polygonFeature = cloneKmlFeatureWithGeometry(feature, new Polygon([closeRingCoordinates(line)]))
          converted.push(polygonFeature)
        } else {
          remainLines.push(line)
        }
      })

      if (remainLines.length > 0) {
        const lineGeometry =
          remainLines.length === 1 ? new LineString(remainLines[0]) : new MultiLineString(remainLines)
        const lineFeature = cloneKmlFeatureWithGeometry(feature, lineGeometry)
        converted.push(lineFeature)
      }
      continue
    }

    converted.push(feature)
  }
  return converted
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
      const features = kmlFormat.readFeatures(item.text, {
        dataProjection: 'EPSG:4326',
        featureProjection: 'EPSG:3857'
      })
      const renderFeatures = convertClosedLinesToPolygonFeatures(features)
      renderFeatures.forEach((feature, featureIndex) => {
        feature.set('isKmlFeature', true)
        feature.set('kmlColorIndex', item.idx)
        feature.set('sourceName', item.title)
        feature.set('featureName', String(feature.get('name') || `要素#${featureIndex + 1}`))
      })
      const optimized = optimizeFeaturesForRender(renderFeatures, selectedRecords.length)
      kmlSource.addFeatures(optimized.features)
      if (optimized.hiddenPointCount > 0) {
        appendTipOnce(
          `性能模式已开启：自动抽稀点注记 ${optimized.hiddenPointCount} 个，以提升批量渲染速度。`
        )
      }
      if (optimized.simplifiedTolerance > 0) {
        appendTipOnce(
          `性能模式已开启：线/面要素已做几何简化（容差 ${optimized.simplifiedTolerance}m）。`
        )
      }
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
  applyKmlHighlightStates()
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

function applyKmlHighlightStates(entries = overlapEntries.value) {
  const overlapFeatureKeySet = new Set()
  ;(entries || []).forEach((row) => {
    const sourceA = String(row?.source_a || '')
    const sourceB = String(row?.source_b || '')
    const featureA = String(row?.feature_a || '')
    const featureB = String(row?.feature_b || '')
    if (sourceA && featureA) {
      overlapFeatureKeySet.add(`${sourceA}|${featureA}`)
    }
    if (sourceB && featureB) {
      overlapFeatureKeySet.add(`${sourceB}|${featureB}`)
    }
  })

  const conflictSourceSet = new Set(
    (props.conflictRows || [])
      .map((row) => String(row?.feature_source || '').trim())
      .filter((name) => Boolean(name))
  )

  kmlSource.getFeatures().forEach((feature) => {
    const sourceName = String(feature.get('sourceName') || '')
    const featureName = String(feature.get('featureName') || '')
    const overlapFlag = overlapFeatureKeySet.has(`${sourceName}|${featureName}`)
    const heritageConflictFlag = conflictSourceSet.has(sourceName)
    feature.set('isOverlapConflict', overlapFlag)
    feature.set('isHeritageConflict', heritageConflictFlag)
  })

  if (kmlLayerRef.value) {
    kmlLayerRef.value.changed()
  }
}

async function reloadOverlapLayer() {
  overlapToken += 1
  const currentToken = overlapToken
  overlapSource.clear()
  overlapEntries.value = []

  const features = kmlSource.getFeatures()
  if (!features || features.length < 2) {
    applyKmlHighlightStates([])
    emit('overlap-update', [])
    return
  }
  if (features.length > OVERLAP_DETECT_LIMIT) {
    appendTipOnce(
      `当前渲染要素 ${features.length} 个，已跳过叠加检测以避免页面卡顿（阈值 ${OVERLAP_DETECT_LIMIT}）。`
    )
    applyKmlHighlightStates([])
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
  applyKmlHighlightStates(entries)
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
    measureText.value = measurePoints.length > 1 ? `${measureText.value}（已结束）` : ''
    return
  }
  measureText.value = '测距已开启：单击添加节点，双击结束当前测距'
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

  measureSource.clear()
  measurePoints.forEach((point) => {
    const pointFeature = new Feature({ geometry: new Point(point) })
    pointFeature.setStyle(measurePointStyle())
    measureSource.addFeature(pointFeature)
  })

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
    const prev = toLonLat(measurePoints[measurePoints.length - 2])
    const curr = toLonLat(measurePoints[measurePoints.length - 1])
    const latest = haversineMeters(prev, curr)
    measureText.value = `总距离：${formatDistance(total)}；本段：${formatDistance(latest)}（双击结束）`
  } else {
    measureText.value = '已设置起点，点击地图继续测距'
  }
}

function finishMeasure() {
  if (!measureMode.value) {
    return
  }
  if (measurePoints.length >= 2) {
    measureMode.value = false
    measureText.value = `${measureText.value}（已结束）`
    return
  }
  measureText.value = '至少需要两个点才能形成测距线'
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

function showHeritagePointPopup(feature, coordinate) {
  const geometry = feature.getGeometry()
  popupTitle.value = String(feature.get('site_name') || '文物点')
  popupContent.value = [
    `文物ID: ${String(feature.get('site_id') || '-')}`,
    `级别: ${String(feature.get('site_level') || '-')}`,
    geometrySummaryText(geometry)
  ].join('\n')
  popupVisible.value = true
  if (popupOverlayRef.value) {
    popupOverlayRef.value.setPosition(coordinate)
  }
}

function showConflictPointPopup(feature, coordinate) {
  const geometry = feature.getGeometry()
  const distanceM = Number(feature.get('distance_m'))
  popupTitle.value = String(feature.get('site_name') || '冲突文物点')
  popupContent.value = [
    `文物ID: ${String(feature.get('site_id') || '-')}`,
    `来源文件: ${String(feature.get('sourceName') || '-')}`,
    `冲突关系: ${String(feature.get('relation') || '-')}`,
    `距离: ${Number.isFinite(distanceM) ? `${distanceM.toFixed(2)} m` : '-'}`,
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
    style: (feature) => kmlStyleByFeature(feature)
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
    if (measureMode.value) {
      closeFeaturePopup()
      handleMeasureClick(evt.coordinate)
      return
    }

    const feature = map.forEachFeatureAtPixel(evt.pixel, (item) => item)
    if (feature && Number.isInteger(feature.get('overlapIndex'))) {
      const idx = feature.get('overlapIndex')
      if (idx >= 0 && idx < overlapEntries.value.length) {
        emit('overlap-click', overlapEntries.value[idx])
      }
      return
    }
    if (feature && feature.get('isHeritage')) {
      showHeritagePointPopup(feature, evt.coordinate)
      return
    }
    if (feature && feature.get('isKmlFeature')) {
      showFeaturePopup(feature, evt.coordinate)
      return
    }
    if (feature && feature.get('site_id')) {
      showConflictPointPopup(feature, evt.coordinate)
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
  })

  map.on('dblclick', (evt) => {
    if (!measureMode.value) {
      return
    }
    evt.preventDefault()
    finishMeasure()
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
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.84) 0%, rgba(30, 41, 59, 0.8) 100%);
  color: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 10px;
  padding: 9px 11px;
  font-size: 12px;
  line-height: 1.45;
  backdrop-filter: blur(4px);
}

.kml-overlay-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 6;
  background: linear-gradient(165deg, rgba(255, 255, 255, 0.88) 0%, rgba(241, 245, 249, 0.84) 100%);
  border: 1px solid rgba(148, 163, 184, 0.34);
  border-radius: 12px;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.18);
  padding: 11px;
  display: flex;
  flex-direction: column;
  gap: 9px;
  backdrop-filter: blur(8px);
}

.toolbar-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.toolbar-label {
  font-size: 12px;
  color: #0f172a;
  min-width: 34px;
  font-weight: 600;
}

.toolbar-btn {
  border: 1px solid rgba(148, 163, 184, 0.55);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  color: #0f172a;
  font-size: 12px;
  line-height: 1;
  padding: 6px 9px;
  cursor: pointer;
  transition: all 180ms ease;
}

.toolbar-btn:hover {
  border-color: rgba(2, 132, 199, 0.6);
  color: #0369a1;
  transform: translateY(-1px);
}

.toolbar-select {
  border: 1px solid rgba(148, 163, 184, 0.55);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  color: #0f172a;
  font-size: 12px;
  line-height: 1;
  padding: 5px 6px;
  max-width: 170px;
}

.toolbar-btn.active {
  border-color: rgba(2, 132, 199, 0.7);
  background: linear-gradient(135deg, rgba(224, 242, 254, 0.96) 0%, rgba(219, 234, 254, 0.94) 100%);
  color: #0c4a6e;
}

.measure-text {
  font-size: 12px;
  color: #0f172a;
  font-weight: 600;
}

.kml-legend-panel {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 6;
  min-width: 196px;
  max-width: 250px;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.9) 0%, rgba(241, 245, 249, 0.9) 100%);
  border: 1px solid rgba(148, 163, 184, 0.34);
  border-radius: 12px;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.18);
  padding: 10px 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  backdrop-filter: blur(8px);
}

.legend-title {
  font-size: 12px;
  color: #0f172a;
  font-weight: 600;
  margin-bottom: 2px;
  letter-spacing: 0.2px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #1e293b;
  line-height: 1.2;
}

.legend-swatch {
  width: 20px;
  height: 12px;
  border-radius: 3px;
  border: 2px solid transparent;
  flex: none;
}

.swatch-kml {
  border-color: #0ea5e9;
  background: rgba(14, 165, 233, 0.18);
}

.swatch-overlap {
  border-color: #d900ff;
  background: rgba(217, 0, 255, 0.18);
}

.swatch-heritage {
  border-color: #ff6a00;
  background: rgba(255, 106, 0, 0.18);
}

.swatch-both {
  border-color: #ff1744;
  background: rgba(255, 23, 68, 0.2);
}

.swatch-hatch {
  border-color: #d900ff;
  background-image: repeating-linear-gradient(
    135deg,
    rgba(217, 0, 255, 0.85) 0,
    rgba(217, 0, 255, 0.85) 2px,
    rgba(255, 255, 255, 0) 2px,
    rgba(255, 255, 255, 0) 6px
  );
  background-color: rgba(255, 255, 255, 0.72);
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #ffffff;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.18);
  flex: none;
}

.dot-heritage {
  background: #2563eb;
}

.dot-conflict {
  background: #dc2626;
}

@media (max-width: 768px) {
  .kml-legend-panel {
    right: 10px;
    bottom: 10px;
    min-width: 168px;
    max-width: 188px;
    padding: 8px;
    gap: 6px;
  }

  .legend-item {
    font-size: 11px;
    gap: 6px;
  }

  .legend-swatch {
    width: 18px;
    height: 10px;
  }
}
</style>

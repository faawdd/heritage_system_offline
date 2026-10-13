<template>
  <section class="heritage-fullscreen-page">
    <HeritageMapCanvas
      ref="mapCanvasRef"
      class="heritage-fullscreen-map"
      :points="points"
      :active-levels="activeLevels"
      :keyword="keyword"
      :show-point-popup="true"
      :enable-map-tools="true"
      @open-detail="openDetail"
    />

    <!-- 菜单收起时的轻量唤起按钮 -->
    <transition name="fade">
      <button
        v-if="!menuVisible"
        type="button"
        class="heritage-mini-toggle-btn"
        @click="menuVisible = true"
        title="展开检索与筛选"
      >
        <span class="mini-toggle-icon">🔍</span>
        <span class="mini-toggle-text">检索与筛选</span>
        <span class="mini-toggle-badge">{{ filteredPoints.length }}</span>
      </button>
    </transition>

    <!-- 展开时的轻量悬浮菜单 -->
    <transition name="slide-fade">
      <aside v-show="menuVisible" class="heritage-floating-menu">
        <div class="heritage-menu-header">
          <div class="menu-header-title">
            <h3>文物检索与筛选</h3>
            <span class="menu-header-badge">共 {{ points.length }} 处</span>
          </div>
          <div class="menu-header-actions">
            <button
              type="button"
              class="menu-icon-btn"
              :class="{ 'is-loading': loading }"
              :disabled="loading"
              title="刷新点位数据"
              @click="loadData"
            >
              ↺
            </button>
            <button
              type="button"
              class="menu-icon-btn"
              title="收起菜单"
              @click="menuVisible = false"
            >
              ✕
            </button>
          </div>
        </div>

        <div class="heritage-menu-body">
          <div class="heritage-search-row">
            <el-input
              v-model="keyword"
              placeholder="搜索文物名称..."
              clearable
              size="default"
            >
              <template #prefix>
                <span class="search-input-prefix">🔍</span>
              </template>
            </el-input>
          </div>

          <div class="heritage-filter-section">
            <div class="section-title-bar">
              <span class="section-label">文物级别</span>
              <button
                type="button"
                class="section-link-btn"
                @click="toggleSelectAllLevels"
              >
                {{ isAllLevelsSelected ? '清空' : '全选' }}
              </button>
            </div>
            <div class="level-chips-grid">
              <button
                v-for="item in levelOptions"
                :key="item.key"
                type="button"
                class="level-chip-btn"
                :class="{ active: activeLevels.includes(item.key) }"
                @click="toggleLevel(item.key)"
              >
                <span class="chip-color-dot" :style="{ backgroundColor: item.color }"></span>
                <span class="chip-label">{{ item.label }}</span>
                <span class="chip-count">{{ getLevelCount(item.key) }}</span>
              </button>
            </div>
          </div>

          <!-- 搜索匹配结果（输入关键字时展示） -->
          <div v-if="keyword.trim()" class="heritage-results-section">
            <div class="section-title-bar">
              <span class="section-label">匹配文物 ({{ filteredPoints.length }})</span>
            </div>
            <el-scrollbar max-height="200px" class="results-scrollbar">
              <div class="results-list">
                <button
                  v-for="item in filteredPoints.slice(0, 50)"
                  :key="item.id"
                  type="button"
                  class="result-item-btn"
                  @click="focusPointOnMap(item)"
                >
                  <span
                    class="result-item-dot"
                    :style="{ backgroundColor: levelColors[item.level] || '#457b9d' }"
                  ></span>
                  <span class="result-item-name" :title="item.name">{{ item.name }}</span>
                  <span class="result-item-level">{{ item.level_label || '未定级' }}</span>
                </button>
                <div v-if="filteredPoints.length === 0" class="results-empty">
                  无匹配文物
                </div>
                <div v-else-if="filteredPoints.length > 50" class="results-overflow-tip">
                  仅展示前 50 条，请细化检索关键词
                </div>
              </div>
            </el-scrollbar>
          </div>
        </div>

        <div class="heritage-menu-footer">
          <span class="footer-count">已展示 <strong>{{ filteredPoints.length }}</strong> / 共 {{ points.length }} 处</span>
          <button
            v-if="hasFilters"
            type="button"
            class="footer-reset-btn"
            @click="resetFilters"
          >
            重置
          </button>
        </div>
      </aside>
    </transition>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchHeritageMapPoints } from '../../api/heritageApi'
import HeritageMapCanvas from '../../components/heritage/HeritageMapCanvas.vue'

const mapCanvasRef = ref(null)
const loading = ref(false)
const keyword = ref('')
const points = ref([])
const activeLevels = ref(['GB', 'SB', 'XB', 'DS'])
const menuVisible = ref(true)

const levelOptions = [
  { key: 'GB', label: '全国重点', color: '#e63946' },
  { key: 'SB', label: '省级', color: '#f4a261' },
  { key: 'XB', label: '市县级', color: '#2a9d8f' },
  { key: 'DS', label: '尚未定级', color: '#457b9d' }
]

const levelColors = {
  GB: '#e63946',
  SB: '#f4a261',
  XB: '#2a9d8f',
  DS: '#457b9d'
}

const allLevelKeys = ['GB', 'SB', 'XB', 'DS']

const isAllLevelsSelected = computed(() => {
  return allLevelKeys.every((key) => activeLevels.value.includes(key))
})

const hasFilters = computed(() => {
  return Boolean(keyword.value.trim()) || activeLevels.value.length !== allLevelKeys.length
})

const filteredPoints = computed(() => {
  const activeSet = new Set(activeLevels.value || [])
  const kw = (keyword.value || '').trim().toLowerCase()
  return (points.value || []).filter((item) => {
    if (activeSet.size && !activeSet.has(item.level)) {
      return false
    }
    if (kw && !String(item.name || '').toLowerCase().includes(kw)) {
      return false
    }
    return true
  })
})

function getLevelCount(key) {
  return (points.value || []).filter((item) => item.level === key).length
}

function toggleLevel(key) {
  const idx = activeLevels.value.indexOf(key)
  if (idx > -1) {
    activeLevels.value.splice(idx, 1)
  } else {
    activeLevels.value.push(key)
  }
}

function toggleSelectAllLevels() {
  if (isAllLevelsSelected.value) {
    activeLevels.value = []
  } else {
    activeLevels.value = [...allLevelKeys]
  }
}

function resetFilters() {
  keyword.value = ''
  activeLevels.value = [...allLevelKeys]
}

function focusPointOnMap(item) {
  mapCanvasRef.value?.focusPoint?.(item)
}

function openDetail(payload) {
  if (!payload?.id || !payload.preview_url) {
    return
  }
  window.open(payload.preview_url, '_blank', 'noopener,noreferrer')
}

async function loadData() {
  loading.value = true
  try {
    const result = await fetchHeritageMapPoints()
    if (!result.success) {
      throw new Error(result.message || '加载点位失败')
    }
    points.value = result.rows || []
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

loadData()
</script>

<style scoped>
.heritage-fullscreen-page {
  position: relative;
  height: 100dvh;
  min-height: 100dvh;
  background: var(--bg);
  overflow: hidden;
}

.heritage-fullscreen-map {
  height: 100%;
  border-radius: 0;
}

/* 确保在全屏一张图页面中，右上角工具栏位于用户面板下方，不发生重叠 */
.heritage-fullscreen-page :deep(.heritage-map-control-group),
.heritage-fullscreen-page :deep(.heritage-map-tools) {
  top: 72px;
  right: 16px;
  z-index: 14;
}

/* 收起时的轻量唤起按钮 */
.heritage-mini-toggle-btn {
  position: absolute;
  left: 16px;
  top: 16px;
  z-index: 20;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.14);
  backdrop-filter: blur(12px);
  color: var(--text);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.heritage-mini-toggle-btn:hover {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--surface) 98%, transparent);
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.18);
  transform: translateY(-1px);
}

.mini-toggle-icon {
  font-size: 14px;
}

.mini-toggle-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: color-mix(in srgb, #0ea5e9 14%, var(--surface));
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
}

/* 展开时的轻量悬浮菜单 */
.heritage-floating-menu {
  position: absolute;
  left: 16px;
  top: 16px;
  width: 300px;
  max-width: calc(100vw - 32px);
  max-height: calc(100dvh - 32px);
  z-index: 20;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--surface) 95%, transparent);
  box-shadow: 0 12px 36px rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(14px);
  overflow: hidden;
}

.heritage-menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
}

.menu-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.menu-header-title h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  line-height: 1;
}

.menu-header-badge {
  padding: 2px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--text) 8%, transparent);
  color: var(--muted);
  font-size: 11px;
  font-weight: 500;
}

.menu-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.menu-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 14px;
  transition: all 0.15s ease;
}

.menu-icon-btn:hover {
  background: color-mix(in srgb, var(--surface) 80%, var(--bg));
  border-color: var(--line);
  color: var(--text);
}

.menu-icon-btn.is-loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.heritage-menu-body {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.heritage-search-row {
  width: 100%;
}

.search-input-prefix {
  font-size: 13px;
  opacity: 0.7;
}

.heritage-filter-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
}

.section-link-btn {
  border: none;
  background: none;
  padding: 0;
  color: var(--accent);
  font-size: 12px;
  cursor: pointer;
}

.section-link-btn:hover {
  text-decoration: underline;
}

.level-chips-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.level-chip-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: color-mix(in srgb, var(--surface) 90%, var(--bg));
  color: var(--muted);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  transition: all 0.15s ease;
  user-select: none;
}

.level-chip-btn:hover {
  border-color: color-mix(in srgb, var(--accent) 50%, var(--line));
  color: var(--text);
}

.level-chip-btn.active {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, var(--surface));
  color: var(--text);
  font-weight: 600;
}

.chip-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chip-label {
  flex: 1;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chip-count {
  font-size: 11px;
  opacity: 0.75;
}

/* 结果列表 */
.heritage-results-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-top: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
  padding-top: 10px;
}

.results-scrollbar {
  max-height: 200px;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-right: 4px;
}

.result-item-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: background 0.12s ease;
}

.result-item-btn:hover {
  background: color-mix(in srgb, var(--surface) 80%, var(--bg));
  border-color: var(--line);
}

.result-item-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.result-item-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-item-level {
  font-size: 11px;
  color: var(--muted);
  flex-shrink: 0;
}

.results-empty {
  padding: 12px 0;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}

.results-overflow-tip {
  padding: 4px 8px;
  text-align: center;
  font-size: 11px;
  color: var(--muted);
}

.heritage-menu-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-top: 1px solid var(--line);
  background: color-mix(in srgb, var(--surface) 60%, var(--bg));
  font-size: 12px;
  color: var(--muted);
}

.heritage-menu-footer strong {
  color: var(--text);
}

.footer-reset-btn {
  border: none;
  background: none;
  padding: 0;
  color: var(--accent);
  font-size: 12px;
  cursor: pointer;
}

.footer-reset-btn:hover {
  text-decoration: underline;
}

/* 动效 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-fade-enter-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-fade-leave-active {
  transition: all 0.15s cubic-bezier(0.4, 0, 1, 1);
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateY(-8px) scale(0.97);
  opacity: 0;
}

@media (max-width: 1024px) {
  .heritage-fullscreen-page {
    height: 100dvh;
    min-height: 100dvh;
  }

  .heritage-floating-menu {
    top: 58px;
    left: 10px;
    right: 10px;
    width: auto;
    max-height: calc(100dvh - 70px);
  }

  .heritage-mini-toggle-btn {
    left: 10px;
    top: 10px;
  }
}
</style>

<template>
  <div class="app-shell" :class="{ 'is-sidebar-collapsed': isSidebarCollapsed }">
    <aside class="sidebar" :class="{ 'is-collapsed': isSidebarCollapsed }">
      <div class="brand-row">
        <div class="brand" :title="isSidebarCollapsed ? '鄯善县文物管理平台' : ''">
          {{ isSidebarCollapsed ? '文保' : '鄯善县文物管理平台' }}
        </div>
        <div class="header-actions" v-if="!isSidebarCollapsed">
          <el-button link type="info" class="collapse-btn" @click="toggleSidebar">折叠</el-button>
          <el-button link type="info" class="logout-btn" @click="logout">退出</el-button>
        </div>
      </div>

      <div class="sidebar-mini-actions" v-if="isSidebarCollapsed">
        <el-button link type="info" class="expand-btn" @click="toggleSidebar">展开</el-button>
      </div>

      <div class="collapsed-icon-nav" v-if="isSidebarCollapsed">
        <router-link
          v-for="group in collapsedShortcutGroups"
          :key="group.key"
          class="collapsed-icon-item"
          :class="{ active: group.active }"
          :to="group.to"
          :data-title="group.title"
        >
          <span class="menu-icon" :class="`menu-icon--${getGroupIconType(group.title)}`" aria-hidden="true">
            {{ getGroupIconLabel(group.title) }}
          </span>
        </router-link>
      </div>

      <div class="sidebar-group" v-for="group in menuGroups" :key="group.key" v-show="!isSidebarCollapsed">
        <button class="sidebar-group-title" type="button" @click="toggleGroup(group.key)">
          <span class="group-title-main">
            <span class="menu-icon" :class="`menu-icon--${getGroupIconType(group.title)}`" aria-hidden="true">
              {{ getGroupIconLabel(group.title) }}
            </span>
            <span>{{ group.title }}</span>
          </span>
          <span class="sidebar-group-arrow" :class="{ open: isGroupOpen(group.key) }">▾</span>
        </button>
        <div class="sidebar-submenu" v-show="isGroupOpen(group.key)">
          <router-link
            v-for="item in group.items"
            :key="item.to"
            class="nav-link nav-sublink"
            :to="item.to"
          >
            {{ item.label }}
          </router-link>
        </div>
      </div>

      <div class="sidebar-footer" :class="{ compact: isSidebarCollapsed }">
        <div class="theme-segmented" :class="{ compact: isSidebarCollapsed }" :title="`当前主题：${themeModeLabel}`" role="tablist" aria-label="主题模式">
          <button
            type="button"
            class="theme-segment"
            :class="{ active: themeMode === 'system' }"
            title="跟随系统"
            @click="setThemeMode('system')"
          >
            A
          </button>
          <button
            type="button"
            class="theme-segment"
            :class="{ active: themeMode === 'light' }"
            title="亮色主题"
            @click="setThemeMode('light')"
          >
            ☀
          </button>
          <button
            type="button"
            class="theme-segment"
            :class="{ active: themeMode === 'dark' }"
            title="暗色主题"
            @click="setThemeMode('dark')"
          >
            ☾
          </button>
        </div>
      </div>
    </aside>
    <main class="content" :class="{ 'content--fullscreen': isFullscreenRoute }">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/system/authStore'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const THEME_MODE_KEY = 'heritage_theme_mode'
const SIDEBAR_COLLAPSE_KEY = 'heritage_sidebar_collapsed'
const themeMode = ref('system')
const isSidebarCollapsed = ref(false)
let mediaQueryList = null

const staticMenuGroups = [
  {
    key: 'workspace',
    title: '工作台',
    items: [{ label: '综合看板', to: '/dashboard' }]
  },
  {
    key: 'heritage',
    title: '文物管理',
    items: [
      { label: '文物一张图', to: '/heritage/map' },
      { label: '文物统计', to: '/heritage/stats' },
      { label: '不可移动文物管理', to: '/heritage/immovable' },
      { label: '巡查记录', to: '/heritage/inspections' }
    ]
  },
  {
    key: 'projects',
    title: '项目管理',
    items: [
      { label: '项目列表', to: '/projects' },
      { label: '新建项目', to: '/projects/new' }
    ]
  },
  {
    key: 'gis',
    title: '地图工具',
    items: [
      { label: 'KML叠加检查', to: '/gis/kml-management' },
      { label: 'KML处理转换', to: '/gis/kml-process-convert' },
      { label: 'OVKML转换导入', to: '/gis/ovkml-convert' }
    ]
  },
  {
    key: 'system',
    title: '系统管理',
    items: [
      { label: '用户管理', to: '/system/users' },
      { label: '角色管理', to: '/system/roles' },
      { label: '菜单管理', to: '/system/menus' }
    ]
  }
]

function buildMenuGroupsFromTree(treeRows = []) {
  const rows = (treeRows || []).filter((item) => item.visible !== false)
  const groups = rows
    .map((group, index) => {
      const children = (group.children || [])
        .filter((child) => child.visible !== false && child.path)
        .map((child) => ({
          label: child.name,
          to: child.path.startsWith('/') ? child.path : `/${child.path}`
        }))

      return {
        key: `dynamic_${group.id || index}`,
        title: group.name || '菜单分组',
        items: children
      }
    })
    .filter((group) => group.items.length > 0)

  return groups
}

function ensureImmovableEntry(groups = []) {
  return groups.map((group) => {
    const title = (group.title || '').trim()
    if (title !== '文物管理') {
      return group
    }

    const hasEntry = (group.items || []).some((item) => item.to === '/heritage/immovable')
    if (hasEntry) {
      return group
    }

    return {
      ...group,
      items: [...(group.items || []), { label: '不可移动文物管理', to: '/heritage/immovable' }]
    }
  })
}

const menuGroups = computed(() => {
  const dynamic = buildMenuGroupsFromTree(authStore.menuTree)
  if (dynamic.length > 0) {
    return ensureImmovableEntry(dynamic)
  }
  return ensureImmovableEntry(staticMenuGroups)
})

const collapsedShortcutGroups = computed(() => {
  return menuGroups.value
    .filter((group) => Array.isArray(group.items) && group.items.length > 0)
    .map((group) => ({
      key: group.key,
      title: group.title,
      to: group.items[0].to,
      active: group.items.some((item) => route.path.startsWith(item.to))
    }))
})

const manuallyOpened = ref({})

const autoOpened = computed(() => {
  const state = {}
  menuGroups.value.forEach((group) => {
    state[group.key] = group.items.some((item) => route.path.startsWith(item.to))
  })
  return state
})

const fullscreenRoutePrefixes = ['/dashboard', '/heritage/map', '/gis/kml-management']

const isFullscreenRoute = computed(() => {
  return fullscreenRoutePrefixes.some((prefix) => route.path.startsWith(prefix))
})

const themeModeLabel = computed(() => {
  if (themeMode.value === 'dark') {
    return '暗色'
  }
  if (themeMode.value === 'light') {
    return '亮色'
  }
  return '跟随'
})

function getResolvedTheme(mode) {
  if (mode === 'dark' || mode === 'light') {
    return mode
  }
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  return 'light'
}

function applyTheme(mode) {
  const resolved = getResolvedTheme(mode)
  document.documentElement.setAttribute('data-theme', resolved)
}

function setThemeMode(mode) {
  if (!['system', 'light', 'dark'].includes(mode)) {
    return
  }
  themeMode.value = mode
}

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

function getGroupIconType(title = '') {
  const text = String(title || '').trim()
  if (text.includes('文物')) {
    return 'heritage'
  }
  if (text.includes('项目')) {
    return 'project'
  }
  if (text.toUpperCase().includes('GIS') || text.includes('地图')) {
    return 'gis'
  }
  if (text.includes('系统')) {
    return 'system'
  }
  if (text.includes('工作台')) {
    return 'workspace'
  }
  return 'default'
}

function getGroupIconLabel(title = '') {
  const type = getGroupIconType(title)
  if (type === 'heritage') {
    return '文'
  }
  if (type === 'project') {
    return '项'
  }
  if (type === 'gis') {
    return 'G'
  }
  if (type === 'system') {
    return '系'
  }
  if (type === 'workspace') {
    return '台'
  }
  return '•'
}

function handleSystemThemeChange() {
  if (themeMode.value === 'system') {
    applyTheme('system')
  }
}

function isGroupOpen(key) {
  if (Object.prototype.hasOwnProperty.call(manuallyOpened.value, key)) {
    return manuallyOpened.value[key]
  }
  return autoOpened.value[key]
}

function toggleGroup(key) {
  const current = isGroupOpen(key)
  manuallyOpened.value = {
    ...manuallyOpened.value,
    [key]: !current
  }
}

watch(
  () => themeMode.value,
  (value) => {
    localStorage.setItem(THEME_MODE_KEY, value)
    applyTheme(value)
  },
  { immediate: true }
)

watch(
  () => isSidebarCollapsed.value,
  (value) => {
    localStorage.setItem(SIDEBAR_COLLAPSE_KEY, value ? '1' : '0')
  },
  { immediate: false }
)

onMounted(() => {
  const savedMode = localStorage.getItem(THEME_MODE_KEY)
  if (savedMode === 'light' || savedMode === 'dark' || savedMode === 'system') {
    themeMode.value = savedMode
  }

  isSidebarCollapsed.value = localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === '1'

  mediaQueryList = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null
  if (mediaQueryList) {
    mediaQueryList.addEventListener('change', handleSystemThemeChange)
  }
})

onUnmounted(() => {
  if (mediaQueryList) {
    mediaQueryList.removeEventListener('change', handleSystemThemeChange)
  }
})

async function logout() {
  await authStore.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-row">
        <div class="brand">鄯善县文物管理平台</div>
        <el-button link type="info" class="logout-btn" @click="logout">退出</el-button>
      </div>

      <div class="sidebar-group" v-for="group in menuGroups" :key="group.key">
        <button class="sidebar-group-title" type="button" @click="toggleGroup(group.key)">
          <span>{{ group.title }}</span>
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
    </aside>
    <main class="content" :class="{ 'content--fullscreen': isFullscreenRoute }">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/system/authStore'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

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
      { label: 'KML管理', to: '/gis/kml-management' },
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

const manuallyOpened = ref({})

const autoOpened = computed(() => {
  const state = {}
  menuGroups.value.forEach((group) => {
    state[group.key] = group.items.some((item) => route.path.startsWith(item.to))
  })
  return state
})

const fullscreenRoutePrefixes = ['/heritage/map', '/gis/kml-management']

const isFullscreenRoute = computed(() => {
  return fullscreenRoutePrefixes.some((prefix) => route.path.startsWith(prefix))
})

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

async function logout() {
  await authStore.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="app-shell" :class="{ 'is-sidebar-collapsed': isSidebarCollapsed }">
    <aside class="sidebar" :class="{ 'is-collapsed': isSidebarCollapsed }">
      <div class="brand-row">
        <div class="brand" :title="isSidebarCollapsed ? systemName : ''">
          {{ isSidebarCollapsed ? '文保' : systemName }}
        </div>
        <div class="header-actions" v-if="!isSidebarCollapsed">
          <el-button link type="info" class="collapse-btn" @click="toggleSidebar">折叠</el-button>
        </div>
      </div>

      <div class="sidebar-mini-actions" v-if="isSidebarCollapsed">
        <el-button link type="info" class="expand-btn" @click="toggleSidebar">展开</el-button>
      </div>

      <div class="collapsed-icon-nav" v-if="isSidebarCollapsed">
        <template v-for="group in collapsedShortcutGroups" :key="group.key">
          <router-link
            class="collapsed-icon-item"
            :class="{ active: group.active }"
            :to="group.to"
            :data-title="group.title"
          >
            <span class="menu-icon" :class="`menu-icon--${getGroupIconType(group.title)}`" aria-hidden="true">
              {{ getGroupIconLabel(group.title) }}
            </span>
          </router-link>
        </template>
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
          <template v-for="item in group.items" :key="item.to">
            <router-link
              class="nav-link nav-sublink"
              :to="item.to"
            >
              {{ item.label }}
            </router-link>
          </template>
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
      <header class="content-topbar" :class="{ 'content-topbar--overlay': isFullscreenRoute }">
        <div class="user-panel" :title="`当前登录：${displayName}`">
          <img v-if="userAvatarUrl" class="user-avatar" :src="userAvatarUrl" alt="用户头像" />
          <span v-else class="user-avatar user-avatar--fallback">{{ userInitial }}</span>
          <span class="user-name">{{ displayName }}</span>
          <el-dropdown trigger="click" @command="handleUserCommand">
            <button type="button" class="user-menu-btn">
              账号管理
              <span class="user-menu-caret">▾</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <section class="content-body" :class="{ 'content-body--fullscreen': isFullscreenRoute }">
        <router-view />
      </section>
    </main>
  </div>

  <el-dialog v-model="profileDialogVisible" title="个人信息" width="520px">
    <el-form label-width="90px" :model="profileForm">
      <el-form-item label="账号">
        <el-input :model-value="profileForm.username" disabled />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="profileForm.first_name" placeholder="请输入姓名" />
      </el-form-item>
      <el-form-item label="姓氏">
        <el-input v-model="profileForm.last_name" placeholder="可选" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
      </el-form-item>
      <el-form-item label="联系方式">
        <el-input v-model="profileForm.contact_info" placeholder="手机号或邮箱" />
      </el-form-item>
      <el-form-item label="角色">
        <el-tag v-for="role in profileForm.roles" :key="role" type="info" effect="plain" style="margin-right: 6px; margin-bottom: 6px;">{{ role }}</el-tag>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="profileDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="profileSubmitting" @click="submitProfileUpdate">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="passwordDialogVisible" title="修改密码" width="460px">
    <el-form label-width="100px" :model="passwordForm">
      <el-form-item label="旧密码">
        <el-input v-model="passwordForm.old_password" type="password" show-password placeholder="请输入旧密码" />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="请输入新密码" />
      </el-form-item>
      <el-form-item label="确认新密码">
        <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="passwordDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="passwordSubmitting" @click="submitPasswordChange">确认修改</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAppStore } from '../stores/system/appStore'
import { useAuthStore } from '../stores/system/authStore'
import { changeSystemPassword, fetchSystemProfile, updateSystemProfile } from '../api/system/systemApi'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()
const THEME_MODE_KEY = 'heritage_theme_mode'
const SIDEBAR_COLLAPSE_KEY = 'heritage_sidebar_collapsed'
const themeMode = ref('system')
const isSidebarCollapsed = ref(false)
const profileDialogVisible = ref(false)
const passwordDialogVisible = ref(false)
const profileSubmitting = ref(false)
const passwordSubmitting = ref(false)
let mediaQueryList = null
const systemName = computed(() => appStore.systemName)

const profileForm = reactive({
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  contact_info: '',
  roles: []
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

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
      { label: '巡查记录', to: '/heritage/inspections' },
      { label: '坎儿井专项管理', to: '/heritage/kanerjing' }
    ]
  },
  {
    key: 'collect',
    title: '文物采集',
    items: [
      { label: '不可移动文物采集', to: '/collect/immovable' },
      { label: '采集数据管理', to: '/collect/records' }
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
      { label: '数据管理', to: '/system/data-management' },
      { label: '关于系统', to: '/system/about' },
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

function ensureHeritageEntries(groups = []) {
  const requiredHeritageItems = [
    { label: '不可移动文物管理', to: '/heritage/immovable' },
    { label: '巡查记录', to: '/heritage/inspections' },
    { label: '坎儿井专项管理', to: '/heritage/kanerjing' }
  ]
  const requiredCollectItems = [
    { label: '不可移动文物采集', to: '/collect/immovable' },
    { label: '采集数据管理', to: '/collect/records' }
  ]
  const requiredSystemItems = [
    { label: '数据管理', to: '/system/data-management' },
    { label: '关于系统', to: '/system/about' }
  ]
  if (isSuperAdminUser()) {
    requiredSystemItems.push({ label: '菜单管理', to: '/system/menus' })
  }

  function isSystemGroup(title, items = []) {
    if ((title || '').trim() === '系统管理') {
      return true
    }
    return (items || []).some((item) => typeof item?.to === 'string' && item.to.startsWith('/system/'))
  }

  const patchedGroups = groups.map((group) => {
    const title = (group.title || '').trim()
    const groupItems = group.items || []
    const systemGroup = isSystemGroup(title, groupItems)

    if (title !== '文物管理' && title !== '文物采集' && !systemGroup) {
      return group
    }

    let requiredItems = requiredHeritageItems
    if (title === '文物采集') {
      requiredItems = requiredCollectItems
    } else if (systemGroup) {
      requiredItems = requiredSystemItems
    }

    let existingItems = [...groupItems]
    if (systemGroup) {
      existingItems = existingItems.filter((item) => {
        const label = String(item?.label || '').trim()
        const to = String(item?.to || '').trim()
        return label !== '后台管理' && !to.startsWith('/admin/')
      })
    }

    const existingToSet = new Set(existingItems.map((item) => item.to))
    requiredItems.forEach((item) => {
      if (!existingToSet.has(item.to)) {
        existingItems.push(item)
      }
    })

    if (existingItems.length === (group.items || []).length) {
      return group
    }

    return {
      ...group,
      items: existingItems
    }
  })

  const collectExists = patchedGroups.some((group) => (group.title || '').trim() === '文物采集')
  if (!collectExists) {
    patchedGroups.push({
      key: 'collect',
      title: '文物采集',
      items: [...requiredCollectItems]
    })
  }

  const systemExists = patchedGroups.some((group) => isSystemGroup(group.title, group.items || []))
  if (!systemExists) {
    patchedGroups.push({
      key: 'system',
      title: '系统管理',
      items: [...requiredSystemItems]
    })
  }

  return patchedGroups
}

const menuGroups = computed(() => {
  const dynamic = buildMenuGroupsFromTree(authStore.menuTree)
  const restrictForNonSuperAdmin = (groups = []) => {
    if (isSuperAdminUser()) {
      return groups
    }
    return groups
      .map((group) => ({
        ...group,
        items: (group.items || []).filter((item) => item.to !== '/system/menus')
      }))
      .filter((group) => Array.isArray(group.items) && group.items.length > 0)
  }

  if (dynamic.length > 0) {
    return restrictForNonSuperAdmin(ensureHeritageEntries(dynamic))
  }
  return restrictForNonSuperAdmin(ensureHeritageEntries(staticMenuGroups))
})

function isSuperAdminUser() {
  const user = authStore.user || {}
  const roles = Array.isArray(user.roles) ? user.roles : []
  return Boolean(user.is_superuser) || roles.includes('超级管理员')
}

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

const displayName = computed(() => {
  const user = authStore.user || {}
  return user.real_name || user.full_name || user.name || user.username || user.nickname || '当前用户'
})

const userAvatarUrl = computed(() => {
  const user = authStore.user || {}
  return user.avatar || user.avatar_url || user.photo || ''
})

const userInitial = computed(() => {
  const text = String(displayName.value || '').trim()
  return text ? text.slice(0, 1).toUpperCase() : 'U'
})

function syncProfileFormFromUser(user = {}) {
  profileForm.username = user.username || ''
  profileForm.first_name = user.first_name || ''
  profileForm.last_name = user.last_name || ''
  profileForm.email = user.email || ''
  profileForm.contact_info = user.profile?.contact_info || ''
  profileForm.roles = Array.isArray(user.roles) ? user.roles : []
}

async function openProfileDialog() {
  profileDialogVisible.value = true
  syncProfileFormFromUser(authStore.user || {})

  try {
    const result = await fetchSystemProfile()
    if (result?.success && result.data) {
      authStore.user = result.data
      authStore.persistAuth()
      syncProfileFormFromUser(result.data)
    }
  } catch (_error) {
    ElMessage.warning('个人信息读取失败，已展示本地缓存信息')
  }
}

async function submitProfileUpdate() {
  profileSubmitting.value = true
  try {
    const payload = {
      first_name: profileForm.first_name || '',
      last_name: profileForm.last_name || '',
      email: profileForm.email || '',
      contact_info: profileForm.contact_info || ''
    }
    const result = await updateSystemProfile(payload)
    if (!result?.success) {
      throw new Error(result?.message || '个人信息保存失败')
    }

    if (result.data) {
      authStore.user = result.data
      authStore.persistAuth()
      syncProfileFormFromUser(result.data)
    }
    ElMessage.success(result?.message || '个人信息已更新')
    profileDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error?.message || '个人信息保存失败')
  } finally {
    profileSubmitting.value = false
  }
}

function openPasswordDialog() {
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  passwordDialogVisible.value = true
}

async function submitPasswordChange() {
  if (!passwordForm.old_password || !passwordForm.new_password || !passwordForm.confirm_password) {
    ElMessage.warning('请完整填写密码信息')
    return
  }
  if (passwordForm.new_password.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  passwordSubmitting.value = true
  try {
    const result = await changeSystemPassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password
    })
    if (!result?.success) {
      throw new Error(result?.message || '密码修改失败')
    }

    ElMessage.success(result?.message || '密码修改成功，请重新登录')
    passwordDialogVisible.value = false
    await logout()
  } catch (error) {
    ElMessage.error(error?.message || '密码修改失败')
  } finally {
    passwordSubmitting.value = false
  }
}

async function handleUserCommand(command) {
  if (command === 'profile') {
    await openProfileDialog()
    return
  }
  if (command === 'password') {
    openPasswordDialog()
    return
  }
  if (command === 'logout') {
    await logout()
  }
}

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

import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '../layouts/AppLayout.vue'
import DashboardView from '../views/dashboard/DashboardView.vue'
import ProjectListView from '../views/projects/ProjectListView.vue'
import ProjectCreateView from '../views/projects/ProjectCreateView.vue'
import ProjectDetailView from '../views/projects/ProjectDetailView.vue'
import HeritageMapView from '../views/heritage/HeritageMapView.vue'
import HeritageStatsView from '../views/heritage/HeritageStatsView.vue'
import HeritageDetailView from '../views/heritage/HeritageDetailView.vue'
import HeritageSiteManageView from '../views/heritage/HeritageSiteManageView.vue'
import InspectionRecordsView from '../views/heritage/InspectionRecordsView.vue'
import InspectionCreateView from '../views/heritage/InspectionCreateView.vue'
import ImmovableHeritageManageView from '../views/heritage/ImmovableHeritageManageView.vue'
import KanerjingListView from '../views/heritage/KanerjingListView.vue'
import ImmovableCollectView from '../views/collect/ImmovableCollectView.vue'
import KmlManagementView from '../views/gis/KmlManagementView.vue'
import KmlProcessConvertView from '../views/gis/KmlProcessConvertView.vue'
import OvkmlConvertView from '../views/gis/OvkmlConvertView.vue'
import LoginView from '../views/Login.vue'
import DeepSeekConfigView from '../views/system/admin/DeepSeekConfigView.vue'
import UserListView from '../views/system/user/UserListView.vue'
import RoleListView from '../views/system/role/RoleListView.vue'
import MenuListView from '../views/system/menu/MenuListView.vue'
import AboutView from '../views/system/about/AboutView.vue'
import DataManagementView from '../views/system/data/DataManagementView.vue'
import { useAuthStore } from '../stores/system/authStore'

const DESKTOP_AUTH_KEY = 'desktop_local_auth'

function hasElectronBridge() {
  return typeof window !== 'undefined' && Boolean(window.electronAPI)
}

function getDesktopAuthStorage() {
  if (typeof window === 'undefined' || !window.sessionStorage) {
    return null
  }
  return window.sessionStorage
}

function isDesktopAuthorized() {
  const storage = getDesktopAuthStorage()
  return hasElectronBridge() && Boolean(storage) && storage.getItem(DESKTOP_AUTH_KEY) === '1'
}

function isDesktopLoginWindowRoute(route) {
  return hasElectronBridge() && route.path === '/login' && route.query.login_window === '1'
}

const routes = [
  {
    path: '/login',
    component: LoginView,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: DashboardView },
      { path: 'projects', component: ProjectListView },
      { path: 'projects/new', component: ProjectCreateView },
      { path: 'projects/:projectId', component: ProjectDetailView, props: true },
      { path: 'heritage/map', component: HeritageMapView },
      { path: 'heritage/stats', component: HeritageStatsView },
      { path: 'heritage/immovable', component: HeritageSiteManageView },
      { path: 'heritage/inspections', component: InspectionRecordsView },
      { path: 'heritage/inspections/new', component: InspectionCreateView },
      { path: 'heritage/kanerjing', component: KanerjingListView },
      { path: 'collect/immovable', component: ImmovableCollectView },
      { path: 'collect/records', component: ImmovableHeritageManageView },
      { path: 'heritage/:siteId', component: HeritageDetailView, props: true },
      { path: 'gis/kml-management', component: KmlManagementView },
      { path: 'gis/kml-process-convert', component: KmlProcessConvertView },
      { path: 'gis/ovkml-convert', component: OvkmlConvertView },
      { path: 'system/users', component: UserListView, meta: { requiresSuperAdmin: true } },
      { path: 'system/roles', component: RoleListView },
      { path: 'system/data-management', component: DataManagementView },
      { path: 'system/about', component: AboutView },
      { path: 'system/ai-config', component: DeepSeekConfigView },
      { path: 'system/menus', component: MenuListView, meta: { requiresSuperAdmin: true } }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(async (to) => {
  if (isDesktopLoginWindowRoute(to)) {
    return true
  }

  if (to.path === '/') {
    return '/login'
  }

  if (to.query.desktop_auth === '1' && hasElectronBridge()) {
    const storage = getDesktopAuthStorage()
    if (storage) {
      storage.setItem(DESKTOP_AUTH_KEY, '1')
    }
    // Clean up legacy persistent flag to avoid login bypass after app restart.
    localStorage.removeItem(DESKTOP_AUTH_KEY)
  }

  if (isDesktopAuthorized()) {
    if (to.path === '/login') {
      return '/dashboard'
    }
    return true
  }

  const authStore = useAuthStore()
  await authStore.restoreSession()

  if (to.path === '/login') {
    if (authStore.isAuthenticated) {
      return '/dashboard'
    }
    return true
  }

  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth !== false)
  if (requiresAuth && !authStore.isAuthenticated) {
    return {
      path: '/login',
      query: {
        redirect: to.fullPath
      }
    }
  }

  const requiresSuperAdmin = to.matched.some((record) => record.meta.requiresSuperAdmin)
  if (requiresSuperAdmin) {
    const user = authStore.user || {}
    const roles = Array.isArray(user.roles) ? user.roles : []
    const isSuperAdmin = Boolean(user.is_superuser) || roles.includes('超级管理员')
    if (!isSuperAdmin) {
      return '/dashboard'
    }
  }

  return true
})

export default router

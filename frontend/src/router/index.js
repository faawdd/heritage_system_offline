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
import LoginView from '../views/system/auth/LoginView.vue'
import UserListView from '../views/system/user/UserListView.vue'
import RoleListView from '../views/system/role/RoleListView.vue'
import MenuListView from '../views/system/menu/MenuListView.vue'
import { useAuthStore } from '../stores/system/authStore'

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
      { path: 'system/users', component: UserListView },
      { path: 'system/roles', component: RoleListView },
      { path: 'system/menus', component: MenuListView }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(async (to) => {
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

  return true
})

export default router

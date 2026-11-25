<template>
  <section>
    <header class="page-header">
      <h1>文物档案详情</h1>
      <p>只读档案、两线坐标与边界导出</p>
    </header>

    <div class="toolbar card">
      <el-button @click="goMap">返回地图</el-button>
      <el-button type="primary" :loading="loading" @click="loadDetail">刷新</el-button>
      <el-button type="success" @click="exportDialogVisible = true">导出范围坐标</el-button>
    </div>

    <div class="dashboard-grid">
      <div class="card">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="文物名称">{{ detail.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="四普编号">{{ detail.sip_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="曾用名/别名">{{ detail.former_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="时代">{{ detail.era || '-' }}</el-descriptions-item>
          <el-descriptions-item label="保护等级">{{ detail.level_label || '-' }}</el-descriptions-item>
          <el-descriptions-item label="文物类别">{{ detail.category_label || '-' }}</el-descriptions-item>
          <el-descriptions-item label="文物类型">{{ detail.heritage_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="乡镇/村">{{ detail.township || '-' }}{{ detail.village ? ' / ' + detail.village : '' }}</el-descriptions-item>
          <el-descriptions-item label="详细地址">{{ detail.address || '-' }}</el-descriptions-item>
          <el-descriptions-item label="经纬度">{{ detail.longitude ?? '-' }}, {{ detail.latitude ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="坐标系">{{ detail.coordinate_system || '-' }}</el-descriptions-item>
          <el-descriptions-item label="管理责任单位">{{ detail.manager || '-' }}</el-descriptions-item>
          <el-descriptions-item label="登记管理单位">{{ detail.management_unit || '-' }}</el-descriptions-item>
          <el-descriptions-item label="权属信息">{{ detail.ownership_detail || '-' }}</el-descriptions-item>
          <el-descriptions-item label="现状描述">{{ detail.description || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="card">
        <HeritageZoneMap
          :longitude="detail.longitude"
          :latitude="detail.latitude"
          :body-boundary-data="detail.body_boundary_data || []"
          :protection-zone-data="detail.protection_zone_data || []"
          :control-zone-data="detail.control_zone_data || []"
        />
      </div>
    </div>

    <div class="card top-space">
      <h3>最近巡查记录</h3>
      <el-table :data="detail.inspection_records || []" v-loading="loading" stripe>
        <el-table-column prop="inspect_time" label="巡查时间" width="180" />
        <el-table-column prop="inspector_name" label="巡查人" width="120" />
        <el-table-column prop="is_normal" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_normal ? 'success' : 'danger'">
              {{ scope.row.is_normal ? '正常' : '异常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="巡查坐标" width="220">
          <template #default="scope">
            {{ formatCoordinates(scope.row) }}
          </template>
        </el-table-column>
        <el-table-column label="距文物点" width="130">
          <template #default="scope">
            {{ formatDistance(scope.row.distance_meters) }}
          </template>
        </el-table-column>
        <el-table-column prop="issue_details" label="问题描述" min-width="260" />
        <el-table-column label="现场照片" width="110">
          <template #default="scope">
            <el-button v-if="getPhotoUrls(scope.row).length" link type="primary" @click="previewPhotos(scope.row)">
              查看（{{ getPhotoUrls(scope.row).length }}）
            </el-button>
            <span v-else>无照片</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="photoDialogVisible" title="巡查现场照片" width="720px">
      <img v-for="url in currentPhotoUrls" :key="url" :src="url" style="width: 100%; max-height: 70vh; object-fit: contain; margin-bottom: 12px" />
    </el-dialog>

    <el-dialog v-model="exportDialogVisible" title="导出文物范围坐标" width="560px">
      <el-form label-width="130px">
        <el-form-item label="导出类型">
          <el-radio-group v-model="exportForm.action">
            <el-radio value="export_single_boundary_csv">边界坐标（CSV）</el-radio>
            <el-radio value="export_single_boundary_kmz">奥维边界（KMZ）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exportDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="exporting" @click="submitExport">开始导出</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { exportHeritageBoundary, fetchHeritageDetail } from '../../api/heritageApi'
import HeritageZoneMap from '../../components/heritage/HeritageZoneMap.vue'

const route = useRoute()
const router = useRouter()

const siteId = route.params.siteId
const loading = ref(false)
const exporting = ref(false)
const exportDialogVisible = ref(false)
const photoDialogVisible = ref(false)
const currentPhotoUrls = ref([])

const detail = reactive({
  protection_zone_data: [],
  control_zone_data: [],
  inspection_records: []
})

const exportForm = reactive({
  action: 'export_single_boundary_csv'
})

function fillReactive(target, source) {
  Object.assign(target, source || {})
}

function goMap() {
  router.push('/heritage/map')
}

function formatDistance(meters) {
  if (meters == null || !Number.isFinite(Number(meters)) || Number(meters) < 0) return '无法计算'
  const value = Number(meters)
  return value < 1000 ? `约 ${Math.round(value)} 米` : `约 ${(value / 1000).toFixed(value < 10000 ? 1 : 0)} 公里`
}

function formatCoordinates(row) {
  if (row.longitude == null || row.latitude == null) return '-'
  return `${row.longitude}, ${row.latitude}`
}

function normalizePhotoUrl(url) {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (/^(https?:)?\/\//i.test(raw) || raw.startsWith('data:') || raw.startsWith('blob:')) return raw
  return new URL(raw.startsWith('/') ? raw : `/${raw}`, window.location.origin).toString()
}

function getPhotoUrls(row) {
  const urls = Array.isArray(row.photo_urls) ? row.photo_urls : (row.photo_url ? [row.photo_url] : [])
  return urls.map(normalizePhotoUrl).filter(Boolean)
}

function previewPhotos(row) {
  currentPhotoUrls.value = getPhotoUrls(row)
  photoDialogVisible.value = currentPhotoUrls.value.length > 0
}

async function loadDetail() {
  loading.value = true
  try {
    const result = await fetchHeritageDetail(siteId)
    if (!result.success) {
      throw new Error(result.message || '加载文物详情失败')
    }
    fillReactive(detail, result.data || {})
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function submitExport() {
  exporting.value = true
  try {
    const payload = new URLSearchParams()
    payload.set('action', exportForm.action)

    const response = await exportHeritageBoundary(siteId, payload)
    const blob = new Blob([response.data])
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    const suffix = exportForm.action === 'export_single_boundary_kmz' ? 'kmz' : 'csv'
    link.download = `heritage_${siteId}_boundary.${suffix}`
    link.click()
    URL.revokeObjectURL(link.href)
    ElMessage.success('导出成功')
    exportDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

loadDetail()
</script>

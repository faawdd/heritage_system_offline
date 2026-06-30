<template>
  <section>
    <header class="page-header">
      <h1>文物档案详情</h1>
      <p>只读档案、两线坐标与边界导出</p>
    </header>

    <div class="toolbar card">
      <el-button @click="goMap">返回地图</el-button>
      <el-button type="primary" :loading="loading" @click="loadDetail">刷新</el-button>
      <el-button type="success" @click="exportDialogVisible = true">导出四普边界</el-button>
    </div>

    <div class="dashboard-grid">
      <div class="card">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="文物名称">{{ detail.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="四普编号">{{ detail.sip_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="保护等级">{{ detail.level_label || '-' }}</el-descriptions-item>
          <el-descriptions-item label="文物类别">{{ detail.category_label || '-' }}</el-descriptions-item>
          <el-descriptions-item label="详细地址">{{ detail.address || '-' }}</el-descriptions-item>
          <el-descriptions-item label="经纬度">{{ detail.longitude }}, {{ detail.latitude }}</el-descriptions-item>
          <el-descriptions-item label="管理责任单位">{{ detail.manager || '-' }}</el-descriptions-item>
          <el-descriptions-item label="现状描述">{{ detail.description || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="card">
        <HeritageZoneMap
          :longitude="detail.longitude"
          :latitude="detail.latitude"
          :protection-zone-data="detail.protection_zone_data || []"
          :control-zone-data="detail.control_zone_data || []"
        />
      </div>
    </div>

    <div class="card top-space">
      <h3>最近巡查记录</h3>
      <el-table :data="detail.inspection_records || []" stripe>
        <el-table-column prop="inspect_time" label="巡查时间" width="180" />
        <el-table-column prop="is_normal" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_normal ? 'success' : 'danger'">
              {{ scope.row.is_normal ? '正常' : '异常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="issue_details" label="问题描述" min-width="260" />
      </el-table>
    </div>

    <el-dialog v-model="exportDialogVisible" title="导出四普边界范围" width="560px">
      <el-form label-width="130px">
        <el-form-item label="四普登录凭证">
          <el-input v-model="exportForm.sipu_cookie" type="textarea" :rows="4" placeholder="请粘贴 Cookie，例如 JSESSIONID=XXXX..." />
        </el-form-item>
        <el-form-item label="行政区划代码">
          <el-input v-model="exportForm.sipu_county" placeholder="如 650421（可选）" />
        </el-form-item>
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

const detail = reactive({
  protection_zone_data: [],
  control_zone_data: [],
  inspection_records: []
})

const exportForm = reactive({
  sipu_cookie: '',
  sipu_county: '',
  action: 'export_single_boundary_csv'
})

function fillReactive(target, source) {
  Object.keys(target).forEach((key) => {
    target[key] = source?.[key] ?? target[key]
  })
}

function goMap() {
  router.push('/heritage/map')
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
  if (!exportForm.sipu_cookie) {
    ElMessage.warning('请填写四普 Cookie')
    return
  }

  exporting.value = true
  try {
    const payload = new URLSearchParams()
    payload.set('sipu_cookie', exportForm.sipu_cookie)
    payload.set('sipu_county', exportForm.sipu_county)
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

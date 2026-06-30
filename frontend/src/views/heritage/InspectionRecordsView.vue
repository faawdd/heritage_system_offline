<template>
  <section>
    <header class="page-header">
      <h1>巡查记录管理</h1>
      <p>统一管理巡查上报数据，兼容 UniApp 与原平台上传记录</p>
    </header>

    <div class="stats-grid top-space">
      <div class="stat-card">
        <p class="stat-title">巡查总数</p>
        <p class="stat-value">{{ stats.total_count }}</p>
      </div>
      <div class="stat-card">
        <p class="stat-title">今日巡查</p>
        <p class="stat-value">{{ stats.today_count }}</p>
      </div>
      <div class="stat-card">
        <p class="stat-title">异常记录</p>
        <p class="stat-value">{{ stats.abnormal_count }}</p>
      </div>
    </div>

    <div class="toolbar card top-space">
      <el-input
        v-model="filters.keyword"
        placeholder="按文物名称/四普编号/巡查员/问题检索"
        clearable
        style="max-width: 360px"
      />
      <el-select v-model="filters.is_normal" placeholder="状态筛选" clearable style="width: 180px">
        <el-option label="正常" value="true" />
        <el-option label="异常" value="false" />
      </el-select>
      <el-button type="primary" :loading="loading" @click="loadRows">查询</el-button>
    </div>

    <div class="card top-space">
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="inspect_time" label="巡查时间" width="170" />
        <el-table-column prop="site_name" label="文物名称" min-width="180" />
        <el-table-column prop="site_code" label="四普编号" width="140" />
        <el-table-column prop="inspector_name" label="巡查员" width="120" />
        <el-table-column prop="is_normal" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_normal ? 'success' : 'danger'">
              {{ scope.row.is_normal ? '正常' : '异常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="issue_details" label="问题描述" min-width="220" show-overflow-tooltip />
        <el-table-column label="照片" width="100">
          <template #default="scope">
            <el-button link type="primary" :disabled="!scope.row.photo_url" @click="previewPhoto(scope.row.photo_url)">
              查看
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210">
          <template #default="scope">
            <el-button link type="warning" @click="toggleStatus(scope.row)">
              标记{{ scope.row.is_normal ? '异常' : '正常' }}
            </el-button>
            <el-button link type="danger" @click="removeRow(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="top-space" style="display: flex; justify-content: flex-end">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="pagination.total"
          :page-size="pagination.page_size"
          :current-page="pagination.page"
          @current-change="onPageChange"
        />
      </div>
    </div>

    <el-dialog v-model="photoDialogVisible" title="现场照片" width="720px">
      <img v-if="currentPhotoUrl" :src="currentPhotoUrl" style="width: 100%; max-height: 70vh; object-fit: contain" />
    </el-dialog>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { deleteInspection, fetchInspections, fetchInspectionStats, patchInspection } from '../../api/inspectionApi'

const loading = ref(false)
const rows = ref([])
const currentPhotoUrl = ref('')
const photoDialogVisible = ref(false)

const filters = reactive({
  keyword: '',
  is_normal: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const stats = reactive({
  total_count: 0,
  today_count: 0,
  abnormal_count: 0
})

function buildParams() {
  return {
    page: pagination.page,
    page_size: pagination.page_size,
    keyword: filters.keyword,
    is_normal: filters.is_normal
  }
}

async function loadStats() {
  const result = await fetchInspectionStats()
  if (result.success) {
    Object.assign(stats, result.data || {})
  }
}

async function loadRows() {
  loading.value = true
  try {
    const result = await fetchInspections(buildParams())
    if (!result.success) {
      throw new Error(result.message || '加载失败')
    }
    rows.value = result.rows || []
    Object.assign(pagination, result.pagination || {})
    await loadStats()
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function previewPhoto(url) {
  currentPhotoUrl.value = url
  photoDialogVisible.value = true
}

async function toggleStatus(row) {
  try {
    const result = await patchInspection(row.id, {
      is_normal: !row.is_normal,
      issue_details: row.issue_details || ''
    })
    if (!result.success) {
      throw new Error(result.message || '更新失败')
    }
    ElMessage.success('状态已更新')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '更新失败')
  }
}

async function removeRow(row) {
  try {
    await ElMessageBox.confirm(`确认删除巡查记录 #${row.id} 吗？`, '删除确认', {
      type: 'warning'
    })
  } catch (_cancel) {
    return
  }

  try {
    const result = await deleteInspection(row.id)
    if (!result.success) {
      throw new Error(result.message || '删除失败')
    }
    ElMessage.success('删除成功')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '删除失败')
  }
}

function onPageChange(page) {
  pagination.page = page
  loadRows()
}

loadRows()
</script>

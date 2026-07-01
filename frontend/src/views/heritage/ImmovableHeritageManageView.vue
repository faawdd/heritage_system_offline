<template>
  <section>
    <header class="page-header">
      <h1>不可移动文物管理</h1>
      <p>支持档案查询、编辑以及 CSV 导入导出</p>
    </header>

    <div class="toolbar card top-space">
      <el-input
        v-model="filters.keyword"
        placeholder="文物名称/四普编号/地址/管理单位"
        clearable
        style="max-width: 320px"
      />
      <el-select v-model="filters.category" clearable placeholder="文物类别" style="width: 180px">
        <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="filters.level" clearable placeholder="保护级别" style="width: 220px">
        <el-option v-for="item in levelOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button type="primary" :loading="loading" @click="handleSearch">查询</el-button>
      <el-button :loading="exporting" @click="handleExport">导出 CSV</el-button>
      <el-upload
        :show-file-list="false"
        accept=".csv"
        :before-upload="beforeImport"
      >
        <el-button type="success" :loading="importing">导入 CSV</el-button>
      </el-upload>
    </div>

    <div class="card top-space">
      <el-table :data="rows" stripe v-loading="loading">
        <el-table-column prop="sip_code" label="四普编号" width="150" />
        <el-table-column label="文物名称" min-width="200">
          <template #default="scope">
            <a
              class="heritage-view-link"
              :href="buildViewModeHref(scope.row)"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ scope.row.name }}
            </a>
          </template>
        </el-table-column>
        <el-table-column prop="category_label" label="文物类别" width="130" />
        <el-table-column prop="level_label" label="保护级别" width="190" />
        <el-table-column prop="address" label="详细地址" min-width="220" show-overflow-tooltip />
        <el-table-column prop="manager" label="管理单位" width="160" show-overflow-tooltip />
        <el-table-column label="坐标" min-width="170">
          <template #default="scope">
            {{ scope.row.longitude }}, {{ scope.row.latitude }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button>
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

    <el-dialog v-model="dialog.visible" title="编辑文物档案" width="780px">
      <el-form label-width="100px" label-position="left">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="文物名称">
              <el-input v-model="dialog.form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="四普编号">
              <el-input v-model="dialog.form.sip_code" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="文物类别">
              <el-select v-model="dialog.form.category" style="width: 100%">
                <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保护级别">
              <el-select v-model="dialog.form.level" style="width: 100%">
                <el-option v-for="item in levelOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="经度">
              <el-input v-model="dialog.form.longitude" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="纬度">
              <el-input v-model="dialog.form.latitude" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="详细地址">
          <el-input v-model="dialog.form.address" />
        </el-form-item>
        <el-form-item label="管理单位">
          <el-input v-model="dialog.form.manager" />
        </el-form-item>
        <el-form-item label="现状描述">
          <el-input v-model="dialog.form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="保护范围坐标">
          <el-input v-model="dialog.form.protection_zone" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="建控地带坐标">
          <el-input v-model="dialog.form.control_zone" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="dialog.loading" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  exportImmovableHeritage,
  fetchImmovableHeritageList,
  importImmovableHeritage,
  patchImmovableHeritage
} from '../../api/heritageApi'

const loading = ref(false)
const importing = ref(false)
const exporting = ref(false)
const rows = ref([])
const categoryOptions = ref([])
const levelOptions = ref([])

const filters = reactive({
  keyword: '',
  category: '',
  level: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const dialog = reactive({
  visible: false,
  loading: false,
  editId: null,
  form: {
    name: '',
    sip_code: '',
    category: '',
    level: '',
    address: '',
    longitude: '',
    latitude: '',
    manager: '',
    description: '',
    protection_zone: '',
    control_zone: ''
  }
})

function buildParams() {
  return {
    page: pagination.page,
    page_size: pagination.page_size,
    keyword: filters.keyword,
    category: filters.category,
    level: filters.level
  }
}

async function loadRows() {
  loading.value = true
  try {
    const result = await fetchImmovableHeritageList(buildParams())
    if (!result.success) {
      throw new Error(result.message || '加载失败')
    }

    rows.value = result.rows || []
    Object.assign(pagination, result.pagination || {})
    categoryOptions.value = result.meta?.category_choices || []
    levelOptions.value = result.meta?.level_choices || []
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadRows()
}

function onPageChange(page) {
  pagination.page = page
  loadRows()
}

function openEdit(row) {
  dialog.editId = row.id
  dialog.form = {
    name: row.name || '',
    sip_code: row.sip_code || '',
    category: row.category || '',
    level: row.level || '',
    address: row.address || '',
    longitude: row.longitude,
    latitude: row.latitude,
    manager: row.manager || '',
    description: row.description || '',
    protection_zone: row.protection_zone || '',
    control_zone: row.control_zone || ''
  }
  dialog.visible = true
}

function buildViewModeHref(row) {
  const id = row?.id
  if (!id) {
    return '#'
  }

  if (row?.preview_url) {
    return row.preview_url
  }

  return `/heritage/${id}?mode=view`
}

async function submitEdit() {
  dialog.loading = true
  try {
    const payload = {
      ...dialog.form,
      longitude: Number(dialog.form.longitude),
      latitude: Number(dialog.form.latitude)
    }

    const result = await patchImmovableHeritage(dialog.editId, payload)
    if (!result.success) {
      throw new Error(result.message || '保存失败')
    }
    ElMessage.success('保存成功')
    dialog.visible = false
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    dialog.loading = false
  }
}

async function handleExport() {
  exporting.value = true
  try {
    const response = await exportImmovableHeritage({
      keyword: filters.keyword,
      category: filters.category,
      level: filters.level
    })

    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8-sig;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `不可移动文物_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(error?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function beforeImport(file) {
  importing.value = true
  try {
    const result = await importImmovableHeritage(file)
    if (!result.success) {
      throw new Error(result.message || '导入失败')
    }
    const summary = result.data || {}
    ElMessage.success(
      `导入完成：新增 ${summary.created_count || 0}，更新 ${summary.updated_count || 0}，跳过 ${summary.skipped_count || 0}`
    )
    pagination.page = 1
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '导入失败')
  } finally {
    importing.value = false
  }

  return false
}

loadRows()
</script>

<style scoped>
.heritage-view-link {
  color: var(--accent, #409eff);
  text-decoration: none;
  font-weight: 600;
}

.heritage-view-link:hover {
  text-decoration: underline;
}
</style>

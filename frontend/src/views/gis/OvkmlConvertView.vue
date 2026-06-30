<template>
  <section>
    <header class="page-header">
      <h1>OVKML/KML/KMZ 转换导入</h1>
      <p>复用旧导入逻辑，支持去重导入项目审计记录</p>
    </header>

    <div class="card top-space">
      <el-form label-width="130px">
        <el-form-item label="文件">
          <input ref="fileInputRef" type="file" accept=".kml,.kmz,.ovkml,.ovkmz" />
        </el-form-item>

        <el-form-item label="输入坐标系">
          <el-select v-model="form.input_crs" style="width: 260px">
            <el-option label="WGS84" value="wgs84" />
            <el-option label="GCJ02" value="gcj02" />
            <el-option label="BD09" value="bd09" />
          </el-select>
        </el-form-item>

        <el-form-item label="输出坐标系">
          <el-select v-model="form.output_crs" style="width: 260px">
            <el-option label="CGCS2000" value="cgcs2000" />
            <el-option label="WGS84" value="wgs84" />
            <el-option label="GCJ02" value="gcj02" />
            <el-option label="BD09" value="bd09" />
          </el-select>
        </el-form-item>

        <el-form-item label="去重导入">
          <el-switch v-model="form.deduplicate" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runConvert">转换预览</el-button>
          <el-button type="success" :loading="loading" @click="runImport">转换并导入</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="card top-space" v-if="result.total_count">
      <h3>转换结果</h3>
      <p>
        共 {{ result.total_count }} 条，格式 {{ result.file_format }}
        <span v-if="result.import_done">，已导入 {{ result.import_count }} 条，跳过 {{ result.import_skipped_count }} 条</span>
      </p>
      <div class="action-row top-space">
        <el-button type="primary" @click="downloadUrl(result.project_csv_url, 'projectaudit.csv')">下载项目审计 CSV</el-button>
        <el-button type="primary" plain @click="downloadUrl(result.detail_csv_url, 'detail.csv')">下载明细 CSV</el-button>
      </div>

      <el-alert
        v-if="result.preview_truncated"
        title="仅显示前 100 条预览，请下载 CSV 查看全量数据"
        type="warning"
        :closable="false"
        class="top-space"
      />

      <el-table :data="result.preview_rows" stripe class="top-space">
        <el-table-column prop="project_name" label="项目名" min-width="200" />
        <el-table-column prop="geometry_type" label="几何" width="110" />
        <el-table-column prop="vertex_count" label="顶点" width="100" />
        <el-table-column prop="project_lon" label="经度" min-width="140" />
        <el-table-column prop="project_lat" label="纬度" min-width="140" />
        <el-table-column prop="cgcs2000_x" label="X" min-width="140" />
        <el-table-column prop="cgcs2000_y" label="Y" min-width="140" />
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { submitOvkmlConvert } from '../../api/gisApi'

const fileInputRef = ref(null)
const loading = ref(false)

const form = reactive({
  input_crs: 'wgs84',
  output_crs: 'cgcs2000',
  deduplicate: true
})

const result = reactive({
  total_count: 0,
  preview_rows: [],
  preview_truncated: false,
  file_format: '',
  project_csv_url: '',
  detail_csv_url: '',
  import_done: false,
  import_count: 0,
  import_skipped_count: 0
})

function buildFormData(action) {
  const file = fileInputRef.value?.files?.[0]
  if (!file) {
    throw new Error('请先选择文件')
  }
  const formData = new FormData()
  formData.set('ovkml_file', file)
  formData.set('input_crs', form.input_crs)
  formData.set('output_crs', form.output_crs)
  formData.set('deduplicate', form.deduplicate ? 'true' : 'false')
  formData.set('action', action)
  return formData
}

async function submit(action) {
  loading.value = true
  try {
    const response = await submitOvkmlConvert(buildFormData(action))
    if (!response.success) {
      throw new Error(response.message || '操作失败')
    }
    Object.assign(result, response.data || {})
    ElMessage.success(action === 'import' ? '导入完成' : '转换完成')
  } catch (error) {
    ElMessage.error(error?.message || '操作失败')
  } finally {
    loading.value = false
  }
}

function runConvert() {
  submit('convert')
}

function runImport() {
  submit('import')
}

function downloadUrl(url, fallbackName) {
  if (!url) {
    ElMessage.warning('暂无可下载文件')
    return
  }
  const link = document.createElement('a')
  link.href = url
  link.download = fallbackName
  link.target = '_blank'
  link.click()
}
</script>

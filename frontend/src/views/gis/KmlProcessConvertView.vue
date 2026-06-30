<template>
  <section>
    <header class="page-header">
      <h1>KML 处理与转换</h1>
      <p>保留旧转换规则，前端改为 Vue3 交互与文件流下载</p>
    </header>

    <div class="dashboard-grid top-space">
      <div class="card">
        <h3>DXF 转 KML</h3>
        <el-form label-width="120px">
          <el-form-item label="DXF文件">
            <input ref="dxfInputRef" type="file" accept=".dxf" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="dxfLoading" @click="runDxfConvert">转换并下载 KML</el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="card">
        <h3>KML/KMZ 坐标表</h3>
        <el-form label-width="120px">
          <el-form-item label="来源模式">
            <el-radio-group v-model="tableForm.source_mode">
              <el-radio label="uploaded">已上传记录</el-radio>
              <el-radio label="file">本地上传</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="已上传记录" v-if="tableForm.source_mode === 'uploaded'">
            <el-select v-model="tableForm.uploaded_record_id" placeholder="请选择" style="width: 100%">
              <el-option v-for="row in records" :key="row.id" :label="`#${row.id} ${row.title}`" :value="String(row.id)" />
            </el-select>
          </el-form-item>

          <el-form-item label="KML文件" v-else>
            <input ref="kmlInputRef" type="file" accept=".kml,.kmz,.ovkml,.ovkmz" />
          </el-form-item>

          <el-form-item label="输入坐标系">
            <el-select v-model="tableForm.input_crs" style="width: 100%">
              <el-option label="WGS84" value="wgs84" />
              <el-option label="GCJ02" value="gcj02" />
              <el-option label="BD09" value="bd09" />
            </el-select>
          </el-form-item>

          <el-form-item label="输出模式">
            <el-select v-model="tableForm.output_mode" style="width: 100%">
              <el-option label="经纬度" value="geo" />
              <el-option label="CGCS2000投影" value="cgcs2000_proj" />
            </el-select>
          </el-form-item>

          <el-form-item label="经纬度输出" v-if="tableForm.output_mode === 'geo'">
            <el-select v-model="tableForm.geo_output_crs" style="width: 100%">
              <el-option label="WGS84" value="wgs84" />
              <el-option label="GCJ02" value="gcj02" />
              <el-option label="BD09" value="bd09" />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="tableLoading" @click="previewTable">预览</el-button>
            <el-button type="success" :loading="tableLoading" @click="exportCsv">导出 CSV</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <div class="card top-space" v-if="preview.total_count">
      <h3>预览结果（{{ preview.total_count }} 条）</h3>
      <el-alert
        v-if="preview.preview_truncated"
        title="仅显示前 200 条，请导出 CSV 查看完整结果"
        type="warning"
        :closable="false"
        class="top-space"
      />
      <el-table :data="preview.preview_rows" stripe class="top-space">
        <el-table-column prop="index" label="序号" width="80" />
        <el-table-column prop="project_name" label="名称" min-width="220" />
        <el-table-column prop="geometry_type" label="几何" width="100" />
        <el-table-column prop="vertex_count" label="顶点" width="100" />
        <el-table-column prop="coord_a" :label="preview.coord_a_label || '坐标A'" min-width="150" />
        <el-table-column prop="coord_b" :label="preview.coord_b_label || '坐标B'" min-width="150" />
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchGisKmlRecords, submitKmlProcessConvert } from '../../api/gisApi'

const dxfInputRef = ref(null)
const kmlInputRef = ref(null)
const dxfLoading = ref(false)
const tableLoading = ref(false)
const records = ref([])

const tableForm = reactive({
  source_mode: 'uploaded',
  uploaded_record_id: '',
  input_crs: 'wgs84',
  output_mode: 'geo',
  geo_output_crs: 'wgs84'
})

const preview = reactive({
  total_count: 0,
  preview_rows: [],
  preview_truncated: false,
  coord_a_label: '经度',
  coord_b_label: '纬度'
})

function saveBlob(blob, filename) {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename || 'export.dat'
  link.click()
  URL.revokeObjectURL(link.href)
}

async function loadRecords() {
  const result = await fetchGisKmlRecords()
  if (result.success) {
    records.value = result.rows || []
    if (!tableForm.uploaded_record_id && records.value.length > 0) {
      tableForm.uploaded_record_id = String(records.value[0].id)
    }
  }
}

async function runDxfConvert() {
  const file = dxfInputRef.value?.files?.[0]
  if (!file) {
    ElMessage.warning('请先选择DXF文件')
    return
  }

  dxfLoading.value = true
  try {
    const formData = new FormData()
    formData.set('tool', 'dxf_to_kml')
    formData.set('dxf_file', file)

    const result = await submitKmlProcessConvert(formData)
    if (!result.success) {
      throw new Error(result.message || '转换失败')
    }
    if (result.download?.blob) {
      saveBlob(result.download.blob, result.download.filename || 'dxf_to_kml.kml')
      ElMessage.success('转换成功')
    }
  } catch (error) {
    ElMessage.error(error?.message || '转换失败')
  } finally {
    dxfLoading.value = false
  }
}

function buildTableFormData(action) {
  const formData = new FormData()
  formData.set('tool', 'kml_table')
  formData.set('action', action)
  formData.set('source_mode', tableForm.source_mode)
  formData.set('input_crs', tableForm.input_crs)
  formData.set('output_mode', tableForm.output_mode)
  formData.set('geo_output_crs', tableForm.geo_output_crs)

  if (tableForm.source_mode === 'uploaded') {
    formData.set('uploaded_record_id', tableForm.uploaded_record_id)
  } else {
    const file = kmlInputRef.value?.files?.[0]
    if (file) {
      formData.set('kml_file', file)
    }
  }

  return formData
}

async function previewTable() {
  tableLoading.value = true
  try {
    const result = await submitKmlProcessConvert(buildTableFormData('preview'))
    if (!result.success) {
      throw new Error(result.message || '预览失败')
    }
    Object.assign(preview, result.data || {})
  } catch (error) {
    ElMessage.error(error?.message || '预览失败')
  } finally {
    tableLoading.value = false
  }
}

async function exportCsv() {
  tableLoading.value = true
  try {
    const result = await submitKmlProcessConvert(buildTableFormData('export_csv'))
    if (!result.success) {
      throw new Error(result.message || '导出失败')
    }
    if (result.download?.blob) {
      saveBlob(result.download.blob, result.download.filename || 'kml_table.csv')
      ElMessage.success('导出成功')
    }
  } catch (error) {
    ElMessage.error(error?.message || '导出失败')
  } finally {
    tableLoading.value = false
  }
}

onMounted(async () => {
  try {
    await loadRecords()
  } catch (error) {
    ElMessage.error(error?.message || '加载上传记录失败')
  }
})
</script>

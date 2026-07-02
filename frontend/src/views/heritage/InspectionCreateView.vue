<template>
  <section>
    <header class="page-header">
      <h1>新增巡查记录</h1>
      <p>统一使用 Vue 页面创建巡查记录，替代旧手机模板</p>
    </header>

    <div class="card top-space" style="max-width: 920px">
      <el-form label-width="110px" label-position="left">
        <el-form-item label="巡查文物点" required>
          <el-select
            v-model="form.site_id"
            filterable
            remote
            reserve-keyword
            clearable
            placeholder="输入名称/四普编号搜索"
            :remote-method="loadSiteOptions"
            :loading="metaLoading"
            style="width: 100%"
          >
            <el-option
              v-for="site in siteOptions"
              :key="site.id"
              :label="`${site.name}（${site.sip_code || '无编号'}）`"
              :value="site.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="巡查员">
          <el-select v-model="form.inspector_id" filterable style="width: 100%">
            <el-option
              v-for="inspector in inspectorOptions"
              :key="inspector.id"
              :label="`${inspector.name}（${inspector.username}）`"
              :value="inspector.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="巡查状态">
          <el-switch v-model="form.is_normal" active-text="正常" inactive-text="异常" />
        </el-form-item>

        <el-form-item label="问题描述">
          <el-input
            v-model="form.issue_details"
            type="textarea"
            :rows="4"
            placeholder="如有异常，请说明问题位置与现象"
          />
        </el-form-item>

        <el-form-item label="经纬度（选填）">
          <el-row :gutter="12" style="width: 100%">
            <el-col :span="12">
              <el-input v-model="form.longitude" placeholder="经度，如 90.335167" />
            </el-col>
            <el-col :span="12">
              <el-input v-model="form.latitude" placeholder="纬度，如 42.870531" />
            </el-col>
          </el-row>
        </el-form-item>

        <el-form-item label="现场照片" required>
          <el-upload
            class="upload-block"
            :auto-upload="false"
            :show-file-list="true"
            :limit="1"
            accept="image/*"
            :on-change="onPhotoChange"
            :on-remove="onPhotoRemove"
          >
            <el-button type="primary" plain>选择照片</el-button>
            <template #tip>
              <div class="el-upload__tip">请上传带经纬度时间水印的现场照片（仅 1 张）</div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submitCreate">提交创建</el-button>
          <el-button @click="goBack">返回列表</el-button>
        </el-form-item>
      </el-form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { createInspection, fetchInspectionMeta } from '../../api/inspectionApi'

const router = useRouter()

const metaLoading = ref(false)
const submitting = ref(false)
const photoFile = ref(null)
const siteOptions = ref([])
const inspectorOptions = ref([])

const form = reactive({
  site_id: null,
  inspector_id: null,
  is_normal: true,
  issue_details: '',
  longitude: '',
  latitude: ''
})

async function loadMeta(keyword = '') {
  metaLoading.value = true
  try {
    const result = await fetchInspectionMeta({ keyword, limit: 100 })
    if (!result.success) {
      throw new Error(result.message || '加载巡查基础信息失败')
    }
    siteOptions.value = result.data?.site_options || []
    inspectorOptions.value = result.data?.inspector_options || []

    if (!form.inspector_id && result.data?.defaults?.inspector_id) {
      form.inspector_id = result.data.defaults.inspector_id
    }
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    metaLoading.value = false
  }
}

function loadSiteOptions(keyword) {
  loadMeta(keyword)
}

function onPhotoChange(file) {
  photoFile.value = file?.raw || null
}

function onPhotoRemove() {
  photoFile.value = null
}

function goBack() {
  router.push('/heritage/inspections')
}

async function submitCreate() {
  if (!form.site_id) {
    ElMessage.warning('请选择巡查文物点')
    return
  }
  if (!photoFile.value) {
    ElMessage.warning('请上传现场照片')
    return
  }

  submitting.value = true
  try {
    const payload = new FormData()
    payload.append('site_id', String(form.site_id))
    if (form.inspector_id) {
      payload.append('inspector_id', String(form.inspector_id))
    }
    payload.append('is_normal', form.is_normal ? 'true' : 'false')
    payload.append('issue_details', form.issue_details || '')
    if (form.longitude !== '') {
      payload.append('longitude', String(form.longitude))
    }
    if (form.latitude !== '') {
      payload.append('latitude', String(form.latitude))
    }
    payload.append('photo', photoFile.value)

    const result = await createInspection(payload)
    if (!result.success) {
      throw new Error(result.message || '创建失败')
    }

    ElMessage.success('巡查记录创建成功')
    router.push('/heritage/inspections')
  } catch (error) {
    ElMessage.error(error?.message || '创建失败')
  } finally {
    submitting.value = false
  }
}

loadMeta()
</script>

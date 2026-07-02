<template>
  <section>
    <header class="page-header">
      <h1>不可移动文物采集</h1>
      <p>现场采集文物基础信息并上传照片，数据进入“采集数据管理”统一维护</p>
    </header>

    <div class="card top-space" style="max-width: 980px">
      <el-form label-width="120px" label-position="left">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="文物名称" required>
              <el-input v-model="form.name" placeholder="请输入文物名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采集编号">
              <el-input v-model="form.survey_code" placeholder="留空自动生成" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="曾用名/别名">
              <el-input v-model="form.former_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="时代" required>
              <el-input v-model="form.era" placeholder="如 汉、唐宋、近现代" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="文物类别" required>
              <el-select v-model="form.category" style="width: 100%" placeholder="请选择文物类别">
                <el-option v-for="item in options.category_choices" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="文物类型">
              <el-select v-model="form.heritage_type" style="width: 100%" filterable clearable placeholder="可选">
                <el-option v-for="item in options.heritage_type_choices" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="省/自治区" required>
              <el-input v-model="form.province" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="市/州">
              <el-input v-model="form.city" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="县/区">
              <el-input v-model="form.county" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="乡镇/街道">
              <el-input v-model="form.township" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="村/社区">
              <el-input v-model="form.village" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="详细地址" required>
          <el-input v-model="form.address" />
        </el-form-item>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="经度" required>
              <el-input v-model="form.longitude" placeholder="如 90.335167" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="纬度" required>
              <el-input v-model="form.latitude" placeholder="如 42.870531" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="坐标系">
              <el-select v-model="form.coordinate_system" style="width: 100%">
                <el-option v-for="item in options.coordinate_system_choices" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="海拔(m)">
              <el-input v-model="form.altitude" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="面积(㎡)">
              <el-input v-model="form.area" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="保护级别">
              <el-select v-model="form.protection_level" style="width: 100%">
                <el-option v-for="item in options.protection_level_choices" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保存现状">
              <el-select v-model="form.preservation_status" style="width: 100%">
                <el-option v-for="item in options.preservation_status_choices" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="权属">
              <el-select v-model="form.ownership" style="width: 100%">
                <el-option v-for="item in options.ownership_choices" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="管理责任人">
              <el-input v-model="form.manager" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="文物简介">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>

        <el-form-item label="上传照片">
          <el-upload
            :auto-upload="false"
            list-type="picture"
            :file-list="photoList"
            :on-change="onPhotoChange"
            :on-remove="onPhotoRemove"
            multiple
            accept="image/*"
          >
            <el-button type="primary" plain>选择照片</el-button>
            <template #tip>
              <div class="el-upload__tip">可选，支持多张；首张会设为封面</div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submitCollect">提交采集</el-button>
          <el-button @click="goManage">查看采集数据管理</el-button>
        </el-form-item>
      </el-form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { createImmovableCollect, fetchImmovableCollectMeta } from '../../api/heritageApi'

const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const photoList = ref([])
const photoRawFiles = ref([])

const options = reactive({
  category_choices: [],
  heritage_type_choices: [],
  coordinate_system_choices: [],
  protection_level_choices: [],
  ownership_choices: [],
  preservation_status_choices: []
})

const form = reactive({
  survey_code: '',
  name: '',
  former_name: '',
  era: '',
  category: '',
  heritage_type: '',
  province: '',
  city: '',
  county: '',
  township: '',
  village: '',
  address: '',
  longitude: '',
  latitude: '',
  coordinate_system: 'CGCS2000',
  altitude: '',
  area: '',
  preservation_status: '一般',
  protection_level: 'DS',
  ownership: 'state',
  manager: '',
  description: ''
})

function onPhotoChange(file, files) {
  photoList.value = files
  photoRawFiles.value = files.map((item) => item.raw).filter(Boolean)
}

function onPhotoRemove(_file, files) {
  photoList.value = files
  photoRawFiles.value = files.map((item) => item.raw).filter(Boolean)
}

function goManage() {
  router.push('/collect/records')
}

async function loadMeta() {
  loading.value = true
  try {
    const result = await fetchImmovableCollectMeta()
    if (!result.success) {
      throw new Error(result.message || '加载采集配置失败')
    }
    Object.assign(options, result.data || {})
    const defaults = result.data?.defaults || {}
    Object.assign(form, {
      coordinate_system: defaults.coordinate_system || form.coordinate_system,
      protection_level: defaults.protection_level || form.protection_level,
      ownership: defaults.ownership || form.ownership,
      preservation_status: defaults.preservation_status || form.preservation_status,
      province: defaults.province || form.province,
      city: defaults.city || form.city,
      county: defaults.county || form.county
    })
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function submitCollect() {
  if (!form.name || !form.era || !form.category || !form.address || !form.province) {
    ElMessage.warning('请先补齐必填项：文物名称、时代、文物类别、省级行政区、详细地址')
    return
  }
  if (form.longitude === '' || form.latitude === '') {
    ElMessage.warning('请填写经纬度')
    return
  }

  submitting.value = true
  try {
    const payload = new FormData()
    Object.entries(form).forEach(([key, value]) => {
      payload.append(key, value ?? '')
    })
    photoRawFiles.value.forEach((file) => {
      payload.append('photos', file)
    })

    const result = await createImmovableCollect(payload)
    if (!result.success) {
      throw new Error(result.message || '提交失败')
    }

    ElMessage.success(`采集成功：${result.data?.name || ''}`)
    router.push('/collect/records')
  } catch (error) {
    ElMessage.error(error?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

loadMeta()
</script>

<template>
  <section>
    <header class="page-header">
      <h1>新建用地项目</h1>
      <p>收文登记，数据直接写入现有项目审批流程</p>
    </header>

    <div class="card form-card">
      <el-form label-width="120px" @submit.prevent>
        <el-form-item label="项目名称">
          <el-input v-model="form.project_name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="企业单位">
          <el-input v-model="form.company_name" placeholder="请输入企业单位名称" />
        </el-form-item>
        <el-form-item label="来函日期">
          <el-date-picker
            v-model="form.incoming_doc_date"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            placeholder="选择来函日期"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submitForm">创建并进入详情</el-button>
          <el-button @click="goBack">返回</el-button>
        </el-form-item>
      </el-form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { createProject } from '../../api/projectApi'

const router = useRouter()
const submitting = ref(false)
const form = reactive({
  project_name: '',
  company_name: '',
  incoming_doc_date: ''
})

function goBack() {
  router.push('/projects')
}

async function submitForm() {
  if (!form.project_name || !form.company_name || !form.incoming_doc_date) {
    ElMessage.warning('请完整填写项目名称、企业单位和来函日期')
    return
  }

  submitting.value = true
  try {
    const result = await createProject({
      project_name: form.project_name,
      company_name: form.company_name,
      incoming_doc_date: form.incoming_doc_date
    })
    if (!result.success) {
      throw new Error(result.message || '创建失败')
    }
    ElMessage.success('创建成功')
    router.push(`/projects/${result.project_id}`)
  } catch (error) {
    ElMessage.error(error?.message || '创建失败')
  } finally {
    submitting.value = false
  }
}
</script>

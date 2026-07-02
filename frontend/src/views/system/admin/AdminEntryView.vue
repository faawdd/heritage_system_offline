<template>
  <section class="admin-entry-page card">
    <h1>后台管理跳转中</h1>
    <p v-if="loading">正在校验当前登录状态并进入 Django 后台...</p>
    <p v-else-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    <div class="top-space" v-if="errorMessage">
      <el-button type="primary" @click="retry">重试</el-button>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { enterDjangoAdmin } from '../../../api/system/systemApi'

const loading = ref(false)
const errorMessage = ref('')

async function jumpToAdmin() {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await enterDjangoAdmin()
    if (!result.success) {
      throw new Error(result.message || '进入后台失败')
    }

    const redirectUrl = result.data?.redirect_url || '/admin/home/'
    window.location.href = redirectUrl
  } catch (error) {
    errorMessage.value = error?.message || '进入后台失败'
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function retry() {
  jumpToAdmin()
}

jumpToAdmin()
</script>

<style scoped>
.admin-entry-page {
  max-width: 720px;
  margin: 24px auto;
}

.error-text {
  color: #d93025;
}
</style>

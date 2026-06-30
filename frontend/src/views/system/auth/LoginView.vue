<template>
  <section class="system-login-page">
    <div class="system-login-card card">
      <h1>系统登录</h1>
      <p>请使用管理账号登录基层文物综合管理平台</p>

      <el-form label-position="top" @submit.prevent>
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
            @keyup.enter="submitLogin"
          />
        </el-form-item>

        <el-button type="primary" :loading="loading" style="width: 100%" @click="submitLogin">
          登录
        </el-button>
      </el-form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../../../stores/system/authStore'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loading = ref(false)
const form = reactive({
  username: '',
  password: ''
})

async function submitLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    const redirect = route.query.redirect || '/dashboard'
    await router.replace(String(redirect))
  } catch (error) {
    ElMessage.error(error?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.system-login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.system-login-card {
  width: 100%;
  max-width: 420px;
}

.system-login-card h1 {
  margin: 0;
  font-size: 24px;
}

.system-login-card p {
  margin: 8px 0 18px;
  color: var(--muted);
}
</style>

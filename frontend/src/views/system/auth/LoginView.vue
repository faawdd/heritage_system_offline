<template>
  <section class="heritage-login-page">
    <header class="login-header">
      <h1>鄯善县文物综合管理平台</h1>
      <p>Django + Vue 一体化管理入口</p>
    </header>

    <div class="login-shell" role="main">
      <div class="login-form-panel">
        <div class="panel-brand">
          <span class="brand-dot"></span>
          <span class="brand-text">HERITAGE CONTROL CENTER</span>
        </div>

        <h2>登录系统</h2>
        <p class="panel-desc">请使用管理员或授权账户登录平台。</p>

        <el-form class="login-form" @submit.prevent>
          <el-form-item>
            <el-input
              v-model="form.username"
              placeholder="用户名"
              size="large"
              @keyup.enter="submitLogin"
            >
              <template #prefix>
                <span class="input-icon">账号</span>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item>
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              show-password
              size="large"
              @keyup.enter="submitLogin"
            >
              <template #prefix>
                <span class="input-icon">密钥</span>
              </template>
            </el-input>
          </el-form-item>

          <el-button
            class="login-btn"
            type="primary"
            :loading="loading"
            @click="submitLogin"
          >
            进入控制台
          </el-button>
        </el-form>

        <div class="panel-footnote">
          <span>建议使用 Chrome / Edge 最新版本访问</span>
          <span>如无法登录，请联系系统管理员</span>
        </div>
      </div>

      <aside class="login-visual-panel" aria-hidden="true">
        <div class="visual-badge">文物保护 · 数字治理</div>
        <div class="visual-title">守护文化遗产</div>
        <p class="visual-subtitle">巡查、研判、审批一体化协同。</p>

        <div class="version-pill">
          <span>系统版本</span>
          <strong>v{{ versionText }}</strong>
        </div>

        <div class="heritage-icons">
          <div class="icon-card icon-guard" title="安全巡查"></div>
          <div class="icon-card icon-relic" title="文物档案"></div>
          <div class="icon-card icon-map" title="一张图定位"></div>
        </div>

        <div class="visual-deco visual-deco-a"></div>
        <div class="visual-deco visual-deco-b"></div>
      </aside>
    </div>

    <footer class="login-footer">© {{ new Date().getFullYear() }} 鄯善县文物综合管理平台</footer>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchSystemVersion } from '../../../api/dashboardApi'
import { useAuthStore } from '../../../stores/system/authStore'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loading = ref(false)
const versionText = ref('-')
const form = reactive({
  username: '',
  password: ''
})

async function loadVersion() {
  try {
    const versionRes = await fetchSystemVersion()
    versionText.value = versionRes?.data?.version || '-'
  } catch (_error) {
    versionText.value = '-'
  }
}

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

onMounted(() => {
  loadVersion()
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;800&display=swap');

.heritage-login-page {
  min-height: 100vh;
  padding: 26px 18px 14px;
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 14px;
  background:
    radial-gradient(circle at 12% 18%, rgba(14, 165, 233, 0.2) 0, rgba(14, 165, 233, 0) 42%),
    radial-gradient(circle at 88% 82%, rgba(59, 130, 246, 0.2) 0, rgba(59, 130, 246, 0) 40%),
    linear-gradient(135deg, #0b5cab 0%, #1b7fd8 48%, #0ea5e9 100%);
  font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
}

.login-header {
  text-align: center;
  color: #f1f7ff;
}

.login-header h1 {
  margin: 0;
  font-size: clamp(22px, 2.9vw, 32px);
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: 0.8px;
}

.login-header p {
  margin: 8px 0 0;
  color: rgba(241, 247, 255, 0.86);
  font-size: 13px;
}

.login-shell {
  width: min(900px, 100%);
  margin: 0 auto;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 14px 34px rgba(5, 23, 52, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.09);
  display: grid;
  grid-template-columns: 1.08fr 0.92fr;
}

.login-form-panel {
  padding: clamp(20px, 3.2vw, 30px);
  background: rgba(255, 255, 255, 0.96);
  display: flex;
  flex-direction: column;
}

.panel-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #0f3e6e;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.7px;
}

.brand-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0ea5e9, #1d4ed8);
}

.panel-brand .brand-text {
  opacity: 0.85;
}

.login-form-panel h2 {
  margin: 12px 0 6px;
  font-size: clamp(22px, 2.9vw, 30px);
  color: #102a43;
  font-weight: 800;
}

.panel-desc {
  margin: 0;
  color: #5d748f;
  line-height: 1.6;
  font-size: 13px;
}

.login-form {
  margin-top: 18px;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: 30px;
  padding: 1px 16px;
  box-shadow: 0 0 0 1px #d6e3f2 inset;
  background: #f7fbff;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1.4px #1d74c7 inset;
  background: #ffffff;
}

.input-icon {
  font-size: 11px;
  color: #5d748f;
  letter-spacing: 0.5px;
}

.login-btn {
  width: 100%;
  margin-top: 6px;
  height: 42px;
  border-radius: 30px;
  border: none;
  background: linear-gradient(90deg, #0b67bd 0%, #1492e6 100%);
  box-shadow: 0 10px 20px rgba(13, 116, 194, 0.28);
  font-size: 15px;
  font-weight: 700;
}

.login-btn:hover {
  filter: brightness(1.06);
}

.panel-footnote {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: #7388a0;
  font-size: 12px;
}

.login-visual-panel {
  position: relative;
  background: linear-gradient(155deg, rgba(10, 44, 86, 0.85), rgba(20, 109, 184, 0.82));
  padding: clamp(18px, 2.8vw, 26px);
  color: #f1f8ff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}

.visual-badge {
  width: fit-content;
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  font-size: 12px;
  letter-spacing: 0.4px;
}

.visual-title {
  margin-top: 14px;
  font-size: clamp(20px, 2.2vw, 28px);
  line-height: 1.3;
  font-weight: 800;
  max-width: 320px;
}

.visual-subtitle {
  margin: 8px 0 0;
  font-size: 13px;
  color: rgba(241, 248, 255, 0.88);
}

.version-pill {
  margin-top: 14px;
  width: fit-content;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  font-size: 12px;
}

.version-pill strong {
  font-size: 13px;
  letter-spacing: 0.3px;
}

.heritage-icons {
  margin-top: 16px;
  display: flex;
  gap: 10px;
}

.icon-card {
  width: 64px;
  height: 64px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.22);
  position: relative;
}

.icon-guard::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 12px;
  width: 22px;
  height: 28px;
  transform: translateX(-50%);
  background: rgba(241, 248, 255, 0.9);
  clip-path: polygon(50% 0%, 100% 15%, 88% 80%, 50% 100%, 12% 80%, 0% 15%);
}

.icon-relic::before,
.icon-relic::after {
  content: '';
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(241, 248, 255, 0.9);
  border-radius: 2px;
}

.icon-relic::before {
  top: 14px;
  width: 28px;
  height: 6px;
}

.icon-relic::after {
  top: 24px;
  width: 36px;
  height: 24px;
  clip-path: polygon(12% 100%, 20% 18%, 32% 18%, 28% 100%, 44% 100%, 48% 18%, 60% 18%, 56% 100%, 72% 100%, 80% 18%, 90% 18%, 88% 100%);
}

.icon-map::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 12px;
  width: 24px;
  height: 32px;
  transform: translateX(-50%);
  background: rgba(241, 248, 255, 0.9);
  border-radius: 50% 50% 50% 50% / 42% 42% 58% 58%;
  clip-path: polygon(50% 0%, 85% 22%, 86% 56%, 50% 100%, 14% 56%, 15% 22%);
}

.icon-map::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 23px;
  width: 8px;
  height: 8px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: rgba(17, 83, 143, 0.95);
}

.visual-deco {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.visual-deco-a {
  width: 150px;
  height: 150px;
  right: -38px;
  top: -42px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.2) 0%, rgba(255, 255, 255, 0) 70%);
}

.visual-deco-b {
  width: 170px;
  height: 170px;
  left: -72px;
  bottom: -78px;
  background: radial-gradient(circle, rgba(14, 165, 233, 0.35) 0%, rgba(14, 165, 233, 0) 72%);
}

.login-footer {
  text-align: center;
  color: rgba(241, 247, 255, 0.78);
  font-size: 12px;
}

@media (max-width: 980px) {
  .heritage-login-page {
    padding: 16px 10px 10px;
  }

  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-visual-panel {
    min-height: 220px;
  }
}

@media (max-width: 640px) {
  .login-header h1 {
    font-size: 21px;
  }

  .login-header p {
    font-size: 12px;
  }

  .login-form-panel {
    padding: 18px 14px;
  }

  .visual-title {
    font-size: 22px;
  }

  .heritage-icons {
    gap: 8px;
  }

  .icon-card {
    width: 56px;
    height: 56px;
  }
}
</style>

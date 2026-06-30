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
        <p class="panel-desc">请使用管理员或授权账户登录，进入项目审批、巡查、KML叠加检查和文物一张图模块。</p>

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
        <div class="visual-badge">文化遗产 · 安全巡查 · 空间研判</div>
        <div class="visual-title">让文物管理从“台账”走向“数据驾驶舱”</div>
        <div class="visual-grid">
          <div class="visual-card">
            <strong>项目审批</strong>
            <span>流程节点可追溯</span>
          </div>
          <div class="visual-card">
            <strong>巡查治理</strong>
            <span>异常风险快速闭环</span>
          </div>
          <div class="visual-card">
            <strong>KML叠加</strong>
            <span>冲突点高亮与分析</span>
          </div>
          <div class="visual-card">
            <strong>一张图</strong>
            <span>文物点位全局掌控</span>
          </div>
        </div>

        <div class="visual-deco visual-deco-a"></div>
        <div class="visual-deco visual-deco-b"></div>
      </aside>
    </div>

    <footer class="login-footer">© {{ new Date().getFullYear() }} 鄯善县文物综合管理平台</footer>
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
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;800&display=swap');

.heritage-login-page {
  min-height: 100vh;
  padding: 38px 22px 20px;
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 18px;
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
  font-size: clamp(24px, 3.2vw, 36px);
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: 0.8px;
}

.login-header p {
  margin: 8px 0 0;
  color: rgba(241, 247, 255, 0.86);
  font-size: 14px;
}

.login-shell {
  width: min(1060px, 100%);
  margin: 0 auto;
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 20px 48px rgba(5, 23, 52, 0.34);
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.09);
  display: grid;
  grid-template-columns: 1.04fr 1fr;
}

.login-form-panel {
  padding: clamp(24px, 4vw, 42px);
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
  margin: 14px 0 8px;
  font-size: clamp(24px, 3.2vw, 34px);
  color: #102a43;
  font-weight: 800;
}

.panel-desc {
  margin: 0;
  color: #5d748f;
  line-height: 1.7;
  font-size: 14px;
}

.login-form {
  margin-top: 24px;
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
  height: 46px;
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
  margin-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: #7388a0;
  font-size: 12px;
}

.login-visual-panel {
  position: relative;
  background: linear-gradient(155deg, rgba(10, 44, 86, 0.85), rgba(20, 109, 184, 0.82));
  padding: clamp(22px, 3.4vw, 34px);
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
  margin-top: 16px;
  font-size: clamp(22px, 2.8vw, 34px);
  line-height: 1.35;
  font-weight: 800;
  max-width: 460px;
}

.visual-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.visual-card {
  border-radius: 12px;
  padding: 12px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(2px);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.visual-card strong {
  font-size: 14px;
  font-weight: 700;
}

.visual-card span {
  font-size: 12px;
  color: rgba(241, 248, 255, 0.86);
}

.visual-deco {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.visual-deco-a {
  width: 210px;
  height: 210px;
  right: -54px;
  top: -64px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.2) 0%, rgba(255, 255, 255, 0) 70%);
}

.visual-deco-b {
  width: 240px;
  height: 240px;
  left: -88px;
  bottom: -98px;
  background: radial-gradient(circle, rgba(14, 165, 233, 0.35) 0%, rgba(14, 165, 233, 0) 72%);
}

.login-footer {
  text-align: center;
  color: rgba(241, 247, 255, 0.78);
  font-size: 12px;
}

@media (max-width: 980px) {
  .heritage-login-page {
    padding: 18px 12px 12px;
  }

  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-visual-panel {
    min-height: 260px;
  }

  .visual-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .login-header h1 {
    font-size: 22px;
  }

  .login-header p {
    font-size: 13px;
  }

  .login-form-panel {
    padding: 20px 16px;
  }

  .visual-title {
    font-size: 22px;
  }

  .visual-grid {
    grid-template-columns: 1fr;
  }
}
</style>

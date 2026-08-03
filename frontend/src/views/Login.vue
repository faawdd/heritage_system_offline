<template>
  <section class="desktop-login-shell">
    <article class="login-window">
      <header class="window-header">
        <span>基层文物管理系统</span>
        <button
          class="window-close-btn"
          type="button"
          :disabled="loading"
          @click="handleCloseWindow"
          aria-label="关闭窗口"
        >
          ×
        </button>
      </header>

      <div class="window-body">
        <img :src="appLogo" alt="基层文物管理系统 Logo" class="app-logo">
        <h1 class="title">基层文物管理系统</h1>
        <p class="subtitle">离线桌面版登录</p>

        <form class="login-form" @submit.prevent="handleLogin">
          <label class="field-label" for="username">用户名</label>
          <input
            id="username"
            v-model.trim="form.username"
            class="field-input"
            type="text"
            name="username"
            autocomplete="username"
            placeholder="例如：test"
            :disabled="loading"
            required
            autofocus
          >

          <label class="field-label" for="password">密码</label>
          <input
            id="password"
            v-model="form.password"
            class="field-input"
            :type="showPassword ? 'text' : 'password'"
            name="password"
            autocomplete="current-password"
            placeholder="请输入密码"
            :disabled="loading"
            required
          >

          <div class="option-row">
            <label class="checkbox-item"><input v-model="rememberPassword" type="checkbox" :disabled="loading"><span>记住密码</span></label>
            <label class="checkbox-item"><input v-model="showPassword" type="checkbox" :disabled="loading"><span>显示密码</span></label>
          </div>

          <p v-if="errorMessage" class="error-box">{{ errorMessage }}</p>

          <button class="login-btn" type="submit" :disabled="loading">
            <span v-if="loading" class="loading-dot" aria-hidden="true"></span>
            {{ loading ? '登录校验中...' : '登 录' }}
          </button>
        </form>
      </div>
    </article>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import appLogo from '../assets/logo.png'

const router = useRouter()
const SAVED_LOGIN_KEY = 'desktop_saved_login_credential'

const loading = ref(false)
const showPassword = ref(false)
const rememberPassword = ref(true)
const errorMessage = ref('')
const form = reactive({
  username: '',
  password: ''
})

onMounted(() => {
  try {
    const raw = localStorage.getItem(SAVED_LOGIN_KEY)
    if (!raw) {
      return
    }
    const saved = JSON.parse(raw)
    const savedUsername = String(saved?.username || '').trim()
    const savedPassword = String(saved?.password || '')
    if (!savedUsername || !savedPassword) {
      return
    }
    form.username = savedUsername
    form.password = savedPassword
    rememberPassword.value = true
  } catch (_error) {
    localStorage.removeItem(SAVED_LOGIN_KEY)
  }
})

async function handleLogin() {
  errorMessage.value = ''

  if (!form.username || !form.password) {
    errorMessage.value = '请输入完整的用户名和密码'
    return
  }

  if (!window.electronAPI || typeof window.electronAPI.login !== 'function') {
    errorMessage.value = '当前环境不支持桌面 IPC 登录，请检查 Electron 预加载配置。'
    return
  }

  loading.value = true
  try {
    const result = await window.electronAPI.login(form.username, form.password)
    if (!result?.success) {
      errorMessage.value = result?.message || '登录失败，请重试'
      return
    }

    if (rememberPassword.value) {
      localStorage.setItem(
        SAVED_LOGIN_KEY,
        JSON.stringify({
          username: String(form.username || '').trim(),
          password: String(form.password || '')
        })
      )
    } else {
      localStorage.removeItem(SAVED_LOGIN_KEY)
    }

    // 标记当前窗口会话登录成功，供路由守卫放行。
    sessionStorage.setItem('desktop_local_auth', '1')
    localStorage.removeItem('desktop_local_auth')

    // 兜底跳转：若主进程未切窗，也可在当前窗口进入主页。
    await router.replace('/dashboard?desktop_auth=1')
  } catch (error) {
    errorMessage.value = String(error?.message || '登录通信失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

async function handleCloseWindow() {
  if (!window.electronAPI || typeof window.electronAPI.closeLoginWindow !== 'function') {
    window.close()
    return
  }

  try {
    await window.electronAPI.closeLoginWindow()
  } catch (_error) {
    window.close()
  }
}
</script>

<style scoped>
* {
  box-sizing: border-box;
}

:global(html),
:global(body),
:global(#app) {
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
}

.desktop-login-shell {
  height: 100vh;
  min-height: 100vh;
  background: #f5f5f5;
  padding: 0;
  font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

.login-window {
  width: 100%;
  height: 100%;
  border-radius: 0;
  overflow: hidden;
  background: #f5f5f5;
  border: none;
  box-shadow: none;
  display: flex;
  flex-direction: column;
}

.window-header {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f7f7f7;
  border-bottom: 1px solid #e5e5e5;
  color: #222222;
  font-size: 14px;
  font-weight: 500;
  position: relative;
}

.window-close-btn {
  position: absolute;
  top: 8px;
  right: 10px;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #9b9b9b;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.window-close-btn:hover {
  background: #e81123;
  color: #ffffff;
}

.window-close-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.window-body {
  display: flex;
  flex-direction: column;
  width: min(360px, 100%);
  margin: auto;
  padding: 12px 24px 26px;
}

.app-logo {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  margin: 0 auto 14px;
  object-fit: cover;
}

.title {
  text-align: center;
  margin: 0 0 6px;
  font-size: 22px;
  line-height: 1.3;
  color: #1f1f1f;
  font-weight: 600;
}

.subtitle {
  margin: 0 0 20px;
  text-align: center;
  font-size: 13px;
  color: #8c8c8c;
}

.login-form {
  display: flex;
  flex-direction: column;
}

.field-label {
  margin-bottom: 6px;
  color: #6f6f6f;
  font-size: 12px;
  font-weight: 500;
}

.field-input {
  height: 44px;
  border: none;
  border-bottom: 1px solid #d8d8d8;
  background: transparent;
  padding: 0 2px;
  outline: none;
  font-size: 14px;
  color: #222222;
  margin-bottom: 12px;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.field-input:focus {
  border-color: #07c160;
  box-shadow: none;
}

.field-input:disabled {
  opacity: 0.75;
}

.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #6f6f6f;
  font-size: 12px;
  margin-bottom: 14px;
}

.checkbox-item input {
  accent-color: #07c160;
}

.checkbox-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.error-box {
  margin: 0 0 10px;
  border: none;
  background: transparent;
  color: #d44949;
  padding: 0;
  font-size: 12px;
  line-height: 1.4;
}

.login-btn {
  height: 44px;
  border: 0;
  border-radius: 6px;
  background: #07c160;
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  transition: background-color 0.16s ease, opacity 0.2s ease;
}

.login-btn:hover {
  background: #06ad56;
}

.login-btn:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.loading-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.52);
  border-top-color: #ffffff;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>

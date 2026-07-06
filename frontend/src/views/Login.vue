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
        <h1 class="title">欢迎登录</h1>
        <p class="subtitle">离线桌面版</p>

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
  display: grid;
  place-items: center;
  background: var(--bg-gradient, radial-gradient(circle at 0% 0%, #dbeeff 0, transparent 44%)), var(--bg, #edf5ff);
  position: relative;
  overflow: hidden;
  padding: 0;
  font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

.login-window {
  width: 100vw;
  height: 100vh;
  border-radius: 0;
  overflow: hidden;
  background: color-mix(in srgb, var(--surface, #ffffff) 94%, #eaf3ff 6%);
  border: none;
  box-shadow: none;
  display: flex;
  flex-direction: column;
}

.window-header {
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #f4f9ff 0%, #e8f2ff 100%);
  border-bottom: 1px solid var(--line, #d7e6f8);
  color: var(--text, #163a60);
  font-size: 14px;
  font-weight: 600;
  position: relative;
}

.window-close-btn {
  position: absolute;
  top: 7px;
  right: 10px;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted, #5f7898);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.window-close-btn:hover {
  background: rgba(128, 176, 229, 0.18);
  color: var(--text, #163a60);
}

.window-close-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.window-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 360px;
  width: 100%;
  margin: 0 auto;
  padding: 24px 20px;
}

.title {
  text-align: center;
  margin: 0 0 4px;
  font-size: 22px;
  line-height: 1.2;
  color: var(--text, #163a60);
  font-weight: 600;
}

.subtitle {
  margin: 0 0 18px;
  text-align: center;
  font-size: 12px;
  color: var(--muted, #5f7898);
}

.login-form {
  display: flex;
  flex-direction: column;
}

.field-label {
  margin-bottom: 6px;
  color: #466a93;
  font-size: 12px;
  font-weight: 600;
}

.field-input {
  height: 42px;
  border-radius: 7px;
  border: 1px solid var(--line, #d7e6f8);
  background: var(--surface, #ffffff);
  padding: 0 12px;
  outline: none;
  font-size: 14px;
  color: var(--text, #163a60);
  margin-bottom: 12px;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}

.field-input:focus {
  border-color: var(--accent, #66adff);
  box-shadow: 0 0 0 2px rgba(102, 173, 255, 0.2);
}

.field-input:disabled {
  opacity: 0.75;
}

.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--muted, #5f7898);
  font-size: 12px;
  margin-bottom: 10px;
}

.checkbox-item input {
  accent-color: var(--accent, #66adff);
}

.checkbox-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.error-box {
  margin: 0 0 10px;
  border-radius: 7px;
  border: 1px solid #f1c0c0;
  background: #fff4f4;
  color: #d64c4c;
  padding: 9px 10px;
  font-size: 12px;
  line-height: 1.4;
}

.login-btn {
  height: 42px;
  border: 0;
  border-radius: 7px;
  background: linear-gradient(180deg, #72b6ff 0%, #66adff 100%);
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  box-shadow: none;
  transition: background-color 0.16s ease, opacity 0.2s ease;
}

.login-btn:hover {
  background: linear-gradient(180deg, #5ea9fb 0%, #4f9cf6 100%);
}

.login-btn:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.loading-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.5);
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

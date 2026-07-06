<template>
  <section class="login-shell">
    <div class="ambient ambient-left"></div>
    <div class="ambient ambient-right"></div>

    <article class="qq-login-card">
      <header class="window-titlebar">
        <div class="window-brand">
          <span class="brand-dot" aria-hidden="true"></span>
          <span class="brand-text">{{ systemName }}</span>
        </div>
        <span class="offline-badge">离线模式</span>
      </header>

      <div class="login-body">
        <div class="avatar-wrap" aria-hidden="true">
          <div class="avatar-ring"></div>
          <div class="avatar-face">{{ avatarText }}</div>
        </div>

        <h1 class="title">欢迎登录</h1>
        <p class="subtitle">基层文物管理系统 · 桌面版</p>

        <form class="login-form" @submit.prevent="submitLogin">
          <div class="field-group" ref="accountPanelRef">
            <div class="input-wrap">
              <span class="field-icon" aria-hidden="true">👤</span>
              <input
                v-model.trim="form.username"
                type="text"
                class="field-input"
                name="username"
                placeholder="请输入账号"
                autocomplete="username"
                required
                autofocus
                @focus="showAccountPanel = true"
              >
              <button
                v-if="savedAccounts.length > 0"
                class="picker-trigger"
                type="button"
                @click="toggleAccountPanel"
                aria-label="显示已保存账号"
              >
                ▼
              </button>
            </div>

            <transition name="fade-slide">
              <ul v-if="showAccountPanel && filteredAccounts.length > 0" class="account-panel">
                <li
                  v-for="account in filteredAccounts"
                  :key="account.username"
                  class="account-item"
                  @click="selectSavedAccount(account)"
                >
                  <span class="account-name">{{ account.username }}</span>
                  <button
                    class="account-remove"
                    type="button"
                    @click.stop="removeAccount(account.username)"
                    aria-label="删除账号"
                  >
                    删除
                  </button>
                </li>
              </ul>
            </transition>
          </div>

          <div class="input-wrap">
            <span class="field-icon" aria-hidden="true">🔒</span>
            <input
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              class="field-input"
              name="password"
              placeholder="请输入密码"
              autocomplete="current-password"
              required
            >
            <button
              class="picker-trigger"
              type="button"
              @click="showPassword = !showPassword"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
            >
              {{ showPassword ? '隐藏' : '显示' }}
            </button>
          </div>

          <div class="form-tools">
            <label class="remember-row">
              <input v-model="rememberPassword" type="checkbox" class="remember-checkbox">
              <span class="remember-indicator" aria-hidden="true"></span>
              <span class="remember-text">记住密码</span>
            </label>
            <span class="status-dot">
              本地引擎运行中
            </span>
          </div>

          <p v-if="errorMessage" class="login-error">{{ errorMessage }}</p>

          <button class="login-btn" type="submit" :disabled="loading">
            {{ loading ? '正在登录...' : '登 录' }}
          </button>
        </form>

        <footer class="card-footer">
          <span>联系管理员获取账户权限</span>
          <span>© {{ currentYear }}</span>
        </footer>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAppStore } from '../../../stores/system/appStore'
import { useAuthStore } from '../../../stores/system/authStore'

const SAVED_ACCOUNTS_KEY = 'heritage_saved_accounts'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()
const authStore = useAuthStore()

const loading = ref(false)
const rememberPassword = ref(true)
const errorMessage = ref('')
const showPassword = ref(false)
const showAccountPanel = ref(false)
const accountPanelRef = ref(null)
const savedAccounts = ref(loadSavedAccounts())
const form = reactive({
  username: '',
  password: ''
})

const systemName = computed(() => appStore.systemName || '基层文物管理系统')
const currentYear = computed(() => new Date().getFullYear())
const avatarText = computed(() => {
  const username = String(form.username || '').trim()
  if (!username) {
    return '文'
  }
  return username.slice(0, 1).toUpperCase()
})

const filteredAccounts = computed(() => {
  const keyword = String(form.username || '').trim().toLowerCase()
  if (!keyword) {
    return savedAccounts.value
  }
  return savedAccounts.value.filter((item) => item.username.toLowerCase().includes(keyword))
})

function loadSavedAccounts() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SAVED_ACCOUNTS_KEY) || '[]')
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed
      .map((item) => ({
        username: String(item?.username || '').trim(),
        password: String(item?.password || ''),
        lastUsedAt: String(item?.lastUsedAt || '')
      }))
      .filter((item) => item.username)
      .sort((left, right) => String(right.lastUsedAt || '').localeCompare(String(left.lastUsedAt || '')))
  } catch (_error) {
    return []
  }
}

function persistSavedAccounts(accounts) {
  const normalized = (accounts || [])
    .filter((item) => item?.username)
    .slice(0, 8)
  savedAccounts.value = normalized
  localStorage.setItem(SAVED_ACCOUNTS_KEY, JSON.stringify(normalized))
}

function saveCurrentAccount() {
  const username = String(form.username || '').trim()
  if (!username) {
    return
  }

  const nextAccounts = savedAccounts.value.filter((item) => item.username !== username)
  if (rememberPassword.value) {
    nextAccounts.unshift({
      username,
      password: String(form.password || ''),
      lastUsedAt: new Date().toISOString()
    })
  }
  persistSavedAccounts(nextAccounts)
}

function selectSavedAccount(account) {
  form.username = account.username
  form.password = account.password || ''
  rememberPassword.value = Boolean(account.password)
  errorMessage.value = ''
  showAccountPanel.value = false
}

function removeAccount(username) {
  const nextAccounts = savedAccounts.value.filter((item) => item.username !== username)
  persistSavedAccounts(nextAccounts)
  if (form.username === username) {
    form.password = ''
    rememberPassword.value = false
  }
}

function toggleAccountPanel() {
  showAccountPanel.value = !showAccountPanel.value
}

function handleDocumentClick(event) {
  if (!accountPanelRef.value) {
    return
  }
  if (!accountPanelRef.value.contains(event.target)) {
    showAccountPanel.value = false
  }
}

watch(
  () => form.username,
  () => {
    errorMessage.value = ''
  }
)

watch(
  () => form.password,
  () => {
    errorMessage.value = ''
  }
)

onMounted(() => {
  appStore.initialize()
  document.addEventListener('click', handleDocumentClick)

  if (savedAccounts.value.length > 0) {
    selectSavedAccount(savedAccounts.value[0])
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})

async function submitLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  errorMessage.value = ''
  try {
    await authStore.login(form.username, form.password)
    saveCurrentAccount()
    ElMessage.success('登录成功')
    const redirect = route.query.redirect || '/dashboard'
    await router.replace(String(redirect))
  } catch (error) {
    errorMessage.value = error?.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
:root {
  color-scheme: light;
}

* {
  box-sizing: border-box;
}

.login-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 16% 18%, rgba(255, 255, 255, 0.42), transparent 34%),
    radial-gradient(circle at 84% 12%, rgba(196, 227, 255, 0.78), transparent 36%),
    linear-gradient(160deg, #8fd1ff 0%, #4ba8f8 42%, #2f8deb 100%);
  padding: 28px;
  position: relative;
  overflow: hidden;
  font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

.ambient {
  position: absolute;
  pointer-events: none;
  border-radius: 50%;
  filter: blur(8px);
}

.ambient-left {
  width: 220px;
  height: 220px;
  left: -68px;
  bottom: 40px;
  background: rgba(255, 255, 255, 0.26);
  animation: float-up 7s ease-in-out infinite;
}

.ambient-right {
  width: 280px;
  height: 280px;
  right: -84px;
  top: 52px;
  background: rgba(178, 222, 255, 0.46);
  animation: float-up 8.6s ease-in-out infinite reverse;
}

.qq-login-card {
  width: min(100%, 428px);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow:
    0 28px 58px rgba(15, 76, 136, 0.28),
    0 6px 16px rgba(13, 61, 106, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
  overflow: hidden;
  backdrop-filter: blur(9px);
  transform: translateY(8px);
  animation: card-enter 0.5s ease forwards;
}

.window-titlebar {
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  background: linear-gradient(180deg, rgba(223, 242, 255, 0.95), rgba(204, 232, 253, 0.9));
  border-bottom: 1px solid rgba(126, 180, 228, 0.42);
}

.window-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #44a6ff, #1f7ee0);
  box-shadow: 0 0 0 3px rgba(69, 163, 255, 0.2);
}

.brand-text {
  font-size: 13px;
  color: #1e4f84;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.offline-badge {
  font-size: 12px;
  color: #205f96;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(107, 166, 219, 0.55);
  border-radius: 999px;
  padding: 2px 9px;
}

.login-body {
  padding: 28px 30px 24px;
}

.avatar-wrap {
  width: 90px;
  height: 90px;
  margin: 0 auto;
  position: relative;
}

.avatar-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(from 110deg, #6ec8ff, #3c9af2, #5ec5ff, #6ec8ff);
  opacity: 0.85;
  animation: spin 5.2s linear infinite;
}

.avatar-face {
  position: absolute;
  inset: 8px;
  border-radius: 50%;
  background: linear-gradient(150deg, #fefefe, #ddf0ff);
  box-shadow: inset 0 0 0 1px rgba(146, 194, 235, 0.6);
  display: grid;
  place-items: center;
  font-size: 32px;
  color: #1f6bb1;
  font-weight: 700;
}

.title {
  margin: 16px 0 4px;
  text-align: center;
  font-size: 24px;
  line-height: 1.2;
  color: #143a67;
  font-weight: 700;
}

.subtitle {
  margin: 0 0 20px;
  text-align: center;
  color: #4b6f96;
  font-size: 13px;
  letter-spacing: 0.3px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-group {
  position: relative;
}

.input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  border-radius: 11px;
  border: 1px solid #b3d8fb;
  background: #f8fcff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
  padding: 0 10px;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.input-wrap:focus-within {
  border-color: #3b95eb;
  box-shadow: 0 0 0 3px rgba(59, 149, 235, 0.15);
}

.field-icon {
  width: 18px;
  text-align: center;
  font-size: 14px;
  opacity: 0.8;
}

.field-input {
  flex: 1;
  border: 0;
  background: transparent;
  height: 42px;
  outline: none;
  color: #184a7d;
  font-size: 14px;
}

.field-input::placeholder {
  color: #89a8c5;
}

.picker-trigger {
  border: 0;
  background: transparent;
  color: #3f7fb7;
  font-size: 12px;
  cursor: pointer;
  height: 28px;
  border-radius: 7px;
  padding: 0 8px;
}

.picker-trigger:hover {
  background: rgba(120, 175, 224, 0.16);
}

.account-panel {
  list-style: none;
  margin: 6px 0 0;
  padding: 6px;
  border-radius: 11px;
  border: 1px solid #b8d8f7;
  background: #ffffff;
  box-shadow: 0 8px 22px rgba(18, 79, 135, 0.14);
  max-height: 164px;
  overflow: auto;
  position: absolute;
  z-index: 12;
  left: 0;
  right: 0;
}

.account-item {
  height: 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 9px;
  color: #1d4f82;
  cursor: pointer;
  font-size: 13px;
}

.account-item:hover {
  background: #edf6ff;
}

.account-name {
  max-width: 80%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-remove {
  border: 0;
  background: transparent;
  color: #6a92ba;
  font-size: 12px;
  cursor: pointer;
  border-radius: 6px;
  padding: 2px 6px;
}

.account-remove:hover {
  color: #e15858;
  background: #ffecee;
}

.form-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  color: #5c7fa3;
}

.remember-row {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
}

.remember-checkbox {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.remember-indicator {
  width: 15px;
  height: 15px;
  border-radius: 5px;
  border: 1px solid #8ebde8;
  background: #eef7ff;
  position: relative;
}

.remember-checkbox:checked + .remember-indicator {
  background: linear-gradient(145deg, #4ea2ef, #2f8ee5);
  border-color: #2f8de4;
}

.remember-checkbox:checked + .remember-indicator::after {
  content: '';
  position: absolute;
  width: 3px;
  height: 7px;
  border-right: 2px solid #ffffff;
  border-bottom: 2px solid #ffffff;
  left: 5px;
  top: 1px;
  transform: rotate(38deg);
}

.status-dot {
  position: relative;
  padding-left: 12px;
}

.status-dot::before {
  content: '';
  position: absolute;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #35bd6d;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  box-shadow: 0 0 0 3px rgba(53, 189, 109, 0.18);
}

.login-error {
  margin: 2px 0 0;
  color: #d64040;
  font-size: 13px;
  line-height: 1.4;
}

.login-btn {
  margin-top: 3px;
  height: 42px;
  border: 0;
  border-radius: 11px;
  background: linear-gradient(160deg, #41a2fa, #2389e6);
  box-shadow: 0 8px 16px rgba(28, 129, 219, 0.3);
  color: #ffffff;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 3px;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.2s ease;
}

.login-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 20px rgba(28, 129, 219, 0.34);
}

.login-btn:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.card-footer {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #7192b4;
  font-size: 12px;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@keyframes float-up {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-12px);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes card-enter {
  from {
    opacity: 0;
    transform: translateY(24px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 540px) {
  .login-shell {
    padding: 16px;
  }

  .login-body {
    padding: 24px 18px 20px;
  }

  .card-footer {
    flex-direction: column;
    gap: 4px;
  }
}
</style>

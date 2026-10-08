<template>
  <section class="w3l-hotair-form desktop-login-shell" :class="{ 'is-electron-login': isDesktop }">
    <h1 v-if="!isDesktop">{{ systemName }}</h1>
    <div class="container">
      <div class="workinghny-form-grid">
        <div class="main-hotair">
          <div class="content-wthree">
            <div v-if="isDesktop" class="desktop-login-brand">
              <img :src="appLogo" alt="" class="desktop-app-logo">
              <h2>欢迎登录</h2>
            </div>
            <template v-else>
              <h2>系统登录</h2>
              <p class="login-subtitle">离线桌面版 · 本机数据安全存储</p>
            </template>
            <form @submit.prevent="submitLogin">
              <input v-model="form.username" type="text" class="text" name="username" placeholder="用户名" required autofocus>
              <input
                v-model="form.password"
                type="password"
                class="password"
                name="password"
                placeholder="密码"
                required
              >
              <button class="btn" type="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
            </form>

            <p v-if="!isDesktop" class="account">如无账号请联系 <a href="javascript:void(0)">系统管理员</a></p>
          </div>
          <div class="w3l_form align-self">
            <div class="left_grid_info">
              <img :src="loginIllustration" alt="登录插图" class="img-fluid">
            </div>
          </div>
        </div>
      </div>
    </div>
    <el-dialog
      v-model="passwordChangeRequired"
      title="首次登录，请先修改密码"
      width="420px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <p class="password-notice">为保护本机数据，请设置新的管理员密码后继续使用系统。</p>
      <form class="password-change-form" @submit.prevent="submitRequiredPasswordChange">
        <input v-model="passwordChangeForm.currentPassword" type="password" autocomplete="current-password" placeholder="当前密码" required>
        <input v-model="passwordChangeForm.newPassword" type="password" autocomplete="new-password" placeholder="新密码，至少 8 位" minlength="8" required>
        <input v-model="passwordChangeForm.confirmPassword" type="password" autocomplete="new-password" placeholder="再次输入新密码" minlength="8" required>
        <button class="password-change-button" type="submit" :disabled="loading">
          {{ loading ? '正在更新...' : '修改密码并继续' }}
        </button>
      </form>
    </el-dialog>
    <div v-if="!isDesktop" class="copyright text-center">
      <p class="copy-footer-29">© {{ new Date().getFullYear() }} {{ systemName }}。保留所有权利</p>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import loginIllustration from '../../../assets/login-illustration.png'
import appLogo from '../../../assets/logo.png'
import { changeSystemPassword } from '../../../api/system/systemApi'
import { useAuthStore } from '../../../stores/system/authStore'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const isDesktop = window.desktopMeta?.runtime === 'electron'
const defaultSystemName = isDesktop
  ? '文物综合管理平台'
  : '鄯善县文物综合管理平台'
const systemName = computed(() => String(route.query.system_name || defaultSystemName))

const loading = ref(false)
const passwordChangeRequired = ref(false)
const form = reactive({
  username: '',
  password: ''
})
const passwordChangeForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

onMounted(() => {
  localStorage.setItem('heritage_system_name', systemName.value)
  if (authStore.isAuthenticated && authStore.user?.profile?.has_changed_password === false) {
    form.username = authStore.user.username || ''
    passwordChangeRequired.value = true
  }
})

function enterSystem() {
  ElMessage.success('登录成功')
  if (isDesktop && window.desktopAuth?.loginSucceeded) {
    return window.desktopAuth.loginSucceeded().then((result) => {
      if (!result?.success) {
        throw new Error(result?.message || '无法打开系统主窗口')
      }
    })
  }
  const redirect = route.query.redirect || '/dashboard'
  return router.replace(String(redirect))
}

async function submitLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    if (authStore.user?.profile?.has_changed_password === false) {
      passwordChangeForm.currentPassword = form.password
      passwordChangeRequired.value = true
      return
    }
    await enterSystem()
  } catch (error) {
    ElMessage.error(error?.message || '登录失败')
  } finally {
    loading.value = false
  }
}

async function submitRequiredPasswordChange() {
  if (passwordChangeForm.newPassword !== passwordChangeForm.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  loading.value = true
  try {
    const result = await changeSystemPassword({
      old_password: passwordChangeForm.currentPassword,
      new_password: passwordChangeForm.newPassword
    })
    if (!result.success) {
      throw new Error(result.message || '密码修改失败')
    }

    form.password = passwordChangeForm.newPassword
    await authStore.clearAuth()
    await authStore.login(form.username, form.password)
    passwordChangeRequired.value = false
    await enterSystem()
  } catch (error) {
    ElMessage.error(error?.message || '密码修改失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
html {
  scroll-behavior: smooth;
}

body,
html {
  margin: 0;
  padding: 0;
  font-family: 'Noto Sans SC', sans-serif;
}

* {
  box-sizing: border-box;
}

.text-center {
  text-align: center;
}

button,
input,
select {
  -webkit-appearance: none;
  outline: none;
  font-family: 'Noto Sans SC', sans-serif;
}

button,
.btn,
select {
  cursor: pointer;
}

a {
  text-decoration: none;
}

img {
  max-width: 100%;
}

h1,
h2,
h3,
h4,
h5,
h6,
p {
  margin: 0;
  padding: 0;
}

p {
  color: #666;
  font-size: 16px;
  line-height: 25px;
  opacity: .6;
  text-align: center;
}

.btn,
button,
.actionbg,
input {
  border-radius: 36px;
  -webkit-border-radius: 36px;
  -moz-border-radius: 36px;
  -o-border-radius: 36px;
  -ms-border-radius: 36px;
}

.btn:hover,
button:hover {
  transition: 0.5s ease;
  -webkit-transition: 0.5s ease;
  -o-transition: 0.5s ease;
  -ms-transition: 0.5s ease;
  -moz-transition: 0.5s ease;
}

.w3l-hotair-form {
  position: relative;
  min-height: 100vh;
  z-index: 0;
  background: #0568c1;
  padding: 40px 40px;
  justify-content: center;
  display: grid;
  grid-template-rows: 1fr auto 1fr;
  align-items: center;
}

.container {
  max-width: 890px;
  margin: 0 auto;
}

.w3l_form {
  flex-basis: 50%;
  -webkit-flex-basis: 50%;
  background: #f4f9fd;
  background-size: cover;
  -webkit-background-size: cover;
  -moz-background-size: cover;
  -o-background-size: cover;
  -ms-background-size: cover;
  padding: 40px;
  border-top-right-radius: 8px;
  border-bottom-right-radius: 8px;
  align-items: center;
  display: grid;
}

.content-wthree {
  flex-basis: 50%;
  -webkit-flex-basis: 50%;
  box-sizing: border-box;
  padding: 3em 3em;
  background: #fff;
  box-shadow: 2px 9px 49px -17px rgba(0, 0, 0, 0.1);
  border-top-left-radius: 8px;
  border-bottom-left-radius: 8px;
}

.w3l-hotair-form .main-hotair {
  position: relative;
  display: -webkit-box;
  display: -moz-box;
  display: -ms-flexbox;
  display: -webkit-flex;
  display: flex;
  margin: 40px 0;
}

.w3l-hotair-form form {
  margin-top: 30px;
  margin-bottom: 30px;
}

p.account,
p.account a {
  text-align: center;
  padding-top: 20px;
  padding-bottom: 0;
  font-size: 16px;
  color: #333;
}

p.account a {
  color: #0568c1;
}

p.account a:hover {
  text-decoration: underline;
}

.w3l-hotair-form h1 {
  text-align: center;
  font-size: 40px;
  font-weight: 700;
  color: #fff;
}

.w3l-hotair-form h2 {
  font-size: 30px;
  line-height: 40px;
  margin-bottom: 5px;
  font-weight: 900;
  color: #272346;
  text-align: center;
}

.w3l-hotair-form input {
  outline: none;
  margin-bottom: 15px;
  font-size: 16px;
  color: #999;
  text-align: left;
  padding: 14px 20px;
  width: 100%;
  display: inline-block;
  box-sizing: border-box;
  border: none;
  background: #f7fafc;
  border: 1px solid #e5e5e5;
  transition: .3s ease;
  -webkit-transition: .3s ease;
  -moz-transition: .3s ease;
  -ms-transition: .3s ease;
  -o-transition: .3s ease;
}

.w3l-hotair-form input:focus {
  background: transparent;
  border: 1px solid #0568c1;
}

.w3l-hotair-form button {
  font-size: 18px;
  color: #fff;
  width: 100%;
  background: #0568c1;
  border: none;
  padding: 14px 15px;
  font-weight: 700;
  transition: .3s ease;
  -webkit-transition: .3s ease;
  -moz-transition: .3s ease;
  -ms-transition: .3s ease;
  -o-transition: .3s ease;
}

.w3l-hotair-form button:hover {
  background: #fdc500;
}

.copyright p {
  text-align: center;
  font-size: 17px;
  line-height: 26px;
  color: #fff;
  opacity: 1;
}

.desktop-login-shell {
  min-height: 100vh;
  grid-template-rows: 1fr auto 1fr;
  padding: 32px 24px;
  background:
    linear-gradient(135deg, transparent 0 48%, rgba(38, 133, 89, .045) 48% 49%, transparent 49% 100%),
    linear-gradient(45deg, transparent 0 48%, rgba(38, 133, 89, .035) 48% 49%, transparent 49% 100%),
    #e9efeb;
  font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

.desktop-login-shell.is-electron-login {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  justify-content: flex-start;
  padding: 20px 24px;
  overflow: hidden;
  background: #f4f6f5;
  user-select: none;
}

.desktop-login-shell.is-electron-login h1 {
  display: none;
}

.desktop-login-brand {
  display: grid;
  justify-items: center;
  gap: 11px;
  margin-bottom: 6px;
}

.desktop-app-logo {
  width: 58px;
  height: 58px;
  border: 1px solid #e1e8e3;
  border-radius: 13px;
  background: #fff;
  object-fit: contain;
}

.desktop-login-shell.is-electron-login .desktop-login-brand h2 {
  color: #29362f;
  font-size: 21px;
  font-weight: 600;
}

.desktop-login-shell.is-electron-login .container {
  width: 100%;
  max-width: none;
  flex: 1;
  min-height: 0;
}

.desktop-login-shell.is-electron-login .workinghny-form-grid,
.desktop-login-shell.is-electron-login .main-hotair {
  height: 100%;
  min-height: 0;
  margin: 0;
}

.desktop-login-shell.is-electron-login .main-hotair {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.desktop-login-shell.is-electron-login .content-wthree {
  width: 100%;
  flex: 1 1 auto;
  flex-basis: auto;
  justify-content: center;
  padding: 18px 26px 24px;
  background: transparent;
}

.desktop-login-shell.is-electron-login .w3l_form {
  display: none;
}

.desktop-login-shell.is-electron-login .copyright {
  flex: none;
}

.desktop-login-shell.is-electron-login .copyright p {
  font-size: 11px;
}

.desktop-login-shell h1 {
  align-self: end;
  margin-bottom: 6px;
  color: #35483d;
  font-size: 22px;
  font-weight: 600;
}

.desktop-login-shell .container {
  width: min(100%, 840px);
  max-width: 840px;
}

.desktop-login-shell .main-hotair {
  min-height: 430px;
  margin: 14px 0;
  overflow: hidden;
  border: 1px solid #d8e1da;
  border-radius: 7px;
  background: #fff;
  box-shadow: 0 18px 52px rgba(37, 66, 47, .14), 0 2px 7px rgba(37, 66, 47, .06);
}

.desktop-login-shell .content-wthree {
  order: 2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 50px 52px;
  border-radius: 0;
  box-shadow: none;
}

.desktop-login-shell h2 {
  color: #28372e;
  font-size: 24px;
  font-weight: 600;
  text-align: left;
}

.desktop-login-shell .login-subtitle {
  margin-top: 7px;
  color: #748078;
  font-size: 13px;
  line-height: 1.5;
  opacity: 1;
  text-align: left;
}

.desktop-login-shell form {
  display: grid;
  gap: 12px;
  margin: 28px 0 14px;
}

.desktop-login-shell input {
  min-height: 46px;
  margin: 0;
  padding: 0 14px;
  border: 1px solid #d8e0da;
  border-radius: 4px;
  background: #fbfcfb;
  color: #27342c;
  font-size: 14px;
}

.desktop-login-shell input:focus {
  border-color: #199566;
  box-shadow: 0 0 0 3px rgba(25, 149, 102, .1);
}

.desktop-login-shell .btn {
  min-height: 46px;
  margin-top: 5px;
  padding: 0 14px;
  border-radius: 4px;
  background: #16a06a;
  font-size: 15px;
  font-weight: 600;
}

.desktop-login-shell .btn:hover {
  background: #118355;
}

.desktop-login-shell .account,
.desktop-login-shell .account a {
  padding: 10px 0 0;
  color: #748078;
  font-size: 12px;
  text-align: left;
}

.desktop-login-shell .account a {
  color: #168b5d;
}

.desktop-login-shell .w3l_form {
  order: 1;
  display: flex;
  flex-basis: 43%;
  align-items: center;
  justify-content: center;
  padding: 28px;
  border-radius: 0;
  background: #f3f7f4;
}

.desktop-login-shell .left_grid_info {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
}

.desktop-login-shell .img-fluid {
  width: min(100%, 310px);
  max-height: 300px;
  object-fit: contain;
}

.desktop-login-shell .copyright p {
  color: #7b887f;
  font-size: 12px;
}

.password-notice {
  margin: 0 0 16px;
  color: #5f6b64;
  font-size: 14px;
  line-height: 1.6;
  opacity: 1;
  text-align: left;
}

.password-change-form input {
  min-height: 42px;
  padding: 0 12px;
  border: 1px solid #d8e0da;
  border-radius: 4px;
}

.password-change-form {
  display: grid;
  gap: 10px;
}

.password-change-button {
  min-height: 44px;
  border: 0;
  border-radius: 4px;
  background: #159764;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
}

.password-change-button:disabled {
  cursor: wait;
  opacity: .65;
}

@media (max-width: 736px) {
  .desktop-login-shell h1 {
    font-size: 18px;
  }

  .desktop-login-shell .main-hotair {
    max-width: 480px;
  }

  .desktop-login-shell .content-wthree {
    padding: 34px 30px;
  }

  .desktop-login-shell .w3l_form {
    display: none;
  }

  .w3l-hotair-form .main-hotair {
    flex-direction: column;
  }

  .w3l-hotair-form form {
    margin-top: 30px;
    margin-bottom: 10px;
  }

  .w3l_form {
    order: 2;
    border-radius: 0;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
    border-top-right-radius: 0;
  }

  .content-wthree {
    order: 1;
    border-radius: 0;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
  }
}

@media (max-width: 480px) {
  .desktop-login-shell.is-electron-login {
    padding-right: 16px;
    padding-left: 16px;
  }

  .desktop-login-shell.is-electron-login h1 {
    font-size: 19px;
  }
}

@media (max-width: 568px) {
  .w3l-hotair-form h1 {
    font-size: 36px;
  }

  .w3l-hotair-form .main-hotair {
    margin: 30px 0;
  }

  .content-wthree {
    padding: 2.5em;
  }
}

@media (max-width: 480px) {
  .desktop-login-shell {
    padding: 24px 16px;
  }

  .desktop-login-shell h1 {
    font-size: 16px;
  }

  .desktop-login-shell .content-wthree {
    padding: 30px 24px;
  }

  .w3l-hotair-form {
    padding: 40px 30px;
  }

  .w3l-hotair-form h1 {
    font-size: 26px;
  }

  .desktop-login-shell h1 {
    font-size: 16px;
  }
}

@media (max-width: 384px) {
  .w3l-hotair-form {
    padding: 30px 15px;
  }

  .content-wthree {
    padding: 2em;
  }

  .w3l-hotair-form h2 {
    font-size: 22px;
    line-height: 32px;
  }

  .copyright p {
    font-size: 16px;
  }
}
</style>

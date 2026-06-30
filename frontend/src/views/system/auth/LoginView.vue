<template>
  <section class="w3l-hotair-form">
    <h1>鄯善县文物综合管理平台</h1>
    <div class="container">
      <div class="workinghny-form-grid">
        <div class="main-hotair">
          <div class="content-wthree">
            <h2>系统登录</h2>
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

            <p class="account">如无账号请联系 <a href="javascript:void(0)">系统管理员</a></p>
          </div>
          <div class="w3l_form align-self">
            <div class="left_grid_info">
              <img :src="loginIllustration" alt="登录插图" class="img-fluid">
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="copyright text-center">
      <p class="copy-footer-29">© {{ new Date().getFullYear() }} 鄯善县文物综合管理平台。保留所有权利</p>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import loginIllustration from '../../../assets/login-illustration.png'
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
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;900&display=swap');

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

@media (max-width: 736px) {
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
  .w3l-hotair-form {
    padding: 40px 30px;
  }

  .w3l-hotair-form h1 {
    font-size: 26px;
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

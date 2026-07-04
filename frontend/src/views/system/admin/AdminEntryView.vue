<template>
  <section class="admin-entry-page">
    <div class="card">
      <div class="page-header">
        <h1>Django 后台管理</h1>
        <p>点击下方按钮前往后台管理系统。</p>
      </div>
      <div class="action-row top-space">
        <el-button type="primary" @click="openAdmin">打开后台管理</el-button>
      </div>
    </div>
  </section>
</template>

<script setup>
const DJANGO_ADMIN_URL = 'https://beichenhome.top:9081/admin'

function openAdmin() {
  window.open(DJANGO_ADMIN_URL, '_blank', 'noopener')
}
</script>

<style scoped>
.admin-entry-page {
  max-width: 980px;
}
</style>

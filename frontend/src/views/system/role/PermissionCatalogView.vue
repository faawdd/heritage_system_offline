<template>
  <section>
    <header class="page-header"><h1>权限条目</h1><p>对应 Django 权限编码，按现有业务模块中文展示。请在用户组或用户管理中分配权限。</p></header>
    <div class="card top-space" v-loading="loading">
      <permission-picker :permissions="permissions" disabled />
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import PermissionPicker from '../../../components/PermissionPicker.vue'
import { fetchSystemPermissions } from '../../../api/system/systemApi'

const permissions = ref([])
const loading = ref(true)
async function load() {
  try {
    const result = await fetchSystemPermissions()
    if (!result.success) throw new Error(result.message || '权限条目加载失败')
    permissions.value = result.rows
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error.message || '权限条目加载失败')
  } finally {
    loading.value = false
  }
}
load()
</script>

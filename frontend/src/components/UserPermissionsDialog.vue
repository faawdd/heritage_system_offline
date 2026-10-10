<template>
  <el-dialog v-model="visible" :title="`用户权限：${username}`" width="min(860px, 95vw)" v-loading="loading">
    <el-alert :closable="false" type="info" title="用户组权限由用户组继承；下面仅编辑额外授予用户的直接权限，取消直接权限不会撤销继承权限。" />
    <p v-if="isSuperAdmin">此用户为超级管理员，拥有全部系统权限。</p>
    <p>用户组继承权限：{{ inheritedNames || '无' }}</p>
    <permission-picker v-model="permissionIds" :permissions="permissions" :disabled="!canChange" />
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button v-if="canChange" type="primary" :loading="saving" @click="save">保存直接权限</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PermissionPicker from './PermissionPicker.vue'
import { fetchSystemPermissions, fetchUserPermissions, updateUserPermissions } from '../api/system/systemApi'
import { useAuthStore } from '../stores/system/authStore'

const authStore = useAuthStore()
const visible = ref(false)
const loading = ref(false)
const saving = ref(false)
const userId = ref(null)
const username = ref('')
const permissions = ref([])
const permissionIds = ref([])
const inherited = ref([])
const isSuperAdmin = ref(false)
const canChange = computed(() => Boolean(authStore.user?.capabilities?.change_users))
const inheritedNames = computed(() => permissions.value.filter(row => inherited.value.includes(row.id)).map(row => row.name).join('、'))

async function open(user) {
  userId.value = user.id
  username.value = user.username
  loading.value = true
  visible.value = true
  try {
    const [catalog, result] = await Promise.all([fetchSystemPermissions(), fetchUserPermissions(user.id)])
    if (!catalog.success || !result.success) throw new Error(result.message || catalog.message || '权限加载失败')
    permissions.value = catalog.rows
    permissionIds.value = result.data.permission_ids
    inherited.value = result.data.group_permission_ids
    isSuperAdmin.value = result.data.is_super_admin
  } catch (error) {
    visible.value = false
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || error.message || '权限加载失败')
  } finally {
    loading.value = false
  }
}
async function save() {
  saving.value = true
  try {
    const result = await updateUserPermissions(userId.value, permissionIds.value)
    if (!result.success) throw new Error(result.message || '保存失败')
    ElMessage.success(result.message)
    visible.value = false
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || error.message || '保存失败')
  } finally {
    saving.value = false
  }
}
defineExpose({ open })
</script>

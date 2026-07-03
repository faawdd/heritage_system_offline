<template>
  <section>
    <header class="page-header">
      <h1>用户管理</h1>
      <p>维护系统用户、状态和角色分配</p>
    </header>

    <div class="toolbar card top-space">
      <el-input v-model="filters.keyword" placeholder="用户名/姓名/邮箱" clearable style="max-width: 320px" />
      <el-button type="primary" :loading="loading" @click="loadUsers">查询</el-button>
      <el-button v-if="isSuperAdmin" @click="openCreateDialog">新增管理员</el-button>
    </div>

    <el-alert
      v-if="!isSuperAdmin"
      class="top-space"
      type="warning"
      :closable="false"
      title="仅超级管理员可新增、编辑或删除管理员账号"
    />

    <div class="card top-space">
      <el-table :data="rows" stripe v-loading="loading">
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column label="姓名" width="140">
          <template #default="scope">
            {{ `${scope.row.last_name || ''}${scope.row.first_name || ''}` || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="220" />
        <el-table-column label="角色" min-width="220">
          <template #default="scope">
            <el-tag v-for="role in scope.row.roles || []" :key="role" size="small" style="margin-right: 6px">
              {{ role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'danger'">
              {{ scope.row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="scope">
            <el-button link type="primary" :disabled="!isSuperAdmin" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button link type="warning" :disabled="!isSuperAdmin" @click="toggleUserStatus(scope.row)">
              {{ scope.row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button link type="danger" :disabled="!isSuperAdmin" @click="removeUser(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialog.visible" :title="dialog.mode === 'create' ? '新增用户' : '编辑用户'" width="560px">
      <el-form label-width="90px" label-position="left">
        <el-form-item label="用户名">
          <el-input v-model="dialog.form.username" :disabled="dialog.mode === 'edit'" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="dialog.form.password" placeholder="留空表示不修改" show-password />
        </el-form-item>
        <el-form-item label="姓">
          <el-input v-model="dialog.form.last_name" />
        </el-form-item>
        <el-form-item label="名">
          <el-input v-model="dialog.form.first_name" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="dialog.form.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="dialog.form.group_ids" multiple style="width: 100%" placeholder="请选择角色">
            <el-option v-for="item in roleOptions" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="dialog.form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="dialog.loading" @click="submitDialog">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createSystemUser,
  deleteSystemUser,
  fetchSystemRoles,
  fetchSystemUsers,
  updateSystemUser
} from '../../../api/system/systemApi'
import { useAuthStore } from '../../../stores/system/authStore'

const loading = ref(false)
const rows = ref([])
const roleOptions = ref([])
const authStore = useAuthStore()
const { user } = storeToRefs(authStore)
const isSuperAdmin = ref(false)

const filters = reactive({
  keyword: ''
})

const dialog = reactive({
  visible: false,
  mode: 'create',
  loading: false,
  editId: null,
  form: {
    username: '',
    password: '',
    first_name: '',
    last_name: '',
    email: '',
    is_active: true,
    is_staff: true,
    group_ids: []
  }
})

function resetDialogForm() {
  dialog.form = {
    username: '',
    password: '',
    first_name: '',
    last_name: '',
    email: '',
    is_active: true,
    is_staff: true,
    group_ids: []
  }
}

async function loadRoles() {
  const result = await fetchSystemRoles()
  if (result.success) {
    roleOptions.value = (result.rows || []).filter((item) => item.name === '管理员')
  }
}

async function loadUsers() {
  loading.value = true
  try {
    const currentUser = user.value || {}
    const roles = Array.isArray(currentUser.roles) ? currentUser.roles : []
    isSuperAdmin.value = Boolean(currentUser.is_superuser) || roles.includes('超级管理员')

    const result = await fetchSystemUsers({ keyword: filters.keyword })
    if (!result.success) {
      throw new Error(result.message || '加载失败')
    }
    rows.value = result.rows || []
    await loadRoles()
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  if (!isSuperAdmin.value) {
    ElMessage.warning('仅超级管理员可创建管理员账号')
    return
  }
  dialog.mode = 'create'
  dialog.editId = null
  resetDialogForm()
  dialog.visible = true
}

function openEditDialog(row) {
  if (!isSuperAdmin.value) {
    ElMessage.warning('仅超级管理员可编辑管理员账号')
    return
  }
  dialog.mode = 'edit'
  dialog.editId = row.id
  dialog.form = {
    username: row.username,
    password: '',
    first_name: row.first_name || '',
    last_name: row.last_name || '',
    email: row.email || '',
    is_active: Boolean(row.is_active),
    is_staff: Boolean(row.is_staff),
    group_ids: (roleOptions.value || [])
      .filter((item) => (row.roles || []).includes(item.name))
      .map((item) => item.id)
  }
  dialog.visible = true
}

async function submitDialog() {
  if (!isSuperAdmin.value) {
    ElMessage.warning('仅超级管理员可保存管理员账号')
    return
  }

  if (!dialog.form.username && dialog.mode === 'create') {
    ElMessage.warning('用户名不能为空')
    return
  }

  dialog.loading = true
  try {
    const payload = {
      ...dialog.form
    }

    if (!payload.password) {
      delete payload.password
    }

    const result =
      dialog.mode === 'create'
        ? await createSystemUser(payload)
        : await updateSystemUser(dialog.editId, payload)

    if (!result.success) {
      throw new Error(result.message || '保存失败')
    }

    ElMessage.success(dialog.mode === 'create' ? '创建成功' : '更新成功')
    dialog.visible = false
    await loadUsers()
  } catch (error) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    dialog.loading = false
  }
}

async function toggleUserStatus(row) {
  if (!isSuperAdmin.value) {
    ElMessage.warning('仅超级管理员可修改用户状态')
    return
  }

  try {
    const result = await updateSystemUser(row.id, {
      is_active: !row.is_active
    })
    if (!result.success) {
      throw new Error(result.message || '更新失败')
    }
    ElMessage.success('状态已更新')
    await loadUsers()
  } catch (error) {
    ElMessage.error(error?.message || '更新失败')
  }
}

async function removeUser(row) {
  if (!isSuperAdmin.value) {
    ElMessage.warning('仅超级管理员可删除管理员账号')
    return
  }

  try {
    await ElMessageBox.confirm(`确认删除用户 ${row.username} 吗？`, '删除确认', {
      type: 'warning'
    })
  } catch (_cancel) {
    return
  }

  try {
    const result = await deleteSystemUser(row.id)
    if (!result.success) {
      throw new Error(result.message || '删除失败')
    }
    ElMessage.success('删除成功')
    await loadUsers()
  } catch (error) {
    ElMessage.error(error?.message || '删除失败')
  }
}

loadUsers()
</script>

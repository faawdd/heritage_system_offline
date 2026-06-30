<template>
  <section>
    <header class="page-header">
      <h1>角色管理</h1>
      <p>查看系统角色及权限分配概览</p>
    </header>

    <div class="card top-space" v-loading="loading">
      <el-table :data="roles" stripe>
        <el-table-column prop="name" label="角色名称" min-width="200" />
        <el-table-column prop="permission_count" label="权限数量" width="120" />
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button link type="primary" @click="showPermissionDetail(scope.row)">查看权限</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="permissionDialog.visible" title="角色权限明细" width="860px">
      <div class="toolbar">
        <el-input
          v-model="permissionDialog.keyword"
          placeholder="按权限名称/编码筛选"
          clearable
          style="max-width: 280px"
        />
      </div>
      <el-table :data="filteredPermissions" height="460" stripe>
        <el-table-column prop="name" label="权限名称" min-width="260" />
        <el-table-column prop="codename" label="权限编码" min-width="220" />
        <el-table-column prop="content_type_id" label="类型ID" width="110" />
      </el-table>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchSystemPermissions, fetchSystemRoles } from '../../../api/system/systemApi'

const loading = ref(false)
const roles = ref([])
const permissions = ref([])

const permissionDialog = reactive({
  visible: false,
  keyword: ''
})

const filteredPermissions = computed(() => {
  const keyword = permissionDialog.keyword.trim().toLowerCase()
  if (!keyword) {
    return permissions.value
  }
  return permissions.value.filter((item) => {
    const name = String(item.name || '').toLowerCase()
    const code = String(item.codename || '').toLowerCase()
    return name.includes(keyword) || code.includes(keyword)
  })
})

async function loadData() {
  loading.value = true
  try {
    const [roleResult, permissionResult] = await Promise.all([fetchSystemRoles(), fetchSystemPermissions()])
    if (!roleResult.success) {
      throw new Error(roleResult.message || '角色加载失败')
    }
    if (!permissionResult.success) {
      throw new Error(permissionResult.message || '权限加载失败')
    }

    roles.value = roleResult.rows || []
    permissions.value = permissionResult.rows || []
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function showPermissionDetail(_role) {
  permissionDialog.keyword = ''
  permissionDialog.visible = true
}

loadData()
</script>

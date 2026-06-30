<template>
  <section>
    <header class="page-header">
      <h1>菜单管理</h1>
      <p>查看系统菜单树结构，支持动态侧边栏接入</p>
    </header>

    <div class="card top-space" v-loading="loading">
      <el-tree
        :data="treeRows"
        :props="treeProps"
        node-key="id"
        default-expand-all
        style="padding: 6px 4px"
      >
        <template #default="scope">
          <div class="menu-node-row">
            <span class="menu-node-title">{{ scope.data.name }}</span>
            <span class="menu-node-meta">{{ scope.data.path || '-' }}</span>
            <el-tag size="small">{{ scope.data.menu_type }}</el-tag>
            <el-tag size="small" :type="scope.data.is_active ? 'success' : 'danger'">
              {{ scope.data.is_active ? '启用' : '禁用' }}
            </el-tag>
          </div>
        </template>
      </el-tree>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchSystemMenus } from '../../../api/system/systemApi'

const loading = ref(false)
const treeRows = ref([])

const treeProps = {
  label: 'name',
  children: 'children'
}

async function loadMenus() {
  loading.value = true
  try {
    const result = await fetchSystemMenus()
    if (!result.success) {
      throw new Error(result.message || '加载失败')
    }
    treeRows.value = result.tree || []
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

loadMenus()
</script>

<style scoped>
.menu-node-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.menu-node-title {
  min-width: 120px;
}

.menu-node-meta {
  color: var(--muted);
  min-width: 180px;
}
</style>

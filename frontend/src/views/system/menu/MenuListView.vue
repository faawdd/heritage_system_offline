<template>
  <section>
    <header class="page-header">
      <h1>菜单管理</h1>
      <p>管理系统菜单树，支持新增、编辑、删除与角色绑定</p>
    </header>

    <div class="toolbar card top-space">
      <el-button type="primary" @click="openCreateDialog">新建菜单</el-button>
      <el-button :loading="loading" @click="loadMenus">刷新</el-button>
      <el-button @click="expandAll">全部展开</el-button>
      <el-button @click="collapseAll">全部收起</el-button>
    </div>

    <div class="card top-space" v-loading="loading">
      <el-tree
        ref="treeRef"
        :data="treeRows"
        :props="treeProps"
        node-key="id"
        :default-expand-all="expandedAll"
        style="padding: 6px 4px"
      >
        <template #default="scope">
          <div class="menu-node-row">
            <span class="menu-node-title">{{ scope.data.name }}</span>
            <span class="menu-node-meta">{{ scope.data.path || '-' }}</span>
            <el-tag size="small">{{ menuTypeLabel(scope.data.menu_type) }}</el-tag>
            <el-tag size="small" :type="scope.data.is_active ? 'success' : 'danger'">
              {{ scope.data.is_active ? '启用' : '禁用' }}
            </el-tag>
            <el-tag size="small" :type="scope.data.visible ? 'success' : 'info'">
              {{ scope.data.visible ? '可见' : '隐藏' }}
            </el-tag>
            <el-tag size="small" type="info">排序 {{ scope.data.order_num }}</el-tag>
            <div class="menu-node-actions">
              <el-button link type="primary" @click.stop="openEditDialog(scope.data)">编辑</el-button>
              <el-button link type="danger" @click.stop="handleDelete(scope.data)">删除</el-button>
            </div>
          </div>
        </template>
      </el-tree>
    </div>

    <el-dialog
      v-model="dialog.visible"
      :title="dialog.mode === 'create' ? '新建菜单' : '编辑菜单'"
      width="720px"
    >
      <el-form label-width="110px" label-position="left">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="菜单名称" required>
              <el-input v-model="dialog.form.name" placeholder="请输入菜单名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="菜单类型" required>
              <el-select v-model="dialog.form.menu_type" style="width: 100%">
                <el-option label="目录" value="directory" />
                <el-option label="菜单" value="menu" />
                <el-option label="按钮" value="button" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="父级菜单">
              <el-select v-model="dialog.form.parent_id" clearable style="width: 100%" placeholder="顶级菜单">
                <el-option
                  v-for="item in parentOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="dialog.form.order_num" :min="0" :max="9999" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="路由路径">
          <el-input v-model="dialog.form.path" placeholder="如 /system/menus" />
        </el-form-item>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="组件路径">
              <el-input v-model="dialog.form.component" placeholder="如 views/system/menu/MenuListView" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="图标">
              <el-input v-model="dialog.form.icon" placeholder="如 setting" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="权限标识">
          <el-input v-model="dialog.form.permission_code" placeholder="如 system:menu:view" />
        </el-form-item>

        <el-form-item label="可访问角色">
          <el-select
            v-model="dialog.form.role_ids"
            multiple
            collapse-tags
            collapse-tags-tooltip
            style="width: 100%"
            placeholder="不选表示所有角色可见"
          >
            <el-option
              v-for="role in roleOptions"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            />
          </el-select>
        </el-form-item>

        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="显示">
              <el-switch v-model="dialog.form.visible" active-text="显示" inactive-text="隐藏" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启用">
              <el-switch v-model="dialog.form.is_active" active-text="启用" inactive-text="禁用" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="缓存">
              <el-switch v-model="dialog.form.keep_alive" active-text="开启" inactive-text="关闭" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="dialog.loading" @click="submitDialog">
          {{ dialog.mode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createSystemMenu,
  deleteSystemMenu,
  fetchSystemMenus,
  fetchSystemRoles,
  updateSystemMenu
} from '../../../api/system/systemApi'

const loading = ref(false)
const treeRef = ref(null)
const treeRows = ref([])
const flatRows = ref([])
const roleOptions = ref([])
const expandedAll = ref(true)

const treeProps = {
  label: 'name',
  children: 'children'
}

const dialog = reactive({
  visible: false,
  loading: false,
  mode: 'create',
  editId: null,
  form: {
    name: '',
    menu_type: 'menu',
    parent_id: null,
    path: '',
    component: '',
    icon: '',
    permission_code: '',
    visible: true,
    is_active: true,
    keep_alive: false,
    order_num: 0,
    role_ids: []
  }
})

const parentOptions = computed(() => {
  return (flatRows.value || [])
    .filter((item) => item.id !== dialog.editId)
    .map((item) => ({
      value: item.id,
      label: `${item.name} (${item.path || '无路径'})`
    }))
})

function menuTypeLabel(value) {
  if (value === 'directory') {
    return '目录'
  }
  if (value === 'button') {
    return '按钮'
  }
  return '菜单'
}

function resetDialogForm() {
  dialog.form = {
    name: '',
    menu_type: 'menu',
    parent_id: null,
    path: '',
    component: '',
    icon: '',
    permission_code: '',
    visible: true,
    is_active: true,
    keep_alive: false,
    order_num: 0,
    role_ids: []
  }
}

function openCreateDialog() {
  dialog.mode = 'create'
  dialog.editId = null
  resetDialogForm()
  dialog.visible = true
}

function openEditDialog(row) {
  dialog.mode = 'edit'
  dialog.editId = row.id
  dialog.form = {
    name: row.name || '',
    menu_type: row.menu_type || 'menu',
    parent_id: row.parent_id ?? null,
    path: row.path || '',
    component: row.component || '',
    icon: row.icon || '',
    permission_code: row.permission_code || '',
    visible: !!row.visible,
    is_active: !!row.is_active,
    keep_alive: !!row.keep_alive,
    order_num: Number(row.order_num || 0),
    role_ids: Array.isArray(row.role_ids) ? row.role_ids : []
  }
  dialog.visible = true
}

async function submitDialog() {
  if (!dialog.form.name.trim()) {
    ElMessage.warning('菜单名称不能为空')
    return
  }

  const payload = {
    ...dialog.form,
    name: dialog.form.name.trim(),
    path: (dialog.form.path || '').trim(),
    component: (dialog.form.component || '').trim(),
    icon: (dialog.form.icon || '').trim(),
    permission_code: (dialog.form.permission_code || '').trim(),
    parent_id: dialog.form.parent_id || null,
    order_num: Number(dialog.form.order_num || 0),
    role_ids: Array.isArray(dialog.form.role_ids) ? dialog.form.role_ids : []
  }

  dialog.loading = true
  try {
    let result
    if (dialog.mode === 'create') {
      result = await createSystemMenu(payload)
    } else {
      result = await updateSystemMenu(dialog.editId, payload)
    }

    if (!result.success) {
      throw new Error(result.message || '保存失败')
    }

    ElMessage.success(dialog.mode === 'create' ? '菜单创建成功' : '菜单保存成功')
    dialog.visible = false
    await loadMenus()
  } catch (error) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    dialog.loading = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除菜单“${row.name}”吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch (_cancel) {
    return
  }

  try {
    const result = await deleteSystemMenu(row.id)
    if (!result.success) {
      throw new Error(result.message || '删除失败')
    }
    ElMessage.success('菜单已删除')
    await loadMenus()
  } catch (error) {
    ElMessage.error(error?.message || '删除失败')
  }
}

async function loadRoles() {
  try {
    const result = await fetchSystemRoles()
    if (!result.success) {
      throw new Error(result.message || '角色加载失败')
    }
    roleOptions.value = result.rows || []
  } catch (error) {
    ElMessage.error(error?.message || '角色加载失败')
  }
}

async function expandAll() {
  expandedAll.value = true
  await nextTick()
  ;(flatRows.value || []).forEach((item) => {
    treeRef.value?.store?.nodesMap?.[item.id]?.expand?.()
  })
}

async function collapseAll() {
  expandedAll.value = false
  await nextTick()
  ;(flatRows.value || []).forEach((item) => {
    treeRef.value?.store?.nodesMap?.[item.id]?.collapse?.()
  })
}

async function loadMenus() {
  loading.value = true
  try {
    const result = await fetchSystemMenus()
    if (!result.success) {
      throw new Error(result.message || '加载失败')
    }
    treeRows.value = result.tree || []
    flatRows.value = result.rows || []
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

loadRoles()
loadMenus()
</script>

<style scoped>
.menu-node-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.menu-node-title {
  min-width: 160px;
}

.menu-node-meta {
  color: var(--muted);
  min-width: 220px;
}

.menu-node-actions {
  margin-left: auto;
  display: inline-flex;
  gap: 6px;
}
</style>

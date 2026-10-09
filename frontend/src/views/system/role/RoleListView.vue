<template>
  <section>
    <header class="page-header">
      <h1>角色管理</h1>
      <p>新增角色（用户组）、从内置模板创建、维护角色权限。内置角色权限由模板维护。</p>
    </header>

    <div class="card top-space" v-loading="loading">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增角色</el-button>
      </div>
      <el-table :data="roles" stripe>
        <el-table-column label="角色名称" min-width="200">
          <template #default="scope">
            {{ scope.row.name }}
            <el-tag v-if="scope.row.is_builtin" size="small" type="warning" style="margin-left: 8px">内置</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="permission_count" label="权限数量" width="110" />
        <el-table-column prop="user_count" label="用户数" width="100" />
        <el-table-column label="操作" width="360">
          <template #default="scope">
            <el-button link type="primary" @click="openPermissions(scope.row)">
              {{ scope.row.is_builtin ? '查看权限' : '编辑权限' }}
            </el-button>
            <el-button v-if="!scope.row.is_builtin" link type="primary" @click="openRename(scope.row)">重命名</el-button>
            <el-button v-if="scope.row.is_builtin" link type="primary" @click="restoreTemplate(scope.row)">恢复模板权限</el-button>
            <el-button v-else link type="danger" @click="removeRole(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="createDialog.visible" title="新增角色" width="860px">
      <el-form label-width="90px">
        <el-form-item label="角色名称">
          <el-input v-model="createDialog.name" maxlength="150" placeholder="例如：区县巡查组" />
        </el-form-item>
        <el-form-item label="权限模板">
          <el-radio-group v-model="createDialog.template" @change="applyTemplateSelection">
            <el-radio value="">自定义</el-radio>
            <el-radio v-for="tpl in templates" :key="tpl.key" :value="tpl.key">{{ tpl.label }}</el-radio>
          </el-radio-group>
          <div class="hint-text">{{ currentTemplateDescription }}</div>
        </el-form-item>
        <el-form-item label="权限">
          <permission-picker
            v-model="createDialog.permissionIds"
            :permissions="permissions"
            :disabled="Boolean(createDialog.template)"
          />
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="自定义角色仅获得所选的数据权限；管理端入口与菜单访问级别以内置角色（管理员、管理员用户组、文物看护员）为准。"
      />
      <template #footer>
        <el-button @click="createDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="createDialog.saving" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="permissionDialog.visible" :title="`角色权限：${permissionDialog.role?.name || ''}`" width="860px">
      <permission-picker
        v-model="permissionDialog.permissionIds"
        :permissions="permissions"
        :disabled="Boolean(permissionDialog.role?.is_builtin)"
      />
      <template #footer>
        <el-button @click="permissionDialog.visible = false">关闭</el-button>
        <el-button
          v-if="!permissionDialog.role?.is_builtin"
          type="primary"
          :loading="permissionDialog.saving"
          @click="submitPermissions"
        >保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, reactive, ref } from 'vue'
import { ElCheckbox, ElInput, ElMessage, ElMessageBox } from 'element-plus'

import {
  applyRoleTemplate,
  createSystemRole,
  deleteSystemRole,
  fetchRolePermissions,
  fetchRoleTemplates,
  fetchSystemPermissions,
  fetchSystemRoles,
  renameSystemRole,
  updateRolePermissions
} from '../../../api/system/systemApi'

const PermissionPicker = defineComponent({
  props: {
    modelValue: { type: Array, default: () => [] },
    permissions: { type: Array, default: () => [] },
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const keyword = ref('')
    const visible = computed(() => {
      const kw = keyword.value.trim().toLowerCase()
      if (!kw) return props.permissions
      return props.permissions.filter(
        (item) => String(item.name || '').toLowerCase().includes(kw) || String(item.codename || '').toLowerCase().includes(kw)
      )
    })
    function toggle(id, checked) {
      const set = new Set(props.modelValue)
      if (checked) set.add(id)
      else set.delete(id)
      emit('update:modelValue', Array.from(set))
    }
    return () =>
      h('div', { style: 'width: 100%' }, [
        h(ElInput, {
          modelValue: keyword.value,
          'onUpdate:modelValue': (value) => (keyword.value = value),
          placeholder: '按权限名称/编码筛选',
          clearable: true,
          style: 'max-width: 280px; margin-bottom: 8px'
        }),
        h(
          'div',
          { style: 'max-height: 360px; overflow: auto; display: grid; grid-template-columns: repeat(2, 1fr); gap: 2px 12px' },
          visible.value.map((item) =>
            h(ElCheckbox, {
              key: item.id,
              modelValue: props.modelValue.includes(item.id),
              disabled: props.disabled,
              'onUpdate:modelValue': (checked) => toggle(item.id, checked),
              label: `${item.name}（${item.codename}）`
            })
          )
        ),
        h('div', { class: 'hint-text' }, `已选 ${props.modelValue.length} / ${props.permissions.length}`)
      ])
  }
})

const loading = ref(false)
const roles = ref([])
const permissions = ref([])
const templates = ref([])

const createDialog = reactive({ visible: false, saving: false, name: '', template: '', permissionIds: [] })
const permissionDialog = reactive({ visible: false, saving: false, role: null, permissionIds: [] })

const currentTemplateDescription = computed(() => {
  const tpl = templates.value.find((item) => item.key === createDialog.template)
  return tpl ? tpl.description : '手动勾选权限'
})

function errorMessage(error, fallback) {
  return error?.response?.data?.message || error?.message || fallback
}

async function loadData() {
  loading.value = true
  try {
    const [roleResult, permissionResult, templateResult] = await Promise.all([
      fetchSystemRoles(),
      fetchSystemPermissions(),
      fetchRoleTemplates()
    ])
    if (!roleResult.success) throw new Error(roleResult.message || '角色加载失败')
    if (!permissionResult.success) throw new Error(permissionResult.message || '权限加载失败')
    roles.value = roleResult.rows || []
    permissions.value = permissionResult.rows || []
    templates.value = templateResult.rows || []
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载失败'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(createDialog, { visible: true, saving: false, name: '', template: '', permissionIds: [] })
}

function applyTemplateSelection(key) {
  const tpl = templates.value.find((item) => item.key === key)
  createDialog.permissionIds = tpl ? [...tpl.permission_ids] : []
}

async function submitCreate() {
  const name = createDialog.name.trim()
  if (!name) {
    ElMessage.warning('请输入角色名称')
    return
  }
  createDialog.saving = true
  try {
    const result = await createSystemRole({
      name,
      template: createDialog.template || undefined,
      permission_ids: createDialog.template ? undefined : createDialog.permissionIds
    })
    ElMessage.success(result.message || '角色已创建')
    createDialog.visible = false
    await loadData()
  } catch (error) {
    ElMessage.error(errorMessage(error, '创建失败'))
  } finally {
    createDialog.saving = false
  }
}

async function openPermissions(role) {
  try {
    const result = await fetchRolePermissions(role.id)
    permissionDialog.role = role
    permissionDialog.permissionIds = result.data?.permission_ids || []
    permissionDialog.visible = true
  } catch (error) {
    ElMessage.error(errorMessage(error, '权限加载失败'))
  }
}

async function submitPermissions() {
  permissionDialog.saving = true
  try {
    const result = await updateRolePermissions(permissionDialog.role.id, permissionDialog.permissionIds)
    ElMessage.success(result.message || '角色权限已更新')
    permissionDialog.visible = false
    await loadData()
  } catch (error) {
    ElMessage.error(errorMessage(error, '保存失败'))
  } finally {
    permissionDialog.saving = false
  }
}

async function openRename(role) {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的角色名称', '重命名角色', { inputValue: role.name })
    const result = await renameSystemRole(role.id, value)
    ElMessage.success(result.message || '已更新')
    await loadData()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error, '重命名失败'))
  }
}

async function removeRole(role) {
  try {
    await ElMessageBox.confirm(`确定删除角色“${role.name}”吗？`, '删除角色', { type: 'warning' })
    const result = await deleteSystemRole(role.id)
    ElMessage.success(result.message || '角色已删除')
    await loadData()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error, '删除失败'))
  }
}

async function restoreTemplate(role) {
  try {
    await ElMessageBox.confirm(`将“${role.name}”的权限恢复为内置模板配置？`, '恢复模板权限', { type: 'warning' })
    const result = await applyRoleTemplate(role.id)
    ElMessage.success(result.message || '已恢复')
    await loadData()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error, '操作失败'))
  }
}

loadData()
</script>

<template>
  <div class="permission-picker">
    <el-input v-model="keyword" placeholder="按中文名称、业务模块或权限编码筛选" clearable />
    <div class="permission-groups">
      <section v-for="group in groups" :key="group.key">
        <h3>{{ group.label }}</h3>
        <el-checkbox
          v-for="permission in group.rows"
          :key="permission.id"
          :model-value="modelValue.includes(permission.id)"
          :disabled="disabled || !permission.grantable"
          :title="`${permission.app_label}.${permission.codename}`"
          @update:model-value="checked => toggle(permission.id, checked)"
        >{{ permission.name }}</el-checkbox>
      </section>
    </div>
    <div class="hint-text">已选 {{ modelValue.length }} / {{ permissions.length }}；权限编码可通过悬停查看。未拥有的权限不可授予。</div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  permissions: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])
const keyword = ref('')
const groups = computed(() => {
  const result = new Map()
  const search = keyword.value.trim().toLowerCase()
  for (const item of props.permissions) {
    if (search && ![item.name, item.app_name, item.model_name, item.codename].some(
      value => String(value || '').toLowerCase().includes(search)
    )) continue
    const key = `${item.app_label}.${item.model}`
    if (!result.has(key)) result.set(key, { key, label: `${item.app_name} · ${item.model_name}`, rows: [] })
    result.get(key).rows.push(item)
  }
  return [...result.values()]
})
function toggle(id, checked) {
  const selected = new Set(props.modelValue)
  if (checked) selected.add(id)
  else selected.delete(id)
  emit('update:modelValue', [...selected])
}
</script>

<style scoped>
.permission-picker { width: 100%; }
.permission-groups { max-height: 420px; overflow: auto; margin: 12px 0; }
.permission-groups h3 { font-size: 14px; margin: 12px 0 6px; }
.permission-groups .el-checkbox { margin-right: 18px; }
</style>

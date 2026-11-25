import { ref } from 'vue'

export const DEFAULT_SYSTEM_NAME = '文物综合管理平台'
export const SYSTEM_NAME_STORAGE_KEY = 'heritage_system_name'

export const systemName = ref(normalizeSystemName(localStorage.getItem(SYSTEM_NAME_STORAGE_KEY)))

if (typeof document !== 'undefined') {
  document.title = systemName.value
}

export function normalizeSystemName(value) {
  const name = String(value || '').trim()
  return name || DEFAULT_SYSTEM_NAME
}

export function setSystemName(value) {
  const name = normalizeSystemName(value)
  systemName.value = name
  localStorage.setItem(SYSTEM_NAME_STORAGE_KEY, name)
  document.title = name
  return name
}

export function getStoredSystemName() {
  return normalizeSystemName(systemName.value)
}

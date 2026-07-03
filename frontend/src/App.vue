<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'

import { useAppStore } from './stores/system/appStore'

const appStore = useAppStore()

onMounted(() => {
  appStore.initialize()
})
</script>

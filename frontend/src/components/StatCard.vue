<template>
  <div class="stat-card">
    <p class="stat-title">{{ title }}</p>
    <p class="stat-value">{{ value }}</p>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: ''
  },
  value: {
    type: [String, Number],
    default: '-'
  }
})
</script>

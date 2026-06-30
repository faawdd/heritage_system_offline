<template>
  <section>
    <header class="page-header">
      <h1>综合看板</h1>
      <p>面向审批、巡查、文保风险和地图联动的统一首页</p>
    </header>

    <div class="stats-grid">
      <StatCard title="待审批项目" :value="42" />
      <StatCard title="今日巡查" :value="17" />
      <StatCard title="文保点总数" :value="1260" />
      <StatCard title="风险预警" :value="6" />
    </div>

    <div class="dashboard-grid">
      <div class="card">
        <h3>系统版本</h3>
        <p>{{ versionText }}</p>
      </div>
      <div class="card tall">
        <h3>地图总览</h3>
        <GisMapPanel />
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { fetchSystemVersion } from '../../api/dashboardApi'
import GisMapPanel from '../../components/GisMapPanel.vue'
import StatCard from '../../components/StatCard.vue'

const versionText = ref('-')

onMounted(async () => {
  try {
    const res = await fetchSystemVersion()
    versionText.value = res?.data?.version || '-'
  } catch (error) {
    versionText.value = '未获取到版本信息'
  }
})
</script>

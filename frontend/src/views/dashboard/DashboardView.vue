<template>
  <section>
    <header class="page-header">
      <h1>综合看板</h1>
      <p>面向审批、巡查、文保风险和地图联动的统一首页</p>
    </header>

    <div class="stats-grid">
      <StatCard title="待审批项目" :value="overview.pending_project_count" />
      <StatCard title="今日巡查" :value="overview.today_inspection_count" />
      <StatCard title="文保点总数" :value="overview.heritage_total_count" />
      <StatCard title="风险预警" :value="overview.risk_warning_count" />
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

import { fetchDashboardOverview, fetchSystemVersion } from '../../api/dashboardApi'
import GisMapPanel from '../../components/GisMapPanel.vue'
import StatCard from '../../components/StatCard.vue'

const versionText = ref('-')
const overview = ref({
  pending_project_count: '-',
  today_inspection_count: '-',
  heritage_total_count: '-',
  risk_warning_count: '-'
})

onMounted(async () => {
  try {
    const dashboardRes = await fetchDashboardOverview()
    if (dashboardRes?.success && dashboardRes?.data) {
      overview.value = {
        ...overview.value,
        ...dashboardRes.data
      }
    }
  } catch (error) {
    overview.value = {
      pending_project_count: '获取失败',
      today_inspection_count: '获取失败',
      heritage_total_count: '获取失败',
      risk_warning_count: '获取失败'
    }
  }

  try {
    const res = await fetchSystemVersion()
    versionText.value = res?.data?.version || '-'
  } catch (error) {
    versionText.value = '未获取到版本信息'
  }
})
</script>

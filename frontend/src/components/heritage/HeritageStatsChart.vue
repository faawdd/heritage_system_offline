<template>
  <div ref="chartEl" class="heritage-stats-chart"></div>
</template>

<script setup>
import * as echarts from 'echarts'
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  labels: {
    type: Array,
    default: () => []
  },
  values: {
    type: Array,
    default: () => []
  }
})

const chartEl = ref(null)
let chartRef = null

function renderChart() {
  if (!chartRef) {
    return
  }
  chartRef.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: props.labels
    },
    yAxis: {
      type: 'value',
      minInterval: 1
    },
    series: [
      {
        type: 'bar',
        data: props.values,
        itemStyle: { color: '#0d9488' }
      }
    ]
  })
}

onMounted(() => {
  chartRef = echarts.init(chartEl.value)
  renderChart()
  window.addEventListener('resize', chartRef.resize)
})

onUnmounted(() => {
  if (chartRef) {
    window.removeEventListener('resize', chartRef.resize)
    chartRef.dispose()
  }
})

watch(
  () => [props.labels, props.values],
  () => renderChart(),
  { deep: true }
)
</script>

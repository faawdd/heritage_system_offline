<template>
  <section class="report-center">
    <header class="page-header report-header">
      <div><p class="eyebrow">HERITAGE INTELLIGENCE</p><h1>报告中心</h1><p>把巡查、文物档案与项目流程，整理成可阅读、可归档的周期观察。</p></div>
      <el-button type="primary" :loading="generating" @click="generate">生成{{ periodLabels[selectedPeriod] }}</el-button>
    </header>

    <div class="report-toolbar card">
      <el-segmented v-model="selectedPeriod" :options="periodOptions" />
      <span class="muted-text">统计上一完整{{ periodLabels[selectedPeriod] }}，适合打印归档</span>
      <el-button link @click="openPreview">预览当前周期</el-button>
    </div>

    <div class="report-layout">
      <div class="report-intro">
        <div class="intro-mark">R<br /><small>02</small></div>
        <h2>让时间成为<br /><em>保护工作的证据</em></h2>
        <p>报告采用系统实时数据生成，针对不同周期调整观察尺度。HTML 页面保留纸张版式，可直接使用浏览器“打印 / 存储为 PDF”。</p>
        <div class="period-notes"><span v-for="option in periodOptions" :key="option.value"><b>{{ option.label }}</b>{{ periodNotes[option.value] }}</span></div>
      </div>
      <div class="history-panel card"><div class="card-header-row"><h3>已生成报告</h3><el-button link :loading="loading" @click="loadReports">刷新</el-button></div><el-table :data="reports" v-loading="loading" empty-text="还没有报告，先生成一份吧" stripe><el-table-column prop="title" label="报告" min-width="220" /><el-table-column label="统计区间" width="220"><template #default="scope">{{ scope.row.period_start }} 至 {{ scope.row.period_end }}</template></el-table-column><el-table-column label="操作" width="150" fixed="right"><template #default="scope"><el-button link type="primary" @click="openReport(scope.row.id)">打开 / PDF</el-button></template></el-table-column></el-table></div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchReportHtml, fetchReportPreview, fetchReports, generateReport } from '../../api/reportApi'

const periodOptions = [
  { label: '周报', value: 'weekly' },
  { label: '月报', value: 'monthly' },
  { label: '季度报', value: 'quarterly' },
  { label: '年报', value: 'yearly' }
]
const periodLabels = Object.fromEntries(periodOptions.map((item) => [item.value, item.label]))
const periodNotes = { weekly: '巡查节奏', monthly: '月度工作量', quarterly: '阶段变化', yearly: '年度复盘' }
const selectedPeriod = ref('monthly')
const reports = ref([])
const loading = ref(false)
const generating = ref(false)

async function loadReports() {
  loading.value = true
  try {
    const result = await fetchReports()
    reports.value = result?.data || []
  } catch (error) { ElMessage.error(error?.response?.data?.message || '报告列表加载失败') } finally { loading.value = false }
}

async function generate() {
  generating.value = true
  try {
    const result = await generateReport(selectedPeriod.value)
    ElMessage.success('报告已生成')
    await loadReports()
    await openReport(result.data.id)
  } catch (error) { ElMessage.error(error?.response?.data?.message || '报告生成失败') } finally { generating.value = false }
}

function openHtml(html) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => URL.revokeObjectURL(url), 60000)
}

async function openReport(id) {
  try { openHtml(await fetchReportHtml(id)) } catch (error) { ElMessage.error('报告打开失败') }
}

async function openPreview() {
  try { openHtml(await fetchReportPreview(selectedPeriod.value)) } catch (error) { ElMessage.error('报告预览失败') }
}

onMounted(loadReports)
</script>

<style scoped>
.report-center { padding: 28px; background: radial-gradient(circle at 88% 0%, rgba(204,169,94,.15), transparent 34%), #f3f5f0; min-height: 100%; color: #1d3b35; }
.report-header { display:flex; justify-content:space-between; align-items:flex-end; gap:24px; } .report-header h1 { margin:4px 0 8px; font: 700 34px/1.1 Georgia,serif; letter-spacing:.03em; } .report-header p { margin:0; color:#6c7d78; } .eyebrow { color:#ad7d37!important; letter-spacing:.18em; font:12px Arial,sans-serif; }
.report-toolbar { display:flex; align-items:center; gap:18px; margin:28px 0; padding:13px 16px; } .report-toolbar .muted-text { flex:1; }
.report-layout { display:grid; grid-template-columns:minmax(240px,.65fr) minmax(500px,1.7fr); gap:22px; } .report-intro { padding:32px 22px; min-height:430px; background:#173c35; color:#f6f1e5; position:relative; overflow:hidden; } .report-intro:after { content:''; position:absolute; right:-60px; bottom:-80px; width:240px; height:240px; border:1px solid rgba(211,166,83,.45); transform:rotate(35deg); } .intro-mark { color:#d4a452; font:bold 48px Georgia,serif; line-height:.75; } .intro-mark small { font:12px Arial,sans-serif; letter-spacing:.2em; } .report-intro h2 { margin:42px 0 16px; font:32px/1.3 Georgia,serif; } .report-intro h2 em { color:#d4a452; font-style:normal; } .report-intro p { color:#c3d2cc; line-height:1.8; max-width:300px; } .period-notes { display:grid; gap:9px; margin-top:30px; font-size:12px; color:#aac0b7; } .period-notes span { display:flex; gap:10px; } .period-notes b { color:#f2ead8; min-width:42px; }
.history-panel { min-width:0; padding:18px; } .history-panel :deep(.el-table) { --el-table-header-bg-color:#f0f4ef; }
@media (max-width: 900px) { .report-center { padding:18px; } .report-header, .report-toolbar { align-items:flex-start; flex-direction:column; } .report-layout { grid-template-columns:1fr; } .report-intro { min-height:unset; } }
@media print { .report-center { display:none; } }
</style>

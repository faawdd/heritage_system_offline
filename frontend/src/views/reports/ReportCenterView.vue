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
        <div class="countdown-block">
          <span class="countdown-label">下一次{{ periodLabels[selectedPeriod] }}生成</span>
          <strong>{{ countdownText }}</strong>
          <small>{{ nextGenerationLabel }}</small>
        </div>
        <div class="period-notes"><span v-for="option in periodOptions" :key="option.value"><b>{{ option.label }}</b>{{ periodNotes[option.value] }}</span></div>
      </div>
      <div class="history-panel card"><div class="card-header-row"><div><h3>{{ periodLabels[selectedPeriod] }}历史报告</h3><span class="history-count">共 {{ filteredReports.length }} 份</span></div><el-button link :loading="loading" @click="loadReports">刷新</el-button></div><el-table :data="filteredReports" v-loading="loading" empty-text="当前类型还没有报告，先生成一份吧" stripe><el-table-column label="类型" width="92"><template #default="scope"><span class="period-badge" :class="`period-${scope.row.period}`">{{ periodLabels[scope.row.period] }}</span></template></el-table-column><el-table-column prop="title" label="报告" min-width="210" /><el-table-column label="统计区间" width="220"><template #default="scope">{{ scope.row.period_start }} 至 {{ scope.row.period_end }}</template></el-table-column><el-table-column label="操作" width="150" fixed="right"><template #default="scope"><el-button link type="primary" @click="openReport(scope.row.id)">打开 / PDF</el-button></template></el-table-column></el-table></div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
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
const filteredReports = computed(() => reports.value.filter((report) => report.period === selectedPeriod.value))
const now = ref(new Date())
let countdownTimer = null

function getNextGenerationDate(period, current = new Date()) {
  const next = new Date(current)
  next.setHours(8, 0, 0, 0)
  if (period === 'weekly') {
    const isGenerationDay = current.getDay() === 1 && current.getHours() < 8
    const daysUntilMonday = isGenerationDay ? 0 : ((8 - current.getDay()) % 7 || 7)
    next.setDate(current.getDate() + daysUntilMonday)
  } else if (period === 'monthly') {
    if (current.getDate() !== 1 || current.getHours() >= 8) {
      next.setMonth(current.getMonth() + 1, 1)
    } else {
      next.setDate(1)
    }
  } else if (period === 'quarterly') {
    const nextQuarterMonth = Math.floor(current.getMonth() / 3) * 3 + 3
    const isQuarterStart = current.getDate() === 1 && current.getMonth() % 3 === 0 && current.getHours() < 8
    next.setMonth(isQuarterStart ? current.getMonth() : nextQuarterMonth, 1)
  } else {
    const isYearStart = current.getMonth() === 0 && current.getDate() === 1 && current.getHours() < 8
    next.setFullYear(isYearStart ? current.getFullYear() : current.getFullYear() + 1, 0, 1)
  }
  return next
}

const nextGenerationDate = computed(() => getNextGenerationDate(selectedPeriod.value, now.value))
const countdownText = computed(() => {
  const remaining = Math.max(0, nextGenerationDate.value.getTime() - now.value.getTime())
  const totalHours = Math.floor(remaining / 3600000)
  const days = Math.floor(totalHours / 24)
  const hours = totalHours % 24
  const minutes = Math.floor((remaining % 3600000) / 60000)
  const seconds = Math.floor((remaining % 60000) / 1000)
  return `${days}天 ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})
const nextGenerationLabel = computed(() => {
  const date = nextGenerationDate.value
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 08:00 自动生成`
})

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

onMounted(() => {
  loadReports()
  countdownTimer = window.setInterval(() => { now.value = new Date() }, 1000)
})

onUnmounted(() => {
  if (countdownTimer) {
    window.clearInterval(countdownTimer)
    countdownTimer = null
  }
})
</script>

<style scoped>
.report-center { padding: 28px; background: var(--bg-gradient), var(--bg); min-height: 100%; color: var(--text); }
.report-header { display:flex; justify-content:space-between; align-items:flex-end; gap:24px; } .report-header h1 { margin:4px 0 8px; font: 700 34px/1.1 Georgia,serif; letter-spacing:.03em; } .report-header p { margin:0; color:var(--muted); } .eyebrow { color:var(--accent)!important; letter-spacing:.18em; font:12px Arial,sans-serif; }
.report-toolbar { display:flex; align-items:center; gap:18px; margin:28px 0; padding:13px 16px; } .report-toolbar .muted-text { flex:1; }
.report-layout { display:grid; grid-template-columns:minmax(240px,.65fr) minmax(500px,1.7fr); gap:22px; } .report-intro { padding:32px 22px; min-height:430px; background:var(--sidebar-bg); color:var(--sidebar-text); border:1px solid var(--line); position:relative; overflow:hidden; } .report-intro:after { content:''; position:absolute; right:-60px; bottom:-80px; width:240px; height:240px; border:1px solid var(--sidebar-border); transform:rotate(35deg); } .intro-mark { color:var(--accent); font:bold 48px Georgia,serif; line-height:.75; } .intro-mark small { font:12px Arial,sans-serif; letter-spacing:.2em; } .report-intro h2 { margin:42px 0 16px; font:32px/1.3 Georgia,serif; } .report-intro h2 em { color:var(--accent); font-style:normal; } .report-intro p { color:var(--sidebar-muted); line-height:1.8; max-width:300px; } .period-notes { display:grid; gap:9px; margin-top:30px; font-size:calc(12rem / 14); color:var(--sidebar-muted); } .period-notes span { display:flex; gap:10px; } .period-notes b { color:var(--sidebar-text); min-width:42px; }
.countdown-block { margin-top:24px; padding-top:16px; border-top:1px solid var(--sidebar-border); } .countdown-label { display:block; color:var(--sidebar-muted); font-size:calc(12rem / 14); } .countdown-block strong { display:block; margin:5px 0 2px; color:var(--accent); font:700 25px/1.2 Georgia,serif; letter-spacing:.03em; } .countdown-block small { color:var(--sidebar-muted); font-size:calc(11rem / 14); }
.history-panel { min-width:0; padding:18px; } .history-panel :deep(.el-table) { --el-table-header-bg-color:var(--surface); } .history-count { color:var(--muted); font-size:calc(12rem / 14); } .period-badge { display:inline-block; min-width:44px; padding:2px 7px; text-align:center; border:1px solid currentColor; font-size:calc(12rem / 14); } .period-weekly { color:#3e8790; background:#edf6f5; } .period-monthly { color:#1b7168; background:#edf5ef; } .period-quarterly { color:#7b5d91; background:#f4eff7; } .period-yearly { color:#a65e3b; background:#fbf0e8; }
@media (max-width: 900px) { .report-center { padding:18px; } .report-header, .report-toolbar { align-items:flex-start; flex-direction:column; } .report-layout { grid-template-columns:1fr; } .report-intro { min-height:unset; } }
@media print { .report-center { display:none; } }
</style>

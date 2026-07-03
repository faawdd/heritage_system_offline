<template>
  <el-dialog
    :model-value="modelValue"
    width="920px"
    top="4vh"
    :destroy-on-close="false"
    @close="emit('update:modelValue', false)"
  >
    <template #header>
      <div class="preview-header">
        <span>{{ pageTitle || '不可移动文物采集登记表预览' }}</span>
        <el-button type="primary" plain size="small" @click="handlePrint">打印</el-button>
      </div>
    </template>

    <div class="preview-scroll-wrap" v-loading="loading">
      <div ref="previewRef" class="a4-paper">
        <header class="paper-hero">
          <h2 class="paper-title">不可移动文物采集登记表</h2>
          <p class="paper-subtitle">管理系统内嵌预览</p>
          <div class="hero-tags">
            <span class="hero-tag">A4 预览</span>
            <span class="hero-tag">可直接打印</span>
            <span class="hero-tag">只读展示</span>
          </div>
        </header>

        <section class="paper-section">
          <h3 class="section-title">基础信息</h3>
          <div class="info-grid">
            <div class="info-item info-item-span-2">
              <label>名称</label>
              <p>{{ readField('name') }}</p>
            </div>
            <div class="info-item">
              <label>编号</label>
              <p>{{ readField('survey_code', 'sip_code') }}</p>
            </div>
            <div class="info-item">
              <label>文物类别</label>
              <p>{{ readField('category_label', 'category') }}</p>
            </div>
            <div class="info-item">
              <label>保护级别</label>
              <p>{{ readField('level_label', 'protection_level_label', 'level', 'protection_level') }}</p>
            </div>
            <div class="info-item">
              <label>时代</label>
              <p>{{ readField('era') }}</p>
            </div>
            <div class="info-item">
              <label>保存现状</label>
              <p>{{ readField('preservation_status') }}</p>
            </div>
          </div>
        </section>

        <section class="paper-section">
          <h3 class="section-title">位置与坐标</h3>
          <div class="info-grid">
            <div class="info-item info-item-span-2">
              <label>行政区划</label>
              <p>{{ regionText }}</p>
            </div>
            <div class="info-item info-item-span-2">
              <label>详细地址</label>
              <p class="multiline">{{ readField('address') }}</p>
            </div>
            <div class="info-item">
              <label>经度</label>
              <p>{{ readField('longitude') }}</p>
            </div>
            <div class="info-item">
              <label>纬度</label>
              <p>{{ readField('latitude') }}</p>
            </div>
          </div>
        </section>

        <section class="paper-section">
          <h3 class="section-title">管理信息</h3>
          <div class="info-grid">
            <div class="info-item">
              <label>权属</label>
              <p>{{ readField('ownership') }}</p>
            </div>
            <div class="info-item">
              <label>管理责任人/单位</label>
              <p>{{ readField('manager', 'management_unit') }}</p>
            </div>
          </div>
        </section>

        <section class="paper-section">
          <h3 class="section-title">内容说明</h3>
          <div class="long-text-block">
            <h4>文物简介</h4>
            <p class="multiline">{{ readField('description', 'brief') }}</p>
          </div>
          <div class="long-text-block">
            <h4>备注</h4>
            <p class="multiline">{{ readField('remarks', 'remark') }}</p>
          </div>
        </section>

        <footer class="signature-footer">
          <div class="signature-title">签章信息</div>
          <div class="signature-grid">
            <div class="signature-item">
              <label>审核人</label>
              <span>{{ readField('reviewer_display', 'reviewer_name', 'reviewer') }}</span>
            </div>
            <div class="signature-item">
              <label>日期</label>
              <span>{{ signatureDate }}</span>
            </div>
            <div class="signature-item signature-item-span-2">
              <label>单位</label>
              <span>{{ signatureUnit }}</span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  record: {
    type: Object,
    default: () => ({}),
  },
  pageTitle: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])
const previewRef = ref(null)

const regionText = computed(() => {
  const province = String(props.record?.province || '').trim()
  const city = String(props.record?.city || '').trim()
  const county = String(props.record?.county || '').trim()
  const township = String(props.record?.township || '').trim()
  const village = String(props.record?.village || '').trim()
  const text = [province, city, county, township, village].filter(Boolean).join(' / ')
  return text || '——'
})

const signatureDate = computed(() => {
  const raw = props.record?.reviewed_at || props.record?.updated_at || props.record?.created_at || ''
  if (!raw) {
    return new Date().toISOString().slice(0, 10)
  }
  return String(raw).slice(0, 10)
})

const signatureUnit = computed(() => {
  const value =
    props.record?.collect_unit ||
    props.record?.management_unit ||
    props.record?.manager ||
    '鄯善县文化体育广播电视和旅游局（文物局）'
  return String(value || '').trim() || '鄯善县文化体育广播电视和旅游局（文物局）'
})

function readField(...keys) {
  for (const key of keys) {
    const value = props.record?.[key]
    if (value === 0) {
      return '0'
    }
    if (value !== null && value !== undefined && String(value).trim() !== '') {
      return String(value)
    }
  }
  return '——'
}

function handlePrint() {
  const node = previewRef.value
  if (!node) {
    ElMessage.error('预览内容不可用')
    return
  }

  const printWindow = window.open('', '_blank', 'width=1024,height=768')
  if (!printWindow) {
    ElMessage.error('浏览器拦截了打印窗口，请允许弹窗后重试')
    return
  }

  const html = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>文物登记表打印</title>
    <style>
      @page { size: A4; margin: 10mm; }
      body { margin: 0; background: #fff; font-family: "PingFang SC", "Microsoft YaHei", sans-serif; }
      .a4-paper { width: 190mm; margin: 0 auto; }
      .paper-hero { border: 1px solid #dbe2ef; background: #f7f9ff; padding: 4mm 5mm; margin-bottom: 5mm; }
      .paper-title { text-align: center; margin: 1mm 0 1mm; font-size: 22px; }
      .paper-subtitle { text-align: center; margin: 0 0 2mm; font-size: 12px; color: #666; }
      .hero-tags { text-align: center; }
      .hero-tag { display: inline-block; margin: 0 2mm; padding: 1mm 2.5mm; border: 1px solid #c8d3ea; border-radius: 999px; font-size: 11px; color: #3a4f77; }
      .paper-section { border: 1px solid #d7dbe2; margin-bottom: 4mm; }
      .section-title { margin: 0; padding: 2.5mm 3mm; font-size: 13px; background: #f5f7fb; border-bottom: 1px solid #d7dbe2; color: #24324a; }
      .info-grid { display: grid; grid-template-columns: 1fr 1fr; }
      .info-item { border-right: 1px solid #d7dbe2; border-bottom: 1px solid #d7dbe2; padding: 2.5mm 3mm; }
      .info-item:nth-child(2n) { border-right: none; }
      .info-item-span-2 { grid-column: span 2; border-right: none; }
      .info-item label { display: block; color: #60708d; font-size: 11px; margin-bottom: 1mm; }
      .info-item p { margin: 0; font-size: 12px; color: #131b2a; }
      .long-text-block { padding: 3mm; border-bottom: 1px solid #d7dbe2; }
      .long-text-block:last-child { border-bottom: none; }
      .long-text-block h4 { margin: 0 0 1.5mm; font-size: 12px; color: #3a4b68; }
      .multiline { line-height: 1.6; white-space: pre-wrap; min-height: 56px; }
      .paper-section,
      .long-text-block,
      .signature-footer { break-inside: avoid-page; page-break-inside: avoid; }
      .signature-footer { border: 1px solid #d7dbe2; padding: 3mm; margin-top: 4mm; }
      .signature-title { font-size: 12px; color: #2b3a55; margin-bottom: 2mm; font-weight: 600; }
      .signature-grid { display: grid; grid-template-columns: 1fr 1fr; }
      .signature-item { border: 1px solid #d7dbe2; border-right: none; border-bottom: none; padding: 2mm 2.5mm; }
      .signature-item:nth-child(2n) { border-right: 1px solid #d7dbe2; }
      .signature-item-span-2 { grid-column: span 2; border-right: 1px solid #d7dbe2; }
      .signature-item label { display: inline-block; min-width: 56px; color: #6a7893; font-size: 11px; }
      .signature-item span { color: #111b2f; font-size: 12px; }
    </style>
  </head>
  <body>${node.outerHTML}</body>
</html>`

  printWindow.document.open()
  printWindow.document.write(html)
  printWindow.document.close()
  printWindow.focus()
  printWindow.print()
}
</script>

<style scoped>
.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 8px;
}

.preview-scroll-wrap {
  max-height: 82vh;
  overflow: auto;
  background: #eef2f8;
  padding: 16px;
  border-radius: 8px;
}

.a4-paper {
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto;
  background: #fff;
  box-shadow: 0 8px 24px rgba(40, 52, 78, 0.14);
  padding: 10mm;
  box-sizing: border-box;
}

.paper-hero {
  border: 1px solid #dbe2ef;
  background: linear-gradient(180deg, #f7f9ff 0%, #fdfdff 100%);
  padding: 4mm 5mm;
  margin-bottom: 5mm;
}

.paper-title {
  text-align: center;
  margin: 1mm 0 1mm;
  font-size: 22px;
  color: #0f1729;
  letter-spacing: 1px;
}

.paper-subtitle {
  text-align: center;
  margin: 0 0 2mm;
  color: #5e6b82;
  font-size: 12px;
}

.hero-tags {
  text-align: center;
}

.hero-tag {
  display: inline-block;
  margin: 0 6px;
  padding: 2px 8px;
  border: 1px solid #c8d3ea;
  border-radius: 999px;
  font-size: 11px;
  color: #3a4f77;
  background: #fff;
}

.paper-section {
  border: 1px solid #d7dbe2;
  margin-bottom: 4mm;
  background: #fff;
}

.section-title {
  margin: 0;
  padding: 9px 12px;
  font-size: 13px;
  color: #24324a;
  background: #f5f7fb;
  border-bottom: 1px solid #d7dbe2;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.info-item {
  border-right: 1px solid #d7dbe2;
  border-bottom: 1px solid #d7dbe2;
  padding: 10px 12px;
  min-height: 64px;
}

.info-item:nth-child(2n) {
  border-right: none;
}

.info-item-span-2 {
  grid-column: span 2;
  border-right: none;
}

.info-item label {
  display: block;
  color: #60708d;
  font-size: 11px;
  margin-bottom: 6px;
}

.info-item p {
  margin: 0;
  font-size: 13px;
  color: #131b2a;
}

.long-text-block {
  padding: 12px;
  border-bottom: 1px solid #d7dbe2;
}

.long-text-block:last-child {
  border-bottom: none;
}

.long-text-block h4 {
  margin: 0 0 6px;
  font-size: 12px;
  color: #3a4b68;
}

.multiline {
  line-height: 1.6;
  white-space: pre-wrap;
  min-height: 56px;
}

.signature-footer {
  border: 1px solid #d7dbe2;
  padding: 12px;
  margin-top: 14px;
  background: #fbfcff;
}

.signature-title {
  margin-bottom: 8px;
  font-size: 12px;
  color: #2b3a55;
  font-weight: 600;
}

.signature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.signature-item {
  border: 1px solid #d7dbe2;
  border-right: none;
  border-bottom: none;
  padding: 8px 10px;
}

.signature-item:nth-child(2n) {
  border-right: 1px solid #d7dbe2;
}

.signature-item-span-2 {
  grid-column: span 2;
  border-right: 1px solid #d7dbe2;
}

.signature-item label {
  display: inline-block;
  min-width: 70px;
  color: #6a7893;
  font-size: 12px;
}

.signature-item span {
  color: #111b2f;
  font-size: 13px;
}

@media print {
  .a4-paper {
    box-shadow: none;
    width: 190mm;
    min-height: auto;
    padding: 0;
  }

  .paper-section,
  .long-text-block,
  .signature-footer {
    break-inside: avoid-page;
    page-break-inside: avoid;
  }
}

@media (max-width: 900px) {
  .a4-paper {
    width: 100%;
    min-height: auto;
    padding: 14px;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .info-item,
  .info-item:nth-child(2n),
  .info-item-span-2 {
    grid-column: span 1;
    border-right: none;
  }

  .signature-grid {
    grid-template-columns: 1fr;
  }

  .signature-item,
  .signature-item:nth-child(2n),
  .signature-item-span-2 {
    grid-column: span 1;
    border-right: 1px solid #d7dbe2;
  }
}
</style>
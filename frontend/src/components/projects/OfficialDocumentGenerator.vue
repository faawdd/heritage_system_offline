<template>
  <div class="official-doc-generator">
    <h4>公文一键生成</h4>
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="110px"
      status-icon
      class="doc-form"
    >
      <el-form-item label="公文类型" prop="documentType">
        <el-select v-model="form.documentType" placeholder="请选择要生成的公文类型" style="width: 100%">
          <el-option label="上报请示" value="qing_shi" />
          <el-option label="企业复函" value="fu_han" />
        </el-select>
      </el-form-item>

      <el-form-item label="核心诉求" prop="userInput">
        <el-input
          v-model="form.userInput"
          type="textarea"
          :rows="6"
          placeholder="例如：市局，我们想查一下某古墓葬的保护范围，因为有企业要在旁边盖工厂"
        />
        <div class="hint-text">
          AI 将自动把口语化诉求转为规范公文，并按模板生成 .docx。
        </div>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="generating" @click="handleGenerate">
          一键生成公文
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { generateProjectOfficialDocument } from '../../api/projectApi'

const props = defineProps({
  projectId: {
    type: [String, Number],
    required: true
  },
  projectDetail: {
    type: Object,
    default: () => ({})
  }
})

const formRef = ref()
const generating = ref(false)

const form = reactive({
  documentType: 'qing_shi',
  userInput: ''
})

const rules = {
  documentType: [{ required: true, message: '请选择公文类型', trigger: 'change' }],
  userInput: [{ required: true, message: '请输入核心诉求', trigger: 'blur' }]
}

function getDefaultFilename() {
  const dateSuffix = new Date().toISOString().slice(0, 10)
  if (form.documentType === 'qing_shi') {
    return `上报请示-${dateSuffix}.docx`
  }
  return `企业复函-${dateSuffix}.docx`
}

function decodeFilenameFromDisposition(dispositionHeader) {
  if (!dispositionHeader) {
    return ''
  }

  const utf8Match = dispositionHeader.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1])
  }

  const plainMatch = dispositionHeader.match(/filename="?([^";]+)"?/i)
  if (plainMatch?.[1]) {
    return plainMatch[1]
  }

  return ''
}

function triggerDownload(blobData, filename) {
  const blob = new Blob([blobData], {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

async function parseBlobErrorMessage(error) {
  const blobData = error?.response?.data
  if (!(blobData instanceof Blob)) {
    return error?.message || '公文生成失败'
  }
  try {
    const text = await blobData.text()
    const parsed = JSON.parse(text)
    return parsed?.message || parsed?.detail || '公文生成失败'
  } catch {
    return '公文生成失败'
  }
}

async function handleGenerate() {
  const isValid = await formRef.value?.validate().catch(() => false)
  if (!isValid) {
    return
  }

  generating.value = true
  try {
    const payload = {
      docType: form.documentType,
      userInput: form.userInput
    }

    const response = await generateProjectOfficialDocument(props.projectId, payload)
    const disposition = response?.headers?.['content-disposition'] || ''
    const filename = decodeFilenameFromDisposition(disposition) || getDefaultFilename()
    triggerDownload(response.data, filename)
    ElMessage.success('公文生成成功，已开始下载')
  } catch (error) {
    const message = await parseBlobErrorMessage(error)
    ElMessage.error(message)
  } finally {
    generating.value = false
  }
}
</script>

<style scoped>
.official-doc-generator {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.official-doc-generator h4 {
  margin: 0 0 12px;
  font-size: 15px;
}

.doc-form {
  max-width: 760px;
}

.hint-text {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}
</style>

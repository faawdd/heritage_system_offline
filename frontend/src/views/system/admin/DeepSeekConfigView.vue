<template>
  <section>
    <header class="page-header">
      <h1>DeepSeek 配置</h1>
      <p>配置公文 AI 生成所需的 API 参数与系统提示词。</p>
    </header>

    <div class="card top-space" v-loading="loading">
      <el-form :model="form" label-width="140px" style="max-width: 900px">
        <el-form-item label="API Key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            placeholder="输入新 API Key（留空则不修改）"
          />
          <div class="hint">当前：{{ form.api_key_masked || '未配置' }}</div>
        </el-form-item>

        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" placeholder="https://api.deepseek.com/v1" />
        </el-form-item>

        <el-form-item label="模型名称">
          <el-input v-model="form.model" placeholder="deepseek-chat" />
        </el-form-item>

        <el-form-item label="Temperature">
          <el-input v-model="form.temperature" placeholder="0.3" />
          <div class="hint">推荐 0.2 - 0.4，数值越低越稳定。</div>
        </el-form-item>

        <el-form-item label="System Prompt">
          <el-input
            v-model="form.system_prompt"
            type="textarea"
            :rows="16"
            placeholder="可自定义系统提示词，留空则后端使用默认提示词"
          />
        </el-form-item>

        <el-form-item>
          <el-button :loading="saving" type="primary" @click="saveConfig">保存配置</el-button>
          <el-button :loading="loading" @click="loadConfig">刷新</el-button>
        </el-form-item>
      </el-form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchDeepSeekConfig, updateDeepSeekConfig } from '../../../api/system/systemApi'

const loading = ref(false)
const saving = ref(false)

const form = reactive({
  api_key: '',
  api_key_masked: '',
  base_url: 'https://api.deepseek.com/v1',
  model: 'deepseek-chat',
  temperature: '0.3',
  system_prompt: ''
})

async function loadConfig() {
  loading.value = true
  try {
    const result = await fetchDeepSeekConfig()
    if (!result.success) {
      throw new Error(result.message || '加载配置失败')
    }
    const data = result.data || {}
    form.api_key = ''
    form.api_key_masked = data.api_key_masked || ''
    form.base_url = data.base_url || 'https://api.deepseek.com/v1'
    form.model = data.model || 'deepseek-chat'
    form.temperature = String(data.temperature || '0.3')
    form.system_prompt = data.system_prompt || ''
  } catch (error) {
    ElMessage.error(error?.message || '加载配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const payload = {
      api_key: form.api_key,
      base_url: (form.base_url || '').trim(),
      model: (form.model || '').trim(),
      temperature: String(form.temperature || '').trim(),
      system_prompt: form.system_prompt || ''
    }
    const result = await updateDeepSeekConfig(payload)
    if (!result.success) {
      throw new Error(result.message || '保存配置失败')
    }
    ElMessage.success('配置保存成功')
    await loadConfig()
  } catch (error) {
    ElMessage.error(error?.message || '保存配置失败')
  } finally {
    saving.value = false
  }
}

loadConfig()
</script>

<style scoped>
.hint {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
}
</style>

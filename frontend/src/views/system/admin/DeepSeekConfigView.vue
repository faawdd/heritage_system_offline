<template>
  <section>
    <header class="page-header">
      <h1>AI 后端配置</h1>
      <p>统一配置本地 Ollama、DeepSeek、阿里云百炼（Qwen）、Kimi、Gemini 和 ChatGPT。</p>
    </header>

    <el-alert
      class="top-space"
      type="info"
      :closable="false"
      title="Ollama 部署在当前系统服务器时，通常可使用 http://127.0.0.1:11434；跨服务器部署可填写可访问地址。"
    />

    <div class="card top-space" v-loading="loading">
      <el-form :model="form" label-width="150px" style="max-width: 980px">
        <el-form-item label="AI 后端">
          <el-radio-group v-model="form.provider" @change="applyProviderDefaults">
            <el-radio-button v-for="provider in providers" :key="provider.value" :value="provider.value">
              {{ provider.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="API Key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            :disabled="form.provider === 'ollama'"
            placeholder="输入新 API Key（留空则保留当前配置）"
          />
          <div class="hint">当前：{{ form.api_key_masked || (form.provider === 'ollama' ? '本地模型无需配置' : '未配置') }}</div>
        </el-form-item>

        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" placeholder="服务地址" />
        </el-form-item>

        <el-form-item label="模型名称">
          <el-select
            v-model="form.model"
            filterable
            allow-create
            default-first-option
            placeholder="检测后选择，或直接输入模型名"
            style="width: 100%"
          >
            <el-option v-for="model in models" :key="model" :label="model" :value="model" />
          </el-select>
          <div class="model-actions">
            <el-button :loading="detecting" @click="detectModels">自动检测模型列表</el-button>
            <el-button :loading="testing" type="success" plain @click="testConnection">测试连接</el-button>
            <span class="hint">检测不到时仍可手工输入模型标识。</span>
          </div>
          <el-alert
            v-if="connectionResult"
            class="connection-result"
            type="success"
            :closable="false"
            :title="`连接成功：${connectionResult.provider} / ${connectionResult.model}，耗时 ${connectionResult.elapsed_ms} ms`"
            :description="`模型响应：${connectionResult.response}；模型列表检测${connectionResult.model_list_supported ? `成功（${connectionResult.model_count} 个）` : '不支持或失败，但对话接口可用'}`"
          />
        </el-form-item>

        <el-form-item label="Temperature">
          <el-slider v-model="form.temperature" :min="0" :max="1" :step="0.05" show-input />
        </el-form-item>

        <el-form-item label="最大输出 Token">
          <el-input-number v-model="form.max_tokens" :min="128" :max="8192" :step="128" />
          <div class="hint">项目导入固定使用紧凑摘要，可在不降低识别质量的情况下显著减少输入 token。</div>
        </el-form-item>

        <el-form-item label="请求超时（秒）">
          <el-input-number v-model="form.timeout" :min="10" :max="600" :step="10" />
        </el-form-item>

        <el-form-item label="公文 System Prompt">
          <el-input
            v-model="form.system_prompt"
            type="textarea"
            :rows="14"
            placeholder="留空使用系统默认公文生成提示词"
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

import { fetchAIModels, fetchDeepSeekConfig, testAIConnection, updateDeepSeekConfig } from '../../../api/system/systemApi'

const loading = ref(false)
const saving = ref(false)
const detecting = ref(false)
const testing = ref(false)
const connectionResult = ref(null)
const providers = ref([])
const models = ref([])

const form = reactive({
  provider: 'deepseek',
  api_key: '',
  api_key_masked: '',
  base_url: 'https://api.deepseek.com/v1',
  model: 'deepseek-chat',
  temperature: 0.2,
  max_tokens: 1800,
  timeout: 120,
  system_prompt: ''
})

function applyProviderDefaults(provider) {
  const selected = providers.value.find((item) => item.value === provider)
  if (!selected) return
  form.base_url = selected.base_url
  form.model = selected.model
  form.api_key = ''
  form.api_key_masked = provider === 'ollama' ? '本地模型无需配置' : ''
  models.value = []
  connectionResult.value = null
}

async function loadConfig() {
  loading.value = true
  try {
    const result = await fetchDeepSeekConfig()
    if (!result.success) throw new Error(result.message || '加载配置失败')
    const data = result.data || {}
    providers.value = data.providers || []
    Object.assign(form, {
      provider: data.provider || 'deepseek',
      api_key: '',
      api_key_masked: data.api_key_masked || '',
      base_url: data.base_url || 'https://api.deepseek.com/v1',
      model: data.model || 'deepseek-chat',
      temperature: Number(data.temperature ?? 0.2),
      max_tokens: Number(data.max_tokens ?? 1800),
      timeout: Number(data.timeout ?? 120),
      system_prompt: data.system_prompt || ''
    })
  } catch (error) {
    ElMessage.error(error?.message || '加载配置失败')
  } finally {
    loading.value = false
  }
}

async function detectModels() {
  detecting.value = true
  try {
    const result = await fetchAIModels({
      provider: form.provider,
      api_key: form.api_key,
      base_url: form.base_url,
      model: form.model
    })
    if (!result.success) throw new Error(result.message || '检测模型失败')
    models.value = result.data?.models || []
    if (models.value.length && !models.value.includes(form.model)) form.model = models.value[0]
    ElMessage.success(`检测到 ${models.value.length} 个模型`)
  } catch (error) {
    ElMessage.error(error?.message || '检测模型失败')
  } finally {
    detecting.value = false
  }
}

async function testConnection() {
  testing.value = true
  connectionResult.value = null
  try {
    const result = await testAIConnection({
      provider: form.provider,
      api_key: form.api_key,
      base_url: form.base_url,
      model: form.model,
      timeout: Math.min(Number(form.timeout) || 30, 30)
    })
    if (!result.success) throw new Error(result.message || '连接测试失败')
    connectionResult.value = result.data
    ElMessage.success('AI 后端连接成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.message || '连接测试失败')
  } finally {
    testing.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const result = await updateDeepSeekConfig({ ...form, temperature: String(form.temperature) })
    if (!result.success) throw new Error(result.message || '保存配置失败')
    ElMessage.success('AI 后端配置保存成功')
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
  color: var(--muted);
  font-size: calc(12rem / 14);
}

.model-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.connection-result {
  margin-top: 10px;
}
</style>

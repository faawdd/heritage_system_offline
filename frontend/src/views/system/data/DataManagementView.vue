<template>
  <section>
    <header class="page-header">
      <h1>数据管理</h1>
      <p>从四普系统抓取"文物矢量图"边界坐标，替换KML叠加检查使用的单点坐标</p>
    </header>

    <div class="card top-space">
      <h3>四普系统文物边界导入</h3>
      <p class="hint">
        Cookie 需手动从浏览器登录四普系统后，通过开发者工具的网络请求中复制 Cookie 请求头粘贴到下方；
        导入会调用后端可复用的 <code>import_sipu_boundary</code> 命令写入数据库。
      </p>

      <el-form label-width="140px" style="max-width: 760px">
        <el-form-item label="四普 Cookie" required>
          <el-input
            v-model="form.cookie"
            type="textarea"
            :rows="3"
            placeholder="粘贴四普系统登录后的 Cookie 请求头"
          />
        </el-form-item>

        <el-form-item label="导入范围">
          <el-radio-group v-model="form.scope">
            <el-radio label="missing">仅补全缺失本体边界的文物点</el-radio>
            <el-radio label="all">全部文物点（覆盖已导入数据）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="行政区划代码">
          <el-input v-model="form.user_county" placeholder="可选，四普系统搜索接口的 userCounty 参数" style="max-width: 320px" />
        </el-form-item>

        <el-form-item label="试跑数量限制">
          <el-input-number v-model="form.limit" :min="0" :max="2000" placeholder="0 表示不限制" />
          <div class="hint">建议首次先填写较小数值（如 10）验证 Cookie 有效后，再置 0 全量导入。</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="running" @click="runImport">开始导入</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="card top-space" v-if="result">
      <h3>导入结果</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <p class="stat-title">处理总数</p>
          <p class="stat-value">{{ result.total }}</p>
        </div>
        <div class="stat-card">
          <p class="stat-title">成功匹配并写入</p>
          <p class="stat-value">{{ result.matched }}</p>
        </div>
        <div class="stat-card">
          <p class="stat-title">未匹配</p>
          <p class="stat-value">{{ (result.unmatched || []).length }}</p>
        </div>
        <div class="stat-card">
          <p class="stat-title">匹配但无边界数据</p>
          <p class="stat-value">{{ (result.no_geometry || []).length }}</p>
        </div>
      </div>

      <div class="top-space" v-if="(result.unmatched || []).length">
        <h4>未匹配文物点</h4>
        <el-table :data="result.unmatched" stripe size="small" max-height="260">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="name" label="文物名称" min-width="180" />
          <el-table-column label="候选名称" min-width="260">
            <template #default="scope">{{ (scope.row.candidates || []).join('、') || '-' }}</template>
          </el-table-column>
        </el-table>
      </div>

      <div class="top-space" v-if="(result.no_geometry || []).length">
        <h4>匹配成功但四普未登记矢量图</h4>
        <el-table :data="result.no_geometry" stripe size="small" max-height="260">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="name" label="文物名称" min-width="180" />
        </el-table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { runSipuBoundaryImport } from '../../../api/system/systemApi'

const running = ref(false)
const result = ref(null)

const form = reactive({
  cookie: '',
  scope: 'missing',
  user_county: '',
  limit: 0
})

async function runImport() {
  if (!form.cookie.trim()) {
    ElMessage.warning('请先填写四普系统 Cookie')
    return
  }

  running.value = true
  result.value = null
  try {
    const response = await runSipuBoundaryImport({
      cookie: form.cookie.trim(),
      scope: form.scope,
      user_county: form.user_county.trim(),
      limit: form.limit || 0
    })
    if (!response.success) {
      throw new Error(response.message || '导入失败')
    }
    result.value = response.data
    ElMessage.success(`导入完成，成功写入 ${response.data?.matched ?? 0} 条`)
  } catch (error) {
    ElMessage.error(error?.message || '导入失败')
  } finally {
    running.value = false
  }
}
</script>

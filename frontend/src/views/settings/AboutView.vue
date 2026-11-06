<template>
  <section class="page-card about-page">
    <div class="about-head">
      <img :src="appLogo" alt="" class="about-logo">
      <div>
        <h2>{{ systemName }}</h2>
        <p class="muted-text">离线桌面版</p>
      </div>
    </div>

    <el-descriptions :column="1" border class="about-info">
      <el-descriptions-item label="当前版本">
        <div class="version-row">
          <button type="button" class="version-button" :disabled="updateState.status === 'checking'" @click="checkDesktopUpdates">
            {{ appVersion }}
          </button>
          <span v-if="updateState.status === 'checking'" role="status">正在检查更新…</span>
          <span v-else-if="updateState.status === 'available'" role="status">
            发现新版本 {{ updateState.latestVersion }}
            <button type="button" class="version-button" @click="downloadUpdate">前往下载</button>
          </span>
          <span v-else-if="updateState.status === 'current'" role="status">暂无新版本</span>
          <span v-else-if="updateState.status === 'error' || updateState.status === 'unavailable'" class="update-error" role="status">
            检查更新失败：{{ updateState.error }}
          </span>
          <span v-else>点击版本号检查更新</span>
        </div>
      </el-descriptions-item>
      <el-descriptions-item label="开源协议">
        <a :href="licenseUrl" target="_blank" rel="noopener noreferrer">{{ licenseName }}</a>
      </el-descriptions-item>
      <el-descriptions-item label="项目主页">
        <a href="https://github.com/faawdd/heritage_system_offline" target="_blank" rel="noopener noreferrer">
          github.com/faawdd/heritage_system_offline
        </a>
      </el-descriptions-item>
    </el-descriptions>

    <h3>系统简介</h3>
    <p class="about-text">
      面向文物保护单位的综合管理平台，覆盖不可移动文物档案、巡查、地图展示、建设项目审核与报告生成等业务。
      离线桌面版所有数据存储于本机，无需联网即可使用。
    </p>

    <h3>主要功能</h3>
    <ul class="feature-list">
      <li v-for="item in features" :key="item.title">
        <strong>{{ item.title }}</strong>
        <span>{{ item.desc }}</span>
      </li>
    </ul>

    <h3>开源协议</h3>
    <p class="about-text">
      本项目基于 Apache License 2.0 开源，允许在遵守协议条款的前提下自由使用、修改与分发。
      软件按“现状”提供，不附带任何明示或暗示的担保。
    </p>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchSystemAbout } from '../../api/dashboardApi'
import appLogo from '../../assets/logo.png'
import { checkDesktopUpdates, openUpdateDownload, updateState } from '../../utils/desktopUpdates'

const appVersion = __APP_VERSION__
const systemName = ref('文物综合管理平台')
const licenseName = ref('Apache License 2.0')
const licenseUrl = ref('https://www.apache.org/licenses/LICENSE-2.0')

async function downloadUpdate() {
  try {
    await openUpdateDownload()
  } catch (error) {
    ElMessage.error(error?.message || '无法打开下载页面')
  }
}

const features = [
  { title: '数据看板', desc: '文物总量、类别、级别与巡查情况一览。' },
  { title: '文物档案与一张图', desc: '不可移动文物档案管理，地图展示与统计分析。' },
  { title: '野外采集', desc: '文物点位、坐标与照片信息采集录入。' },
  { title: '巡查管理', desc: '巡查记录登记、查询与归档。' },
  { title: '项目管理', desc: '建设项目登记，结合 KML/KMZ 空间数据核验与文物叠加分析。' },
  { title: 'GIS 工具', desc: 'KML 管理、OVKML 转换，以及离线地图瓦片管理。' },
  { title: '报告中心', desc: '定期自动生成并导出各类统计报告。' },
  { title: '系统管理', desc: '用户、用户组、权限、操作日志与数据管理。' }
]

onMounted(async () => {
  try {
    const result = await fetchSystemAbout()
    const data = result?.data || {}
    systemName.value = data.system_name || systemName.value
    licenseName.value = data.license || licenseName.value
    licenseUrl.value = data.license_url || licenseUrl.value
  } catch {
    // 使用内置默认值
  }
})
</script>

<style scoped>
.about-page {
  max-width: 880px;
}

.about-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.about-head h2 {
  margin: 0;
}

.about-logo {
  width: 56px;
  height: 56px;
  object-fit: contain;
}

.about-info {
  margin-bottom: 8px;
}

.version-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.version-button {
  padding: 0;
  border: 0;
  background: none;
  color: #168b5d;
  cursor: pointer;
  font: inherit;
  text-decoration: underline;
}

.version-button:disabled {
  cursor: wait;
  opacity: .6;
}

.update-error {
  color: #c45656;
}

h3 {
  margin: 24px 0 8px;
}

.about-text {
  line-height: 1.8;
  margin: 0;
}

.feature-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
}

.feature-list strong {
  margin-right: 8px;
}
</style>

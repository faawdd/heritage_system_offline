<template>
  <section class="about-page card">
    <header class="about-header">
      <h1>{{ systemName }}</h1>
      <p>面向基层文物保护、巡查与项目管理的本地化离线桌面系统。</p>
    </header>

    <div class="about-grid">
      <article class="about-item">
        <h2>系统信息</h2>
        <ul>
          <li><span>系统名称</span><strong>{{ systemName }}</strong></li>
          <li><span>当前版本</span><strong>{{ versionText }}</strong></li>
          <li><span>运行平台</span><strong>{{ runtimeLabel }}</strong></li>
          <li><span>前端框架</span><strong>Vue 3 + Element Plus</strong></li>
          <li><span>后端框架</span><strong>Django</strong></li>
        </ul>
      </article>

      <article class="about-item">
        <h2>离线能力</h2>
        <ul>
          <li><span>数据目录</span><strong>支持首启自动配置与手动切换</strong></li>
          <li><span>日志目录</span><strong>支持首启自动配置与手动切换</strong></li>
          <li><span>数据库</span><strong>首次启动自动迁移并创建</strong></li>
          <li><span>桌面封装</span><strong>Electron 多平台发行</strong></li>
        </ul>
      </article>

      <article class="about-item about-item--wide">
        <h2>离线运行逻辑（技术说明）</h2>
        <div class="tech-flow">
          <p>
            系统采用 Electron + 内置 Django 后端 + 本地 SQLite 的离线架构。
            桌面端启动时会先拉起本地后端服务，再由前端加载本机静态资源，业务数据默认落在本地数据目录，
            因此在无外网条件下仍可完成日常管理、查询、导入导出和打印归档。
          </p>
          <ul>
            <li><span>步骤 1</span><strong>桌面程序启动并初始化运行环境（数据目录/日志目录）</strong></li>
            <li><span>步骤 2</span><strong>后端执行数据库迁移与基础账号检查</strong></li>
            <li><span>步骤 3</span><strong>本地服务监听后加载前端页面，进入业务模块</strong></li>
            <li><span>步骤 4</span><strong>数据读写、统计、预览与打印全部走本地链路</strong></li>
          </ul>
        </div>
      </article>

      <article class="about-item">
        <h2>需联网功能</h2>
        <ul>
          <li><span>四普系统抓取</span><strong>需访问四普业务地址并提供有效会话（JSESSIONID）</strong></li>
          <li><span>在线底图服务</span><strong>天地图在线瓦片在离线网络不可用时会受限</strong></li>
          <li><span>外部接口联调</span><strong>涉及第三方服务/跨系统接口调用时需联网</strong></li>
          <li><span>发布与更新</span><strong>GitHub Actions 打包发布及远程更新检查需联网</strong></li>
        </ul>
      </article>

      <article class="about-item">
        <h2>核心功能简介</h2>
        <ul>
          <li><span>文物档案管理</span><strong>支持不可移动文物档案维护、详情预览与A4打印归档</strong></li>
          <li><span>采集与巡查管理</span><strong>支持采集记录、巡查记录、异常统计与趋势分析</strong></li>
          <li><span>数据联动与导入</span><strong>支持CSV导入导出及跨模型双向同步</strong></li>
          <li><span>GIS与KML能力</span><strong>支持KML/KMZ管理、叠加检查与冲突分析</strong></li>
          <li><span>项目审批管理</span><strong>支持项目流程、空间核验与过程日志留痕</strong></li>
        </ul>
      </article>

      <article class="about-item about-item--wide">
        <h2>版权与说明</h2>
        <p>本系统用于基层文物保护业务数字化管理，支持离线部署和本地数据留存。</p>
        <ul class="copyright-list">
          <li><span>版权所有</span><strong>北辰</strong></li>
          <li><span>作者</span><strong>北辰</strong></li>
          <li><span>联系邮箱</span><strong>1443469207@qq.com</strong></li>
          <li><span>联系电话</span><strong>13899665458</strong></li>
        </ul>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { useAppStore } from '../../../stores/system/appStore'
import { fetchSystemVersion } from '../../../api/dashboardApi'

const appStore = useAppStore()
const systemName = computed(() => appStore.systemName)
const versionText = ref('-')

const runtimeLabel = computed(() => {
  const runtime = window?.desktopMeta?.runtime
  return runtime === 'electron' ? 'Electron Desktop' : 'Web Browser'
})

onMounted(async () => {
  try {
    const response = await fetchSystemVersion()
    versionText.value = response?.data?.version || '-'
  } catch {
    versionText.value = '-'
  }
})
</script>

<style scoped>
.about-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px;
}

.about-header h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.2;
}

.about-header p {
  margin: 12px 0 0;
  color: #5f6c7b;
  font-size: 15px;
}

.about-grid {
  margin-top: 20px;
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.about-item {
  background: #fff;
  border: 1px solid #e6edf5;
  border-radius: 12px;
  padding: 18px;
}

.about-item h2 {
  margin: 0 0 12px;
  font-size: 18px;
}

.about-item ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.about-item li {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 14px;
}

.about-item li span {
  color: #6b7280;
}

.about-item li strong {
  text-align: right;
  color: #1f2937;
}

.about-item--wide {
  grid-column: 1 / -1;
}

.about-item p {
  margin: 0;
  color: #475569;
  line-height: 1.7;
}

.tech-flow {
  display: grid;
  gap: 12px;
}

.copyright-list {
  margin-top: 12px;
}

@media (max-width: 900px) {
  .about-grid {
    grid-template-columns: 1fr;
  }
}
</style>

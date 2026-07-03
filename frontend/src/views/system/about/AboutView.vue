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
        <h2>版权与说明</h2>
        <p>
          本系统用于基层文物保护业务数字化管理，支持离线部署和本地数据留存。
          如需技术支持，请联系系统维护人员。
        </p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

import { useAppStore } from '../../../stores/system/appStore'

const appStore = useAppStore()
const systemName = computed(() => appStore.systemName)

const runtimeLabel = computed(() => {
  const runtime = window?.desktopMeta?.runtime
  return runtime === 'electron' ? 'Electron Desktop' : 'Web Browser'
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

@media (max-width: 900px) {
  .about-grid {
    grid-template-columns: 1fr;
  }
}
</style>

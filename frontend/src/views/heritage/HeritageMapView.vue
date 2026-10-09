<template>
  <section class="heritage-fullscreen-page">
    <HeritageMapCanvas
      class="heritage-fullscreen-map"
      :points="points"
      :active-levels="activeLevels"
      :keyword="keyword"
      :show-point-popup="true"
      @open-detail="openDetail"
    />

    <div class="heritage-menu-toggle">
      <el-button type="primary" plain @click="menuVisible = !menuVisible">
        {{ menuVisible ? '隐藏菜单' : '显示菜单' }}
      </el-button>
    </div>

    <aside v-show="menuVisible" class="heritage-floating-menu">
      <div class="heritage-menu-header">
        <div>
          <h3>文物一张图</h3>
          <p>全屏地图 + 悬浮菜单</p>
        </div>
        <el-button link type="primary" @click="menuVisible = false">收起</el-button>
      </div>

      <el-scrollbar class="heritage-menu-scroll">
        <el-collapse v-model="activePanels">
          <el-collapse-item title="筛选条件" name="filters">
            <div class="heritage-form-block">
              <el-input v-model="keyword" placeholder="输入文物名称搜索" clearable />
              <el-checkbox-group v-model="activeLevels" class="heritage-level-group">
                <el-checkbox label="GB">全国重点</el-checkbox>
                <el-checkbox label="SB">自治区级</el-checkbox>
                <el-checkbox label="XB">县级</el-checkbox>
                <el-checkbox label="DS">尚未定级</el-checkbox>
              </el-checkbox-group>
              <el-button type="primary" @click="loadData" :loading="loading">刷新点位</el-button>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-scrollbar>
    </aside>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchHeritageMapPoints } from '../../api/heritageApi'
import HeritageMapCanvas from '../../components/heritage/HeritageMapCanvas.vue'

const loading = ref(false)
const keyword = ref('')
const points = ref([])
const activeLevels = ref(['GB', 'SB', 'XB', 'DS'])
const menuVisible = ref(true)
const activePanels = ref(['filters'])

function openDetail(payload) {
  if (!payload?.id || !payload.preview_url) {
    return
  }
  window.open(payload.preview_url, '_blank', 'noopener,noreferrer')
}

async function loadData() {
  loading.value = true
  try {
    const result = await fetchHeritageMapPoints()
    if (!result.success) {
      throw new Error(result.message || '加载点位失败')
    }
    points.value = result.rows || []
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

loadData()
</script>

<style scoped>
.heritage-fullscreen-page {
  position: relative;
  height: 100dvh;
  min-height: 100dvh;
  background: #f1f5f9;
  overflow: hidden;
}

.heritage-fullscreen-map {
  height: 100%;
  border-radius: 0;
}

.heritage-menu-toggle {
  position: absolute;
  left: 16px;
  top: 16px;
  z-index: 20;
}

.heritage-floating-menu {
  position: absolute;
  left: 16px;
  top: 62px;
  bottom: 16px;
  width: min(420px, calc(100vw - 32px));
  z-index: 18;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe5ef;
  border-radius: 14px;
  box-shadow: 0 14px 36px rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(5px);
  display: flex;
  flex-direction: column;
}

.heritage-menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 14px 8px;
  border-bottom: 1px solid #e2e8f0;
}

.heritage-menu-header h3 {
  margin: 0;
  font-size: calc(16rem / 14);
}

.heritage-menu-header p {
  margin: 4px 0 0;
  font-size: calc(12rem / 14);
  color: #64748b;
}

.heritage-menu-scroll {
  flex: 1;
  padding: 8px 10px 12px;
}

.heritage-form-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.heritage-level-group {
  margin: 2px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 1024px) {
  .heritage-fullscreen-page {
    height: 100dvh;
    min-height: 100dvh;
  }

  .heritage-floating-menu {
    top: 58px;
    left: 10px;
    right: 10px;
    width: auto;
    bottom: 10px;
  }

  .heritage-menu-toggle {
    left: 10px;
    top: 10px;
  }
}
</style>

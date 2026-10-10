<template>
  <section class="page-card appearance-settings">
    <div class="appearance-head">
      <div>
        <h2>外观设置</h2>
        <p class="muted-text">自定义界面字体、字号与默认主题偏好，仅对当前浏览器生效，立即应用。</p>
      </div>
      <el-button @click="resetAppearance">恢复默认</el-button>
    </div>

    <el-form label-width="110px" class="appearance-form">
      <el-form-item label="界面字体">
        <el-select :model-value="appearanceState.fontFamily" style="width: 260px" @change="(v) => setAppearance({ fontFamily: v })">
          <el-option v-for="item in FONT_OPTIONS" :key="item.value" :label="item.label" :value="item.value">
            <span :style="{ fontFamily: item.stack }">{{ item.label }}</span>
          </el-option>
        </el-select>
      </el-form-item>

      <el-form-item label="字号">
        <div class="font-size-row">
          <el-slider
            :model-value="appearanceState.fontSize"
            :min="FONT_SIZE_RANGE.min"
            :max="FONT_SIZE_RANGE.max"
            :step="FONT_SIZE_RANGE.step"
            show-input
            @input="(v) => setAppearance({ fontSize: v })"
          />
        </div>
      </el-form-item>

      <el-form-item label="默认主题偏好">
        <el-radio-group :model-value="appearanceState.themeMode" @change="(v) => setAppearance({ themeMode: v })">
          <el-radio-button v-for="item in THEME_MODES" :key="item.value" :value="item.value">{{ item.label }}</el-radio-button>
        </el-radio-group>
        <div class="hint-text">选择“跟随系统”时，界面会随操作系统的亮/暗模式自动切换。</div>
      </el-form-item>

      <el-form-item label="效果预览">
        <div class="appearance-preview">
          <strong>文物综合管理平台</strong>
          <p>这是一段预览文字：不可移动文物 0123456789 ABC abc。</p>
          <el-button type="primary" size="small">示例按钮</el-button>
        </div>
      </el-form-item>
    </el-form>
  </section>
</template>

<script setup>
import {
  appearanceState,
  FONT_OPTIONS,
  FONT_SIZE_RANGE,
  THEME_MODES,
  resetAppearance,
  setAppearance
} from '../../utils/appearance'
</script>

<style scoped>
.appearance-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.appearance-head h2 {
  margin: 0 0 6px;
}
.appearance-form {
  max-width: 720px;
}
.font-size-row {
  width: 100%;
  padding-right: 12px;
}
.appearance-preview {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--border, rgba(128, 128, 128, 0.35));
  border-radius: 8px;
  font-family: var(--app-font-family);
  font-size: var(--app-font-size);
}
.appearance-preview p {
  margin: 8px 0 12px;
}
</style>

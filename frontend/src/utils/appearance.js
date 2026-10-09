import { reactive } from 'vue'

const APPEARANCE_KEY = 'heritage_appearance'
const THEME_MODE_KEY = 'heritage_theme_mode'

export const FONT_OPTIONS = [
  { label: '系统默认', value: 'default', stack: "'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif" },
  { label: '微软雅黑', value: 'yahei', stack: "'Microsoft YaHei', '微软雅黑', 'PingFang SC', sans-serif" },
  { label: '苹方', value: 'pingfang', stack: "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif" },
  { label: '思源黑体', value: 'noto-sans', stack: "'Noto Sans SC', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif" },
  { label: '宋体', value: 'songti', stack: "'Songti SC', 'SimSun', '宋体', serif" },
  { label: '楷体', value: 'kaiti', stack: "'Kaiti SC', 'KaiTi', '楷体', serif" },
  { label: '等宽字体', value: 'mono', stack: "'SF Mono', Consolas, 'Courier New', monospace" }
]

export const FONT_SIZE_RANGE = { min: 12, max: 20, step: 1 }
export const THEME_MODES = [
  { label: '跟随系统', value: 'system' },
  { label: '亮色', value: 'light' },
  { label: '暗色', value: 'dark' }
]

export const DEFAULT_APPEARANCE = { fontFamily: 'default', fontSize: 14, themeMode: 'system' }

function sanitize(raw = {}) {
  const fontFamily = FONT_OPTIONS.some((item) => item.value === raw.fontFamily) ? raw.fontFamily : DEFAULT_APPEARANCE.fontFamily
  const size = Number(raw.fontSize)
  const fontSize = Number.isFinite(size)
    ? Math.min(FONT_SIZE_RANGE.max, Math.max(FONT_SIZE_RANGE.min, Math.round(size)))
    : DEFAULT_APPEARANCE.fontSize
  const themeMode = THEME_MODES.some((item) => item.value === raw.themeMode) ? raw.themeMode : DEFAULT_APPEARANCE.themeMode
  return { fontFamily, fontSize, themeMode }
}

function load() {
  let stored = {}
  try {
    stored = JSON.parse(localStorage.getItem(APPEARANCE_KEY) || '{}') || {}
  } catch {
    stored = {}
  }
  const legacyTheme = localStorage.getItem(THEME_MODE_KEY)
  return sanitize({ ...stored, themeMode: legacyTheme || stored.themeMode })
}

export const appearanceState = reactive(load())

export function resolveTheme(mode) {
  if (mode === 'dark' || mode === 'light') {
    return mode
  }
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyAppearance() {
  const root = document.documentElement
  const stack = (FONT_OPTIONS.find((item) => item.value === appearanceState.fontFamily) || FONT_OPTIONS[0]).stack
  const size = appearanceState.fontSize
  root.style.setProperty('--app-font-family', stack)
  root.style.fontSize = `${size}px`
  root.style.setProperty('--app-font-size', `${size}px`)
  root.style.setProperty('--el-font-family', stack)
  root.style.setProperty('--el-font-size-base', `${size}px`)
  root.style.setProperty('--el-font-size-small', `${Math.max(size - 1, 10)}px`)
  root.style.setProperty('--el-font-size-extra-small', `${Math.max(size - 2, 10)}px`)
  root.style.setProperty('--el-font-size-large', `${size + 2}px`)
  root.setAttribute('data-theme', resolveTheme(appearanceState.themeMode))
}

export function setAppearance(patch = {}) {
  Object.assign(appearanceState, sanitize({ ...appearanceState, ...patch }))
  localStorage.setItem(
    APPEARANCE_KEY,
    JSON.stringify({ fontFamily: appearanceState.fontFamily, fontSize: appearanceState.fontSize })
  )
  localStorage.setItem(THEME_MODE_KEY, appearanceState.themeMode)
  applyAppearance()
}

export function resetAppearance() {
  setAppearance({ ...DEFAULT_APPEARANCE })
}

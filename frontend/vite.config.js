import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

// 版本号优先取当前 git tag（发布构建即 tag 本身），其次 APP_VERSION 环境变量，最后回退到 package.json
function resolveAppVersion() {
  if (process.env.APP_VERSION) return process.env.APP_VERSION.trim()
  try {
    const described = execSync('git describe --tags --always', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
    if (/^v?\d+\.\d+/.test(described)) return described
  } catch {
    // 无 git 或无 tag 时回退
  }
  const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8'))
  return pkg.version
}

const appVersion = resolveAppVersion()

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(/^\d/.test(appVersion) ? `v${appVersion}` : appVersion)
  },
  base: '/static/frontend/',
  build: {
    outDir: '../static/frontend',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }
          if (id.includes('element-plus') || id.includes('@vue') || id.includes('vue-router') || id.includes('pinia')) {
            return 'vendor-vue'
          }
          if (id.includes('echarts')) {
            return 'vendor-echarts'
          }
          if (id.includes('/ol/')) {
            return 'vendor-ol'
          }
          return 'vendor-misc'
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/media': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})

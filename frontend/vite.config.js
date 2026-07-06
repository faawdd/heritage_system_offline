import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendHost = process.env.HERITAGE_DESKTOP_BACKEND_HOST || '127.0.0.1'
const backendPort = process.env.HERITAGE_DESKTOP_BACKEND_PORT || '8000'
const backendTarget = `http://${backendHost}:${backendPort}`

export default defineConfig({
  plugins: [vue()],
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
        target: backendTarget,
        changeOrigin: true
      },
      '/media': {
        target: backendTarget,
        changeOrigin: true
      }
    }
  }
})

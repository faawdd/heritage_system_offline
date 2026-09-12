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
      },
      // 离线天地图瓦片由 Django 从 APP_DIR/static/tiles 提供；
      // Vite 的 base 为 /static/frontend/，不会自动代理 /static/tiles，
      // 若不显式转发，开发模式下地图瓦片会 404，无法调试离线底图。
      '/static/tiles': {
        target: backendTarget,
        changeOrigin: true
      },
      // DEM 瓦片等后端生成的静态资源同理转发。
      '/static/dem_tiles': {
        target: backendTarget,
        changeOrigin: true
      }
    }
  }
})

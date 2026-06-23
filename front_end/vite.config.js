import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, 'index.html'),
        algoConfig: resolve(__dirname, 'algo-config.html'),
        algoHealth: resolve(__dirname, 'algo-health.html')
      }
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false
  }
})

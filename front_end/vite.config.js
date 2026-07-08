import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './src')
    }
  },
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, 'index.html'),
        dashboard: resolve(__dirname, 'dashboard.html'),
        clues: resolve(__dirname, 'clues.html'),
        clueDetail: resolve(__dirname, 'clue-detail.html'),
        oneshot: resolve(__dirname, 'oneshot.html'),
        orderDetail: resolve(__dirname, 'order-detail.html'),
        distributor: resolve(__dirname, 'distributor.html'),
        verify: resolve(__dirname, 'verify.html'),
        backtest: resolve(__dirname, 'backtest.html'),
        algoArchitecture: resolve(__dirname, 'algo-architecture.html')
      }
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false
  }
})

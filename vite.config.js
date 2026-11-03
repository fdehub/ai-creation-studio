import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
const frontendPath = path => fileURLToPath(new URL(path, import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: Number(process.env.NOVEL_FRONTEND_PORT || 5273),
    strictPort: true,
    fs: {
      strict: true,
      allow: ['src', 'public', 'node_modules', 'index.html'].map(frontendPath),
      deny: ['.env', '.env.*', '*.{crt,pem}', '**/.git/**', '**/recoveredData.js', '**/*.db', '**/*.db-*', '**/*.sqlite*']
    },
    proxy: {
      '/api': {
        target: process.env.NOVEL_API_PROXY || 'http://127.0.0.1:8100',
        changeOrigin: true
      }
    }
  },
  preview: {
    host: '127.0.0.1', port: 5273, strictPort: true,
    proxy: { '/api': { target: process.env.NOVEL_API_PROXY || 'http://127.0.0.1:8100', changeOrigin: true } }
  }
})

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // Send /api requests to Flask, so the browser sees one site and keys stay on the server.
    proxy: {
      '/api': 'http://127.0.0.1:5000',
    },
  },
})

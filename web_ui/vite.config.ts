import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendTarget = process.env.VITE_TITAN_BACKEND_TARGET ?? 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': {
        target: backendTarget,
        ws: true,
      },
      '/healthz': {
        target: backendTarget,
      },
    },
  },
  build: {
    outDir: '../titan_cli/ui_web/static',
    emptyOutDir: true,
  },
})

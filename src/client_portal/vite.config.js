/* global process */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: process.env.VITE_PORT || 5173,
    strictPort: false,
  },
  resolve: {
    alias: {
      '@': '/src',
      '@components': '/src/components',
      '@types': '/src/types',
      '@utils': '/src/utils',
    },
  },
})

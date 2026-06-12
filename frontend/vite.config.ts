import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
// Mode-based config:
// - Default (dev, vite build): SPA mode with Vue Router + Element Plus
// - Library (vite build --mode library): Vue Flow ER diagram as IIFE bundle
export default defineConfig(({ mode }) => {
  // Library mode — builds only er-diagram.js for SSR mount
  if (mode === 'library') {
    return {
      plugins: [vue()],
      build: {
        lib: {
          entry: resolve(__dirname, 'src/pages/er-diagram/main.ts'),
          name: 'ErDiagram',
          fileName: 'er-diagram',
          formats: ['iife'],
        },
        outDir: 'dist/assets',
        emptyOutDir: false,
      },
    }
  }

  // Default SPA mode for development and default build
  return {
    plugins: [vue()],
    server: {
      proxy: {
        '/mcp': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      // SPA mode — no library targeting
    },
  }
})
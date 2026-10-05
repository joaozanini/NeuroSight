/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// O navegador só fala com /api (mesma origem do dev server): o proxy leva para a API em :8000,
// inclusive os WebSockets (ws: true) da sessão ao vivo. Assim o vídeo também é same-origin e o
// <video> consegue tocar e buscar (Range).
export default defineConfig({
  plugins: [react()],
  server: {
    // Usa a porta do ambiente (PORT) quando setada (ex.: painel de preview); senão 5173.
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
  },
})

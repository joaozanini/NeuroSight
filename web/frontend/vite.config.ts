import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// O browser só fala com /api (mesma origem do dev server) -> proxy para a API em :8000.
// Isso também faz o vídeo ser same-origin (sem CORS) para o <video> tocar e buscar (Range).
export default defineConfig({
  plugins: [react()],
  server: {
    // Usa a porta do ambiente (PORT) quando setada (ex.: painel de preview); senão 5173.
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})

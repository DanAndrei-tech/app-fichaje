import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Hacia dónde reenvía Vite las peticiones /api durante el desarrollo.
// - En Docker: http://backend:8000 (lo define docker-compose.yml).
// - En tu máquina: http://localhost:8000.
// Gracias al proxy, frontend y API comparten origen, como en producción.
const apiProxyTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': apiProxyTarget,
    },
    // En Docker sobre Windows/macOS hace falta sondear para detectar cambios.
    watch: {
      usePolling: process.env.WATCH_POLLING === 'true',
    },
  },
})

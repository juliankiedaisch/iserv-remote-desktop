import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    hmr: {
      // HMR WebSocket must go through the external proxy
      host: 'test-desktop.hub.mdg-hamburg.de',
      protocol: 'wss',
      clientPort: 443,
    },
    proxy: {
      '/api': {
        target: 'http://localhost:5021',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://localhost:5021',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'build',
  },
});

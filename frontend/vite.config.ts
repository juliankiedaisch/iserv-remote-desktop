import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
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

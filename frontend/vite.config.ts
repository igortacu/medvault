import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Only the institution routes live under /api/v1 on the backend; every
      // other router is mounted at the root, so strip the /api prefix for those.
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) =>
          path.startsWith('/api/v1/') ? path : path.replace(/^\/api/, ''),
      },
    },
  },
});

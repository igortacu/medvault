import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Nothing embeds this app, and framing is the way to trick someone into a consent click.
// `same-origin` keeps the Origin header that the backend's cross-origin check reads.
const securityHeaders = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'same-origin',
};

// For the built app only: the dev server's hot reload needs inline scripts. Blob frames
// and images are how originals are shown. A production web server must send the same.
const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  'frame-src blob:',
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ');

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  preview: {
    headers: {
      ...securityHeaders,
      'Content-Security-Policy': contentSecurityPolicy,
    },
  },
  server: {
    headers: securityHeaders,
    // Under docker compose: file events don't cross the bind mount, so poll.
    watch: process.env.VITE_USE_POLLING ? { usePolling: true } : undefined,
    proxy: {
      // Only the institution routes live under /api/v1 on the backend; every
      // other router is mounted at the root, so strip the /api prefix for those.
      '/api': {
        // docker compose points this at the backend container.
        target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
        rewrite: (path) =>
          path.startsWith('/api/v1/') ? path : path.replace(/^\/api/, ''),
      },
    },
  },
});

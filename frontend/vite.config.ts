import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Browser security headers for the pages the UI serves (OWASP ZAP reported them
// missing). The policy allows only our own origin; blob: is for the document
// viewer, which shows originals fetched as blobs in an <img> or <iframe>.
function contentSecurityPolicy(dev: boolean): string {
  return [
    "default-src 'self'",
    // The dev server injects React Fast Refresh as an inline script; a production
    // build has no inline scripts, so it does not get 'unsafe-inline'.
    dev ? "script-src 'self' 'unsafe-inline'" : "script-src 'self'",
    // UI components set inline style attributes.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "frame-src 'self' blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ');
}

function securityHeaders(dev: boolean): Record<string, string> {
  return {
    'Content-Security-Policy': contentSecurityPolicy(dev),
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    headers: securityHeaders(true),
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
  // `vite preview` serves the production build: the strict policy.
  preview: {
    headers: securityHeaders(false),
  },
});

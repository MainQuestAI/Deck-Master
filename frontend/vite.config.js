import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

function cleanWebDistAssets() {
  const assetsDir = fileURLToPath(new URL('../rust/web-dist/assets', import.meta.url));
  return {
    name: 'clean-web-dist-assets',
    buildStart() {
      // Remove stale generated bundles while keeping tracked rust/web-dist/index.html intact.
      rmSync(assetsDir, { recursive: true, force: true });
    },
  };
}

export function isAllowedDevOrigin(origin, port = 5173) {
  if (!origin) return true;
  return origin === `http://127.0.0.1:${port}` || origin === `http://localhost:${port}`;
}

export default defineConfig(() => {
  // Read only the explicit process environment; do not load .env files.
  const target = process.env.DECK_SERVE_URL;
  const devPort = 5173;
  if (target !== undefined) {
    let url;
    try { url = new URL(target); }
    catch { throw new Error('DECK_SERVE_URL 必须是有效的本机服务 URL'); }
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
      throw new Error('DECK_SERVE_URL 只允许本机地址：127.0.0.1 或 localhost');
    }
  }
  return {
    envDir: false,
    plugins: [react(), cleanWebDistAssets()],
    build: {
      outDir: '../rust/web-dist',
      // The tracked shell also lets cargo build without npm. Only assets are generated.
      emptyOutDir: false,
      rollupOptions: {
        input: fileURLToPath(new URL('./src/main.jsx', import.meta.url)),
        output: {
          entryFileNames: 'assets/deck.js',
          assetFileNames: 'assets/deck[extname]',
        },
      },
    },
    server: {
      port: devPort,
      host: '127.0.0.1',
      proxy: target ? {
        '/api': {
          target,
          changeOrigin: true,
          bypass(req, res) {
            if (!isAllowedDevOrigin(req.headers.origin, devPort)) {
              res.statusCode = 403;
              res.setHeader('Content-Type', 'application/json; charset=utf-8');
              res.end(JSON.stringify({ error: '仅接受本机开发服务的 Origin' }));
              return false;
            }
            return undefined;
          },
          configure(proxy) {
            proxy.on('proxyReq', (proxyReq, req) => {
              if (isAllowedDevOrigin(req.headers.origin, devPort)) {
                proxyReq.setHeader('Origin', new URL(target).origin);
              }
            });
          },
        },
      } : undefined,
    },
  };
});

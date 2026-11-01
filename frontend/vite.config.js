import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig(() => {
  // Read only the explicit process environment; do not load .env files.
  const target = process.env.DECK_SERVE_URL;
  if (target !== undefined) {
    let url;
    try { url = new URL(target); }
    catch { throw new Error('DECK_SERVE_URL 必须是有效的本机服务 URL'); }
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) {
      throw new Error('DECK_SERVE_URL 只允许本机地址：127.0.0.1、localhost 或 ::1');
    }
  }
  return {
    envDir: false,
    plugins: [react()],
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
      port: 5173,
      host: '127.0.0.1',
      proxy: target ? {
        '/api': {
          target,
          changeOrigin: true,
          configure(proxy) {
            proxy.on('proxyReq', request => request.setHeader('Origin', new URL(target).origin));
          },
        },
      } : undefined,
    },
  };
});

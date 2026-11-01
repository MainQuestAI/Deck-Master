import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig(() => {
  // Read only the explicit process environment; do not load .env files.
  const target = process.env.DECK_SERVE_URL;
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

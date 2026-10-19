import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxy = {
    target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000',
    // Preserve the browser Host/Origin pair for the backend's CSRF checks.
    changeOrigin: false,
  };
  return {
    plugins: [react()],
    server: { port: 5173, strictPort: true, proxy: { '/api': proxy } },
    preview: { port: 4173, strictPort: true, proxy: { '/api': proxy } },
    build: { outDir: 'dist', sourcemap: false },
  };
});

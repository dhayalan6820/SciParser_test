import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig(({ mode }) => {
  // Load env from the project root (unified .env), then Frontend/ overrides
  const projectRoot = path.resolve(__dirname, '..');
  const rootEnv = loadEnv(mode, projectRoot, '');
  const localEnv = loadEnv(mode, process.cwd(), '');
  const env = { ...rootEnv, ...localEnv };
  const backendTarget = env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000';

  return {
    plugins: [
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5000,
      allowedHosts: true,
      proxy: {
        '/sciparser': {
          target: backendTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  };
});

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import process from 'node:process';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    cors: false,
    proxy: { '/api': { target: process.env.PORTAL_API_PROXY_TARGET ?? 'http://localhost:8001', rewrite: path => path.replace(/^\/api/, '') } },
  },
  test: { include: ['src/**/*.test.{ts,tsx}'], environment: 'jsdom', setupFiles: './src/test-setup.ts', restoreMocks: true },
});

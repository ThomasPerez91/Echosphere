import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import process from 'node:process';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000', rewrite: path => path.replace(/^\/api/, '') } },
  },
  test: { include: ['src/**/*.test.{ts,tsx}'], environment: 'jsdom', setupFiles: './src/test-setup.ts', restoreMocks: true,
    // jsdom role queries are slow on shared CI runners; budgets only, assertions unchanged.
    testTimeout: 20000 },
});

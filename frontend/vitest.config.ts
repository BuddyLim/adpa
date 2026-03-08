import { defineConfig } from 'vitest/config'
import viteReact from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [tsconfigPaths({ projects: ['./tsconfig.json'] }), viteReact()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      exclude: [
        'src/routeTree.gen.ts',
        'src/integrations/**',
        'src/router.tsx',
        'coverage',
        'dist',
        'eslint.config.js',
        'prettier.config.js',
        'vite.config.ts',
        'vitest.config.ts',
      ],
    },
  },
})

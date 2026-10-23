import { defineConfig, devices } from '@playwright/test'

const PORT = Number(process.env.E2E_PORT ?? 8099)
const PERF_PORT = 8098
const python = process.env.E2E_PYTHON ?? '../.venv/bin/python'

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', testIgnore: /perf\.spec\.ts/, use: { ...devices['Desktop Chrome'] } },
    {
      name: 'perf',
      testMatch: /perf\.spec\.ts/,
      use: { ...devices['Pixel 5'], baseURL: `http://127.0.0.1:${PERF_PORT}` },
    },
  ],
  webServer: [
    {
      command: `${python} serve.py`,
      cwd: '.',
      url: `http://127.0.0.1:${PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { E2E_PORT: String(PORT) },
    },
    {
      // 12 demo cases + 48 extra = 60 active cases for the performance budget
      command: `${python} serve.py`,
      cwd: '.',
      url: `http://127.0.0.1:${PERF_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { E2E_PORT: String(PERF_PORT), E2E_CASES: '48' },
    },
  ],
})

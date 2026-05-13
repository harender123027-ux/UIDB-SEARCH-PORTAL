// @ts-check
const { defineConfig, devices } = require("@playwright/test");

/**
 * Run E2E tests with frontend and backend running.
 * Start backend: cd backend && .venv/bin/uvicorn app.main:app --port 8000
 * Start frontend: npm run dev
 * Then: npm run test:e2e
 */
module.exports = defineConfig({
  testDir: "./tests",
  testMatch: "*.spec.cjs",  // Only match spec files directly in tests/
  testIgnore: ["**/unit/**", "**/unit-legacy/**", "**/fixtures/**"],  // Ignore non-Playwright tests
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "html",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
  },
});

/**
 * Playwright config — L4 E2E (docs/03-test-plan.md §2 L4).
 *
 * E2E always runs against the stacked real build: real backend on :8000,
 * real frontend on :3000 (docs/03-test-plan.md §2 note).
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --port 8000",
      url: "http://localhost:8000/api/healthz",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "pnpm --dir frontend dev",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});

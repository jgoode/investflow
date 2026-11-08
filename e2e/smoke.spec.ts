/**
 * ITER-01 smoke scenario (docs/07 §4 deliverable #6):
 *   open app → placeholder page renders; healthz responds ok.
 * (No network mocking needed per docs/07 §4.)
 */
import { expect, test } from "@playwright/test";

const BACKEND = "http://localhost:8000";

test("healthz responds ok with a version", async ({ request }) => {
  const resp = await request.get(`${BACKEND}/api/healthz`);

  expect(resp.ok()).toBeTruthy();
  const body = (await resp.json()) as { status?: string; version?: string };
  expect(body.status).toBe("ok");
  expect(body.version).toMatch(/^\d+\.\d+\.\d+/);
});

test("open app → root redirects to /dashboard placeholder (not yet built)", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText(/not yet built/i)).toBeVisible();
});

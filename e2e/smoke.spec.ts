import { expect, test } from "@playwright/test";

const BACKEND = "http://localhost:8000";

test("healthz responds ok with a version", async ({ request }) => {
  const resp = await request.get(`${BACKEND}/api/healthz`);

  expect(resp.ok()).toBeTruthy();
  const body = (await resp.json()) as { status?: string; version?: string };
  expect(body.status).toBe("ok");
  expect(body.version).toMatch(/^\d+\.\d+\.\d+/);
});

test("register → dashboard → logout → login journey", async ({
  page,
}) => {
  const username = `e2e_${Date.now()}`;
  const password = "correct-horse-10";

  await page.goto("/register");
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByLabel("Display name (optional)").fill("E2E User");
  await page.getByRole("textbox", { name: /^Password/ }).first().fill(password);
  await page.getByRole("textbox", { name: /^Password confirmation/ }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText(/not yet built/i)).toBeVisible();

  await page.getByRole("button", { name: "Menu" }).click();
  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByRole("textbox", { name: /^Password/ }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

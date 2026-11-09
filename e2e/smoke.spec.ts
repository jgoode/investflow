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
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText(/net worth/i)).toBeVisible();

  await page.context().clearCookies();
  await page.goto("/login");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByRole("textbox", { name: /^Password/ }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("users management flow: list + own-password change", async ({ page }) => {
  const username = `u_${Date.now()}`;
  const oldPassword = "correct-horse-10";
  const newPassword = "new-secure-pass-22";

  await page.goto("/register");
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByRole("textbox", { name: /^Password/ }).first().fill(oldPassword);
  await page.getByRole("textbox", { name: /^Password confirmation/ }).fill(oldPassword);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/users");
  await expect(page.getByRole("heading", { name: "Users" })).toBeVisible();
  await expect(page.getByRole("cell", { name: username })).toBeVisible();

  await page.getByLabel(/^Current password$/).fill(oldPassword);
  await page.getByLabel(/^New password$/).fill(newPassword);
  await page.getByLabel(/^Confirm new password$/).fill(newPassword);
  await page.getByRole("button", { name: "Change password" }).click();

  await page.context().clearCookies();
  await page.goto("/login");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByRole("textbox", { name: /^Password/ }).fill(newPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("categories CRUD flow with default account", async ({ page }) => {
  const username = `cat_${Date.now()}`;
  const categoryName = `Pet Supplies ${Date.now()}`;
  const password = "correct-horse-10";

  await page.goto("/register");
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByRole("textbox", { name: /^Password/ }).first().fill(password);
  await page.getByRole("textbox", { name: /^Password confirmation/ }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/categories");
  await expect(page.getByRole("heading", { name: "Categories" })).toBeVisible();
  await page.getByLabel("Name").fill(categoryName);
  await page.getByLabel("Flow").selectOption("expense");
  await page.getByRole("button", { name: "Save category" }).click();
  await expect(page.getByText("Category created.")).toBeVisible();

  const deleteButton = page.getByRole("button", { name: `Delete ${categoryName}` });
  await expect(deleteButton).toBeVisible();
  await deleteButton.click();
  await expect(deleteButton).toHaveCount(0);
});

test("reports monthly URL params are shareable and deterministic", async ({ page }) => {
  const username = `rep_${Date.now()}`;
  const password = "correct-horse-10";
  const now = new Date();
  const year = now.getUTCFullYear();
  const month = now.getUTCMonth();
  const monthNumber = String(month + 1).padStart(2, "0");
  const start = `${year}-${monthNumber}-01`;
  const end = new Date(Date.UTC(year, month + 1, 0)).toISOString().slice(0, 10);
  const period = `${year}-${monthNumber}`;

  await page.goto("/register");
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByRole("textbox", { name: /^Password/ }).first().fill(password);
  await page.getByRole("textbox", { name: /^Password confirmation/ }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/transactions");
  await page.getByLabel("Mode").selectOption("income");
  await page.getByLabel("Description").fill("Salary report seed");
  await page.getByLabel("Posting account").selectOption({ label: "Bank A" });
  await page.getByLabel("Category").selectOption({ label: "Salary" });
  await page.getByLabel("Amount (cents)").fill("12345");
  await page.getByRole("button", { name: "Post transaction" }).click();
  await expect(page.getByText("Transaction posted.")).toBeVisible();

  await page.goto(
    `/reports?kind=monthly&date_from=${start}&date_to=${end}&months=${period}`,
  );
  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();
  await expect(page.getByText("monthly")).toBeVisible();
  await expect(page.getByRole("cell", { name: `"${period}"` })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("cell", { name: `"${period}"` })).toBeVisible();
});

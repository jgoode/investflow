import path from "node:path";

import { expect, test } from "@playwright/test";

const BACKEND = "http://localhost:8000";

/** Fixture CSVs live in e2e/fixtures; Playwright runs from the repo root, and
 * import.meta.url is not usable in its CJS-transpiled specs. */
function fixturePath(name: string): string {
  return path.resolve(process.cwd(), "e2e", "fixtures", name);
}


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
  await page.getByLabel("Users table filter").fill(username);
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
  await page.getByLabel("Flow", { exact: true }).selectOption("expense");
  await page.getByRole("button", { name: "Save category" }).click();
  await expect(page.getByText("Category created.")).toBeVisible();

  const deleteButton = page.getByRole("button", { name: `Delete ${categoryName}` });
  await expect(deleteButton).toBeVisible();
  await deleteButton.click();
  await expect(deleteButton).toHaveCount(0);
});

test("navbar submenu reachability: brand link + Accounts submenu → transactions", async ({
  page,
}) => {
  const username = `nav_${Date.now()}`;
  const password = "correct-horse-10";

  await page.goto("/register");
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByRole("textbox", { name: /^Password/ }).first().fill(password);
  await page.getByRole("textbox", { name: /^Password confirmation/ }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Left brand link routes to /dashboard when launched from another page.
  await page.goto("/settings");
  await page.getByRole("link", { name: "InvestFlow home" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Top-level order per FR-X4a.
  const nav = page.getByRole("navigation", { name: "Primary navigation" });
  const labels = await nav
    .getByRole("link")
    .evaluateAll((links) =>
      links
        .map((link) => link.textContent?.trim() ?? "")
        .filter((label) =>
          ["Dashboard", "Accounts", "Investments", "Reporting", "Settings"].includes(label),
        ),
    );
  expect(labels).toEqual(["Dashboard", "Accounts", "Investments", "Reporting", "Settings"]);

  // Hover opens the Accounts submenu; its items navigate to reachable pages.
  await nav.getByRole("link", { name: "Accounts" }).hover();
  await expect(nav.getByRole("link", { name: "Chart of Accounts" })).toBeVisible();
  await nav.getByRole("link", { name: "Transactions" }).click();
  await expect(page).toHaveURL(/\/transactions$/);
  await expect(page.getByRole("heading", { name: "Transactions" })).toBeVisible();
});

test("investment import wizard: import positions + trades fixtures (FR-IMP-1)", async ({
  page,
}) => {
  const username = `imp_${Date.now()}`;
  const password = "correct-horse-10";

  await page.goto("/register");
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByRole("textbox", { name: /^Password/ }).first().fill(password);
  await page.getByRole("textbox", { name: /^Password confirmation/ }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Reach the Import center through the Investments submenu (Nav regression stays green).
  const nav = page.getByRole("navigation", { name: "Primary navigation" });
  await nav.getByRole("link", { name: "Investments" }).hover();
  await expect(nav.getByRole("link", { name: "Import" })).toBeVisible();
  await nav.getByRole("link", { name: "Import" }).click();
  await expect(page).toHaveURL(/\/investments\/import$/);
  await expect(page.getByRole("heading", { name: /import/i })).toBeVisible();

  // --- positions snapshot import (Brokerage A binding auto-selected) ---
  await page.getByLabel("Import kind").selectOption("positions");
  await page
    .getByLabel("CSV file")
    .setInputFiles(fixturePath("positions-snapshot.csv"));
  await page.getByRole("button", { name: "Run preview" }).click();
  await expect(page.getByText("Import preview")).toBeVisible();
  await expect(page.getByText(/MSFT/).first()).toBeVisible();
  await expect(page.getByText(/Brokerage A/).first()).toBeVisible();
  await page.getByRole("button", { name: "Confirm import" }).click();
  await expect(page.getByText(/Posted 1|imported/i)).toBeVisible();

  // Imported snapshot drives the positions page.
  await page.goto("/investments");
  await expect(page.getByText(/MSFT/i).first()).toBeVisible();

  // --- trade history import (brokerage binding auto-selected) ---
  await page.goto("/investments/import");
  await page.getByLabel("Import kind").selectOption("trades");
  await page
    .getByLabel("CSV file")
    .setInputFiles(fixturePath("trade-history.csv"));
  await page.getByRole("button", { name: "Run preview" }).click();
  await expect(page.getByText("Import preview")).toBeVisible();
  await page.getByRole("button", { name: "Confirm import" }).click();
  await expect(page.getByText(/Posted \d+/)).toBeVisible();

  // Dividend/fee rows landed as real ledger transactions (AC-IMP1e).
  const versions = await page.request.get(
    `${BACKEND}/api/transactions?date_from=2000-01-01&page_size=50`,
  );
  expect(versions.ok()).toBeTruthy();
  const ledger = (await versions.json()).transactions as Array<{ description: string }>;
  const descriptions = ledger.map((entry) => entry.description);
  expect(descriptions.some((text) => /Dividend AAPL/i.test(text))).toBe(true);
  expect(descriptions.some((text) => /Fee AAPL/i.test(text))).toBe(true);
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
  await page.getByLabel("Description", { exact: true }).fill("Salary report seed");
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

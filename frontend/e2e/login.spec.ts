import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8001";
const USER = `e2e_${Date.now()}`;
const PASS = "password123";

async function register() {
  const r = await fetch(`${API}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: USER, password: PASS }),
  });
  expect(r.status).toBe(201);
}

test("login succeeds, persists token, survives reload", async ({ page }) => {
  await register();
  await page.goto("/login");
  await page.getByPlaceholder("Username (min 3 chars)").fill(USER);
  await page.getByPlaceholder("Password (min 8 chars)").fill(PASS);
  await page.getByRole("button", { name: "Log in" }).click();
  // Must redirect off /login (catches infinite-loading regressions).
  await page.waitForURL("**/tracker", { timeout: 20000 });
  const token = await page.evaluate(() => localStorage.getItem("thedaaakhouse_token"));
  expect(token).toBeTruthy();
  await page.reload();
  await page.waitForURL("**/tracker", { timeout: 20000 });
  // Regression: loading must resolve to content or empty state, never hang.
  await expect(page.locator("body")).not.toContainText("Loading…", { timeout: 20000 });
  await expect(
    page.getByRole("heading", { name: "Job Tracker" })
  ).toBeVisible({ timeout: 20000 });
  await expect(page.getByText(/No applications yet|application/i).first()).toBeVisible();
});

test("wrong password shows error and re-enables the form (never stuck)", async ({ page }) => {
  await page.goto("/login");
  await page.getByPlaceholder("Username (min 3 chars)").fill("nobody");
  await page.getByPlaceholder("Password (min 8 chars)").fill("wrongpass1");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.locator("form p")).toContainText(/invalid/i, { timeout: 20000 });
  await expect(page.getByRole("button", { name: "Log in" })).toBeEnabled();
});

test("hung backend surfaces a timeout error instead of hanging", async ({ page }) => {
  // Blackhole the login call: never responds. Client must abort ~15s.
  await page.route("**/api/auth/login", () => new Promise(() => {}));
  await page.goto("/login");
  await page.getByPlaceholder("Username (min 3 chars)").fill("anyone");
  await page.getByPlaceholder("Password (min 8 chars)").fill("password123");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.locator("form")).toContainText(/timed out|unable to reach/i, { timeout: 30000 });
  await expect(page.getByRole("button", { name: "Log in" })).toBeEnabled();
});

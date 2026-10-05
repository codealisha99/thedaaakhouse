# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: frontend/e2e/login.spec.ts >> wrong password shows error and re-enables the form (never stuck)
- Location: frontend/e2e/login.spec.ts:30:5

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/login", waiting until "load"

```

# Test source

```ts
  1  | import { expect, test } from "@playwright/test";
  2  | 
  3  | const API = "http://127.0.0.1:8001";
  4  | const USER = `e2e_${Date.now()}`;
  5  | const PASS = "password123";
  6  | 
  7  | async function register() {
  8  |   const r = await fetch(`${API}/api/auth/register`, {
  9  |     method: "POST",
  10 |     headers: { "Content-Type": "application/json" },
  11 |     body: JSON.stringify({ username: USER, password: PASS }),
  12 |   });
  13 |   expect(r.status).toBe(201);
  14 | }
  15 | 
  16 | test("login succeeds, persists token, survives reload", async ({ page }) => {
  17 |   await register();
  18 |   await page.goto("/login");
  19 |   await page.getByPlaceholder("Username (min 3 chars)").fill(USER);
  20 |   await page.getByPlaceholder("Password (min 8 chars)").fill(PASS);
  21 |   await page.getByRole("button", { name: "Log in" }).click();
  22 |   // Must redirect off /login (catches infinite-loading regressions).
  23 |   await page.waitForURL("**/tracker", { timeout: 20000 });
  24 |   const token = await page.evaluate(() => localStorage.getItem("thedaaakhouse_token"));
  25 |   expect(token).toBeTruthy();
  26 |   await page.reload();
  27 |   await page.waitForURL("**/tracker", { timeout: 20000 });
  28 | });
  29 | 
  30 | test("wrong password shows error and re-enables the form (never stuck)", async ({ page }) => {
> 31 |   await page.goto("/login");
     |              ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  32 |   await page.getByPlaceholder("Username (min 3 chars)").fill("nobody");
  33 |   await page.getByPlaceholder("Password (min 8 chars)").fill("wrongpass1");
  34 |   await page.getByRole("button", { name: "Log in" }).click();
  35 |   await expect(page.locator("form p")).toContainText(/invalid/i, { timeout: 20000 });
  36 |   await expect(page.getByRole("button", { name: "Log in" })).toBeEnabled();
  37 | });
  38 | 
  39 | test("hung backend surfaces a timeout error instead of hanging", async ({ page }) => {
  40 |   // Blackhole the login call: never responds. Client must abort ~15s.
  41 |   await page.route("**/api/auth/login", () => new Promise(() => {}));
  42 |   await page.goto("/login");
  43 |   await page.getByPlaceholder("Username (min 3 chars)").fill("anyone");
  44 |   await page.getByPlaceholder("Password (min 8 chars)").fill("password123");
  45 |   await page.getByRole("button", { name: "Log in" }).click();
  46 |   await expect(page.locator("form")).toContainText(/timed out|unable to reach/i, { timeout: 30000 });
  47 |   await expect(page.getByRole("button", { name: "Log in" })).toBeEnabled();
  48 | });
  49 | 
```
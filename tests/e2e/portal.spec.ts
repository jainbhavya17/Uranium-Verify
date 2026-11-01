import { test, expect } from "@playwright/test";
import AxeBuilder from "axe-core";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const axeSource = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

test("public guidance, private route guard and accessible sign-in", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.getByLabel("User ID or registered email")).toHaveAttribute("type", "email");
  await page.addScriptTag({ content: axeSource });
  const issues = await page.evaluate(async () => {
    const result = await (window as unknown as { axe: typeof AxeBuilder }).axe.run();
    return result.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  });
  expect(issues).toEqual([]);
  await page.goto("/institution/dashboard");
  await expect(page.getByRole("heading", { name: "Sign in to your workspace" })).toBeVisible();
});

test("institution draft, automatic precheck and private access", async ({ page }) => {
  test.skip(
    !process.env.UV_E2E_EMAIL || !process.env.UV_E2E_PASSWORD,
    "Use dedicated local test credentials.",
  );
  await page.goto("/login");
  await page.getByLabel("User ID or registered email").fill(process.env.UV_E2E_EMAIL!);
  await page.getByLabel("Password", { exact: true }).fill(process.env.UV_E2E_PASSWORD!);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page).toHaveURL(/institution\/dashboard/);
  await page.getByRole("link", { name: "New application", exact: true }).click();
  await page.getByRole("button", { name: /Create draft & continue|Resume draft/ }).click();
  await page.getByLabel(/Authorized signatory/).fill("Browser test signatory");
  await expect(page.getByText(/Saved at/)).toBeVisible();
  await page.getByRole("link", { name: "Step 5 of 6: Precheck" }).click();
  await expect(
    page.getByRole("heading", { name: "Corrections needed before submission" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /Fix evidence/ }).first()).toBeVisible();
  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: "This workspace is restricted" })).toBeVisible();
});

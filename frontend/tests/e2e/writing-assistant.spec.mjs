import { test, expect } from "@playwright/test";

test("creator accepts a writing fix, re-checks, and requests review", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Fill / Sign in as Creator" }).click();
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeHidden({ timeout: 15_000 });
  await page.goto("/new");
  const quickStart = page.getByRole("dialog");
  if (await quickStart.isVisible()) await quickStart.getByRole("button", { name: "Got it" }).click();

  await page.getByPlaceholder("e.g. Holiday Season Sourdough Campaign").fill("Writing assistant journey");
  await page.getByPlaceholder(/Announce our organic oat elixir/).fill("Introduce our bakery and welcome our neighbors.");
  await page.getByPlaceholder(/Paste marketing copy/).fill(
    "Teh bakery accomodate our patrons. Its a more faster way to enjoy an all-natural bread. We we welcome our neighbors",
  );
  await page.getByRole("button", { name: "Run Brand Governance Check" }).click();

  await expect(page.getByText("Grammar and spelling", { exact: true })).toBeVisible({ timeout: 90_000 });
  const claimReason = page.getByText(/Claim 'all-natural' is ambiguous without certification or qualification/).first();
  await expect(claimReason).toBeVisible();
  const claimCard = claimReason.locator("xpath=ancestor::div[.//button[normalize-space(.)='Dispute']][1]");
  await expect(claimCard.getByText("Needs Reviewer", { exact: true })).toBeVisible();
  await expect(claimCard.getByRole("button", { name: "Accept Fix" })).toHaveCount(0);

  await page.getByRole("button", { name: "Accept Fix" }).first().click();
  await expect(page.getByText("Version 2", { exact: true })).toBeVisible({ timeout: 90_000 });

  await page.getByRole("button", { name: "Request Manager Review" }).click();
  await expect(page.getByText("in_review", { exact: true })).toBeVisible({ timeout: 20_000 });
});

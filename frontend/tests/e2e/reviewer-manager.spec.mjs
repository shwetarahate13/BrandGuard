import { test, expect } from "@playwright/test";

test("reviewer signs off an escalated demo submission before manager approval", async ({ page, browser }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Fill / Sign in as Reviewer" }).click();
  await expect(page.getByRole("heading", { name: "Reviewer workbench" })).toBeVisible({ timeout: 15_000 });
  const reviewerTips = page.getByRole("dialog");
  if (await reviewerTips.isVisible()) await reviewerTips.getByRole("button", { name: "Got it" }).click();

  const escalatedCard = page.getByText(/This energy figure is expired/)
    .locator("xpath=ancestor::div[contains(@class,'p-5')][1]");
  await escalatedCard.getByRole("button", { name: "Provide Compliance Verdict" }).click();
  await page.locator("#reviewer-escalation-justification").fill(
    "The current approved fact shows a different energy figure; confirm the claim needs correction.",
  );
  await escalatedCard.getByRole("button", { name: "Confirm Finding" }).click();

  const assignedRow = page.getByText("DEMO · Spring Sustainability Newsletter", { exact: true })
    .locator("xpath=ancestor::div[contains(@class,'py-4')][1]");
  await assignedRow.getByRole("button", { name: "Sign Off High-Risk Copy" }).click();
  const approvalPath = new URL(page.url()).pathname;
  expect(approvalPath).toMatch(/^\/approval\//);
  await expect(page.getByText("Reviewer sign-off checklist")).toBeVisible();
  for (const label of ["Claims verified", "Facts are current", "Accessibility reviewed", "Legal wording reviewed"]) {
    await page.getByRole("checkbox", { name: label }).check();
  }
  await page.locator("#review-evidence-notes").fill("Compared the campaign statistic with the current approved energy audit.");
  await page.locator("#review-signoff-justification").fill("The claim has been reviewed against the current source and checklist.");
  await page.getByRole("button", { name: "Record reviewer sign-off" }).click();
  await expect(page.getByText("Reviewer sign-off recorded", { exact: true })).toBeVisible();

  const managerContext = await browser.newContext();
  const managerPage = await managerContext.newPage();
  await managerPage.goto("/");
  await managerPage.getByRole("button", { name: "Fill / Sign in as Manager" }).click();
  await expect(managerPage.getByRole("link", { name: "Sign in", exact: true })).toBeHidden({ timeout: 15_000 });
  const managerTips = managerPage.getByRole("dialog");
  if (await managerTips.isVisible()) await managerTips.getByRole("button", { name: "Got it" }).click();
  await managerPage.goto(approvalPath);
  await expect(managerPage.getByRole("button", { name: "Final Manager Approval" })).toBeVisible();
  await managerPage.getByRole("button", { name: "Final Manager Approval" }).click();
  await managerPage.getByLabel("Decision note").fill("Reviewer sign-off reviewed; final manager approval recorded.");
  await managerPage.getByRole("button", { name: "Confirm decision" }).click();
  await expect(managerPage.getByText("approved", { exact: true }).first()).toBeVisible();
  await managerContext.close();
});

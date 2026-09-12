import { test, expect } from "@playwright/test";

test("patient journey: language → consent → chest pain intake → summary", async ({ page }) => {
  await page.goto("http://localhost:3000");

  // Language picker
  await page.getByText("Hindi").click();

  // Consent (auto-granted in UI for demo)
  await page.getByText("Main agree").click();

  // New Visit
  await page.getByText("New Visit").click();

  // Chief complaint picker
  await page.getByText("Chest Pain").click();

  // Walk through 6 touch answers (onset, location, character, radiation, associated, severity)
  for (let i = 0; i < 6; i++) {
    await page.locator('[data-test="touch-option-0"]').click();
    // Confirm for multi_choice
    if (i === 4) {  // associated is multi_choice
      await page.locator('[data-test="option-confirm"]').click();
    }
  }

  // Summary screen
  await expect(page.getByText("Your summary is ready")).toBeVisible();
});

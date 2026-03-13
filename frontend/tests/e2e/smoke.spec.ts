import { test, expect } from "@playwright/test";

test.describe("Smoke tests — app loads in both locales", () => {
  test("EN locale loads with DeckForge header and LTR direction", async ({ page }) => {
    await page.goto("/en");

    // Header renders with brand name
    await expect(page.locator("header")).toContainText("DeckForge");

    // Page direction is LTR
    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("ltr");

    // Dashboard title visible
    await expect(page.locator("h1")).toContainText("Dashboard");

    // Locale switcher shows Arabic option
    await expect(page.locator("header a")).toContainText("العربية");
  });

  test("AR locale loads with DeckForge header and RTL direction", async ({ page }) => {
    await page.goto("/ar");

    // Header renders with brand name
    await expect(page.locator("header")).toContainText("DeckForge");

    // Page direction is RTL
    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");

    // Dashboard title visible in Arabic
    await expect(page.locator("h1")).toContainText("لوحة التحكم");

    // Locale switcher shows English option
    await expect(page.locator("header a")).toContainText("English");
  });

  test("locale switcher navigates from EN to AR", async ({ page }) => {
    await page.goto("/en");

    // Click the Arabic switcher link
    await page.locator("header a").click();

    // Should be on AR page with RTL
    await expect(page).toHaveURL(/\/ar/);
    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");
  });

  test("root URL redirects to /en", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/en/);
  });
});

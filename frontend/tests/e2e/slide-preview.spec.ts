/**
 * E2E: Slide preview — thumbnail grid in both modes, detail modal.
 *
 * All API calls mocked via Playwright route interception. Zero real backend calls.
 */

import { test, expect } from "@playwright/test";

// ── Mock Data ────────────────────────────────────────────────────────

const SESSION_ID = "e2e-slides-001";

const MOCK_SLIDES = [
  { slide_number: 1, entry_type: "A1 Clone", asset_id: "intro_001", semantic_layout_id: "title_slide", section_id: "Introduction", thumbnail_url: null, shape_count: 5, fonts: ["Calibri"], text_preview: "Welcome to the proposal" },
  { slide_number: 2, entry_type: "B Variable", asset_id: "content_001", semantic_layout_id: "two_column", section_id: "Section 01", thumbnail_url: null, shape_count: 8, fonts: ["Calibri", "Arial"], text_preview: "Market analysis overview" },
  { slide_number: 3, entry_type: "A2 Shell", asset_id: "chart_001", semantic_layout_id: "chart_full", section_id: "Section 02", thumbnail_url: null, shape_count: 3, fonts: ["Calibri"], text_preview: "Financial projections" },
];

async function mockSlidesAPI(
  page: import("@playwright/test").Page,
  mode: "metadata_only" | "rendered" = "metadata_only",
) {
  await page.route(`**/api/pipeline/${SESSION_ID}/slides`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        slides: MOCK_SLIDES,
        thumbnail_mode: mode,
      }),
    }),
  );
}

async function mockSlidesNotReady(page: import("@playwright/test").Page) {
  await page.route(`**/api/pipeline/${SESSION_ID}/slides`, (route) =>
    route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        detail: { error: { code: "PIPELINE_NOT_COMPLETE", message: "Pipeline not complete" } },
      }),
    }),
  );
}

// ── Tests ────────────────────────────────────────────────────────────

test.describe("Slide Preview — EN (metadata_only)", () => {
  test("renders slide grid with metadata cards", async ({ page }) => {
    await mockSlidesAPI(page, "metadata_only");
    await page.goto(`/en/pipeline/${SESSION_ID}/slides`);

    await expect(page.getByText("Slide Browser")).toBeVisible();
    await expect(page.getByText("3 slides")).toBeVisible();
    await expect(page.getByText("Metadata View")).toBeVisible();
  });

  test("shows slide entry type badges", async ({ page }) => {
    await mockSlidesAPI(page, "metadata_only");
    await page.goto(`/en/pipeline/${SESSION_ID}/slides`);

    await expect(page.getByText("A1 Clone")).toBeVisible();
    await expect(page.getByText("B Variable")).toBeVisible();
    await expect(page.getByText("A2 Shell")).toBeVisible();
  });

  test("shows section and layout info", async ({ page }) => {
    await mockSlidesAPI(page, "metadata_only");
    await page.goto(`/en/pipeline/${SESSION_ID}/slides`);

    await expect(page.getByText("Introduction")).toBeVisible();
  });

  test("shows back to pipeline link", async ({ page }) => {
    await mockSlidesAPI(page, "metadata_only");
    await page.goto(`/en/pipeline/${SESSION_ID}/slides`);

    await expect(page.getByText("Back to Pipeline")).toBeVisible();
  });
});

test.describe("Slide Preview — EN (rendered)", () => {
  test("renders slide grid with image thumbnails", async ({ page }) => {
    await mockSlidesAPI(page, "rendered");

    // Mock thumbnail images
    await page.route(`**/api/pipeline/${SESSION_ID}/slides/*/thumbnail.png`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "image/png",
        body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "base64"),
      }),
    );

    await page.goto(`/en/pipeline/${SESSION_ID}/slides`);

    await expect(page.getByText("3 slides")).toBeVisible();
    await expect(page.getByText("Image Thumbnails")).toBeVisible();
  });
});

test.describe("Slide Preview — Not Ready", () => {
  test("shows not-complete message on 409", async ({ page }) => {
    await mockSlidesNotReady(page);
    await page.goto(`/en/pipeline/${SESSION_ID}/slides`);

    await expect(page.getByText(/not completed|not complete/i)).toBeVisible();
  });
});

test.describe("Slide Preview — AR", () => {
  test("renders slide browser in Arabic with RTL", async ({ page }) => {
    await mockSlidesAPI(page, "metadata_only");
    await page.goto(`/ar/pipeline/${SESSION_ID}/slides`);

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");

    await expect(page.getByText("متصفح الشرائح")).toBeVisible();
  });
});

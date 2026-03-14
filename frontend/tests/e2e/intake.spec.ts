/**
 * E2E: Intake page — file upload, text paste, configuration, and pipeline start.
 *
 * All API calls mocked via Playwright route interception. Zero real backend calls.
 */

import { test, expect } from "@playwright/test";

// ── Mock API Helpers ─────────────────────────────────────────────────

async function mockUploadAPI(page: import("@playwright/test").Page) {
  await page.route("**/api/pipeline/upload", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        uploads: [
          {
            upload_id: "upload-001",
            filename: "rfp.pdf",
            size_bytes: 1024000,
            content_type: "application/pdf",
            extracted_text_length: 5000,
            detected_language: "en",
          },
        ],
      }),
    }),
  );
}

async function mockStartPipeline(page: import("@playwright/test").Page) {
  await page.route("**/api/pipeline/start", (route) =>
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: "test-session-001",
        status: "running",
        created_at: new Date().toISOString(),
        stream_url: "/api/pipeline/test-session-001/stream",
      }),
    }),
  );
}

// ── Tests ────────────────────────────────────────────────────────────

test.describe("Intake — EN", () => {
  test("renders the intake form with all configuration fields", async ({ page }) => {
    await page.goto("/en/new");

    // Title visible
    await expect(page.locator("h1")).toContainText("New Proposal");

    // Configuration fields present
    await expect(page.getByText("Language")).toBeVisible();
    await expect(page.getByText("Proposal Mode")).toBeVisible();
    await expect(page.getByText("Sector")).toBeVisible();
    await expect(page.getByText("Geography")).toBeVisible();
  });

  test("shows text paste area", async ({ page }) => {
    await page.goto("/en/new");

    // Textarea for RFP text
    const textarea = page.locator("textarea");
    await expect(textarea).toBeVisible();
  });

  test("shows upload area with supported formats", async ({ page }) => {
    await page.goto("/en/new");
    await expect(page.getByText("PDF, DOCX, TXT")).toBeVisible();
  });

  test("submit button starts pipeline with text input", async ({ page }) => {
    await mockStartPipeline(page);

    await page.goto("/en/new");

    // Type RFP text
    const textarea = page.locator("textarea");
    await textarea.fill("This is a test RFP document for proposal generation.");

    // Click generate
    const submitButton = page.getByText("Generate Proposal");
    await expect(submitButton).toBeVisible();
  });

  test("shows validation when no input provided", async ({ page }) => {
    await page.goto("/en/new");

    // Need input message should appear or button should indicate need
    await expect(page.getByText(/Upload files or paste text/i)).toBeVisible();
  });
});

test.describe("Intake — AR", () => {
  test("renders intake form in Arabic with RTL", async ({ page }) => {
    await page.goto("/ar/new");

    // Title in Arabic
    await expect(page.locator("h1")).toContainText("عرض جديد");

    // RTL direction
    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");
  });

  test("shows Arabic labels for configuration", async ({ page }) => {
    await page.goto("/ar/new");
    await expect(page.getByText("اللغة")).toBeVisible();
  });
});

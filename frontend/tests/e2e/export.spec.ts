/**
 * E2E: Export — download buttons, not-ready state, session summary.
 *
 * All API calls mocked via Playwright route interception. Zero real backend calls.
 */

import { test, expect } from "@playwright/test";

// ── Mock Data ────────────────────────────────────────────────────────

const SESSION_ID = "e2e-export-001";

async function mockExportStatus(
  page: import("@playwright/test").Page,
  status: "complete" | "running" = "complete",
) {
  await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: SESSION_ID,
        status,
        current_stage: status === "complete" ? "finalized" : "context_analysis",
        current_gate: null,
        completed_gates: status === "complete"
          ? [1, 2, 3, 4, 5].map((n) => ({
              gate_number: n,
              approved: true,
              feedback: "",
              decided_at: new Date().toISOString(),
            }))
          : [],
        started_at: "2024-01-01T10:00:00Z",
        elapsed_ms: 300000,
        error: null,
        outputs: status === "complete"
          ? { pptx_ready: true, docx_ready: true, slide_count: 24 }
          : null,
        session_metadata: {
          total_llm_calls: 42,
          total_input_tokens: 125000,
          total_output_tokens: 45000,
          total_cost_usd: 3.75,
        },
      }),
    }),
  );
}

async function mockDownload(page: import("@playwright/test").Page) {
  await page.route(`**/api/pipeline/${SESSION_ID}/export/*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/octet-stream",
      headers: { "Content-Disposition": 'attachment; filename="proposal.pptx"' },
      body: Buffer.from("PK\x03\x04mock"),
    }),
  );
}

// ── Tests ────────────────────────────────────────────────────────────

test.describe("Export — EN (Complete)", () => {
  test("shows export page with title and session info", async ({ page }) => {
    await mockExportStatus(page, "complete");
    await page.goto(`/en/pipeline/${SESSION_ID}/export`);

    await expect(page.getByText("Export Deliverables")).toBeVisible();
  });

  test("shows download buttons when pipeline is complete", async ({ page }) => {
    await mockExportStatus(page, "complete");
    await page.goto(`/en/pipeline/${SESSION_ID}/export`);

    await expect(page.getByText(/Download Presentation/i)).toBeVisible();
    await expect(page.getByText(/Download Research Report/i)).toBeVisible();
  });

  test("shows slide count", async ({ page }) => {
    await mockExportStatus(page, "complete");
    await page.goto(`/en/pipeline/${SESSION_ID}/export`);

    await expect(page.getByText("24 slides generated")).toBeVisible();
  });

  test("shows session summary with metadata", async ({ page }) => {
    await mockExportStatus(page, "complete");
    await page.goto(`/en/pipeline/${SESSION_ID}/export`);

    await expect(page.getByText("Session Summary")).toBeVisible();
    await expect(page.getByText("42")).toBeVisible(); // LLM calls
    await expect(page.getByText("$3.75")).toBeVisible(); // Cost
    await expect(page.getByText("5/5")).toBeVisible(); // Gates
  });

  test("shows format badges", async ({ page }) => {
    await mockExportStatus(page, "complete");
    await page.goto(`/en/pipeline/${SESSION_ID}/export`);

    await expect(page.getByText("PowerPoint (.pptx)")).toBeVisible();
    await expect(page.getByText("Word Document (.docx)")).toBeVisible();
  });

  test("shows navigation links", async ({ page }) => {
    await mockExportStatus(page, "complete");
    await page.goto(`/en/pipeline/${SESSION_ID}/export`);

    await expect(page.getByText("View Slides")).toBeVisible();
    await expect(page.getByText("Back to Pipeline")).toBeVisible();
  });
});

test.describe("Export — EN (Not Ready)", () => {
  test("shows not-ready message when pipeline is running", async ({ page }) => {
    await mockExportStatus(page, "running");
    await page.goto(`/en/pipeline/${SESSION_ID}/export`);

    await expect(page.getByText(/available after the pipeline completes/i)).toBeVisible();
  });
});

test.describe("Export — AR", () => {
  test("shows export page in Arabic with RTL", async ({ page }) => {
    await mockExportStatus(page, "complete");
    await page.goto(`/ar/pipeline/${SESSION_ID}/export`);

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");

    await expect(page.getByText("تصدير المخرجات")).toBeVisible();
  });
});

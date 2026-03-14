/**
 * E2E: RTL — Full Arabic journey verifying layout direction across all views.
 *
 * All API calls mocked via Playwright route interception. Zero real backend calls.
 */

import { test, expect } from "@playwright/test";

const SESSION_ID = "e2e-rtl-001";

async function mockAllAPIs(page: import("@playwright/test").Page) {
  // Pipeline status (complete)
  await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: SESSION_ID,
        status: "complete",
        current_stage: "finalized",
        current_gate: null,
        completed_gates: [1, 2, 3, 4, 5].map((n) => ({
          gate_number: n, approved: true, feedback: "", decided_at: new Date().toISOString(),
        })),
        started_at: new Date().toISOString(),
        elapsed_ms: 180000,
        error: null,
        outputs: { pptx_ready: true, docx_ready: true, slide_count: 12 },
        session_metadata: { total_llm_calls: 20, total_input_tokens: 50000, total_output_tokens: 15000, total_cost_usd: 1.5 },
      }),
    }),
  );

  // SSE stream
  await page.route(`**/api/pipeline/${SESSION_ID}/stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: `data: ${JSON.stringify({ type: "heartbeat", timestamp: new Date().toISOString() })}\n\n`,
    }),
  );

  // Slides
  await page.route(`**/api/pipeline/${SESSION_ID}/slides`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        slides: [
          { slide_number: 1, entry_type: "A1 Clone", asset_id: "intro", semantic_layout_id: "title", section_id: "مقدمة", thumbnail_url: null, shape_count: 4, fonts: ["Calibri"], text_preview: "مرحبا بالعرض" },
        ],
        thumbnail_mode: "metadata_only",
      }),
    }),
  );

  // Pipeline start
  await page.route("**/api/pipeline/start", (route) =>
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: SESSION_ID,
        status: "running",
        created_at: new Date().toISOString(),
        stream_url: `/api/pipeline/${SESSION_ID}/stream`,
      }),
    }),
  );
}

// ── Tests ────────────────────────────────────────────────────────────

test.describe("RTL — Full Arabic Journey", () => {
  test("dashboard renders in RTL with Arabic content", async ({ page }) => {
    await page.goto("/ar");

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");

    await expect(page.locator("h1")).toContainText("لوحة التحكم");
    await expect(page.locator("header")).toContainText("DeckForge");
  });

  test("intake form renders in RTL", async ({ page }) => {
    await page.goto("/ar/new");

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");

    await expect(page.locator("h1")).toContainText("عرض جديد");
  });

  test("pipeline page renders in RTL", async ({ page }) => {
    await mockAllAPIs(page);
    await page.goto(`/ar/pipeline/${SESSION_ID}`);

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");
  });

  test("slides page renders in RTL with Arabic content", async ({ page }) => {
    await mockAllAPIs(page);
    await page.goto(`/ar/pipeline/${SESSION_ID}/slides`);

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");

    await expect(page.getByText("متصفح الشرائح")).toBeVisible();
  });

  test("export page renders in RTL with Arabic content", async ({ page }) => {
    await mockAllAPIs(page);
    await page.goto(`/ar/pipeline/${SESSION_ID}/export`);

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");

    await expect(page.getByText("تصدير المخرجات")).toBeVisible();
  });

  test("sidebar navigation renders in RTL", async ({ page }) => {
    await page.goto("/ar");

    // Sidebar should contain Arabic nav items
    await expect(page.locator("nav")).toContainText("لوحة التحكم");
    await expect(page.locator("nav")).toContainText("عرض جديد");
  });
});

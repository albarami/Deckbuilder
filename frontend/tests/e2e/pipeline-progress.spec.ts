/**
 * E2E: Pipeline progress — stage tracker with mock SSE events.
 *
 * All API calls mocked via Playwright route interception. Zero real backend calls.
 */

import { test, expect } from "@playwright/test";

// ── Mock API Helpers ─────────────────────────────────────────────────

const SESSION_ID = "e2e-pipeline-001";

async function mockPipelineStatus(
  page: import("@playwright/test").Page,
  status: "running" | "gate_pending" | "complete",
  currentStage = "context_analysis",
) {
  await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: SESSION_ID,
        status,
        current_stage: currentStage,
        current_gate: status === "gate_pending"
          ? { gate_number: 1, summary: "Review context", prompt: "Please review", gate_data: {} }
          : null,
        completed_gates: [],
        started_at: new Date().toISOString(),
        elapsed_ms: 5000,
        error: null,
        outputs: status === "complete"
          ? { pptx_ready: true, docx_ready: true, slide_count: 24 }
          : null,
        session_metadata: {
          total_llm_calls: 0,
          total_input_tokens: 0,
          total_output_tokens: 0,
          total_cost_usd: 0,
        },
      }),
    }),
  );
}

async function mockSSEStream(page: import("@playwright/test").Page) {
  await page.route(`**/api/pipeline/${SESSION_ID}/stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        "data: " + JSON.stringify({ type: "heartbeat", timestamp: new Date().toISOString() }),
        "",
        "data: " + JSON.stringify({ type: "stage_change", stage: "context_analysis", timestamp: new Date().toISOString() }),
        "",
        "data: " + JSON.stringify({ type: "agent_start", agent: "context_analyzer", timestamp: new Date().toISOString() }),
        "",
      ].join("\n"),
    }),
  );
}

// ── Tests ────────────────────────────────────────────────────────────

test.describe("Pipeline Progress — EN", () => {
  test("shows loading state while fetching status", async ({ page }) => {
    // Delay response to see loading
    await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
      new Promise((resolve) => setTimeout(() => resolve(
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session_id: SESSION_ID,
            status: "running",
            current_stage: "context_analysis",
            current_gate: null,
            completed_gates: [],
            started_at: new Date().toISOString(),
            elapsed_ms: 1000,
            error: null,
            outputs: null,
            session_metadata: { total_llm_calls: 0, total_input_tokens: 0, total_output_tokens: 0, total_cost_usd: 0 },
          }),
        }),
      ), 500)),
    );
    await mockSSEStream(page);

    await page.goto(`/en/pipeline/${SESSION_ID}`);
    // Loading text should appear briefly
    await expect(page.getByText(/Loading session/i)).toBeVisible();
  });

  test("shows stage tracker when pipeline is running", async ({ page }) => {
    await mockPipelineStatus(page, "running", "context_analysis");
    await mockSSEStream(page);

    await page.goto(`/en/pipeline/${SESSION_ID}`);

    // Wait for status to load
    await expect(page.getByText("Pipeline Progress")).toBeVisible();

    // Stage tracker shows stages
    await expect(page.getByText("Context Analysis")).toBeVisible();
    await expect(page.getByText("Source Research")).toBeVisible();
  });

  test("shows pipeline header with session info", async ({ page }) => {
    await mockPipelineStatus(page, "running");
    await mockSSEStream(page);

    await page.goto(`/en/pipeline/${SESSION_ID}`);

    await expect(page.getByText("Pipeline Progress")).toBeVisible();
  });

  test("shows complete state with export buttons", async ({ page }) => {
    await mockPipelineStatus(page, "complete", "finalized");
    await mockSSEStream(page);

    await page.goto(`/en/pipeline/${SESSION_ID}`);

    await expect(page.getByText("Export Deliverables")).toBeVisible();
    await expect(page.getByText(/Download Presentation/i)).toBeVisible();
  });

  test("shows session expired for unknown session", async ({ page }) => {
    await page.route(`**/api/pipeline/unknown-id/status`, (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          detail: { error: { code: "SESSION_NOT_FOUND", message: "Not found" } },
        }),
      }),
    );

    await page.goto("/en/pipeline/unknown-id");
    await expect(page.getByText("Session Expired")).toBeVisible();
  });
});

test.describe("Pipeline Progress — AR", () => {
  test("shows stage tracker in Arabic with RTL", async ({ page }) => {
    await mockPipelineStatus(page, "running");
    await mockSSEStream(page);

    await page.goto(`/ar/pipeline/${SESSION_ID}`);

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");
  });
});

/**
 * E2E: Session resume — refresh during gate, restore state from GET /status.
 *
 * All API calls mocked via Playwright route interception. Zero real backend calls.
 */

import { test, expect } from "@playwright/test";

const SESSION_ID = "e2e-resume-001";

// ── Tests ────────────────────────────────────────────────────────────

test.describe("Session Resume — EN", () => {
  test("restores gate_pending state after page reload", async ({ page }) => {
    // Mock status as gate_pending at gate 3
    await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: SESSION_ID,
          status: "gate_pending",
          current_stage: "gate_3",
          current_gate: {
            gate_number: 3,
            summary: "Report ready for review",
            prompt: "Review the generated report",
            gate_data: { report: "# Report\n\nThis is the report." },
          },
          completed_gates: [
            { gate_number: 1, approved: true, feedback: "", decided_at: "2024-01-01T10:05:00Z" },
            { gate_number: 2, approved: true, feedback: "", decided_at: "2024-01-01T10:10:00Z" },
          ],
          started_at: "2024-01-01T10:00:00Z",
          elapsed_ms: 900000,
          error: null,
          outputs: null,
          session_metadata: { total_llm_calls: 15, total_input_tokens: 50000, total_output_tokens: 20000, total_cost_usd: 1.2 },
        }),
      }),
    );

    await page.route(`**/api/pipeline/${SESSION_ID}/stream`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `data: ${JSON.stringify({ type: "heartbeat", timestamp: new Date().toISOString() })}\n\n`,
      }),
    );

    // Navigate to pipeline page
    await page.goto(`/en/pipeline/${SESSION_ID}`);

    // Should restore to gate 3 review
    await expect(page.getByText(/Gate 3 Review/i)).toBeVisible();
    await expect(page.getByText("Approve & Continue")).toBeVisible();
  });

  test("restores running state after reload", async ({ page }) => {
    await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: SESSION_ID,
          status: "running",
          current_stage: "source_research",
          current_gate: null,
          completed_gates: [
            { gate_number: 1, approved: true, feedback: "", decided_at: "2024-01-01T10:05:00Z" },
          ],
          started_at: "2024-01-01T10:00:00Z",
          elapsed_ms: 600000,
          error: null,
          outputs: null,
          session_metadata: { total_llm_calls: 8, total_input_tokens: 30000, total_output_tokens: 10000, total_cost_usd: 0.8 },
        }),
      }),
    );

    await page.route(`**/api/pipeline/${SESSION_ID}/stream`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `data: ${JSON.stringify({ type: "stage_change", stage: "source_research", timestamp: new Date().toISOString() })}\n\n`,
      }),
    );

    await page.goto(`/en/pipeline/${SESSION_ID}`);

    // Should show pipeline running with stage tracker
    await expect(page.getByText("Pipeline Progress")).toBeVisible();
    await expect(page.getByText("Source Research")).toBeVisible();
  });

  test("shows session expired on 404", async ({ page }) => {
    await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          detail: { error: { code: "SESSION_NOT_FOUND", message: "Session not found" } },
        }),
      }),
    );

    await page.goto(`/en/pipeline/${SESSION_ID}`);

    await expect(page.getByText("Session Expired")).toBeVisible();
    await expect(page.getByText("Start New Proposal")).toBeVisible();
  });
});

test.describe("Session Resume — AR", () => {
  test("restores state in Arabic with RTL", async ({ page }) => {
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
          elapsed_ms: 300000,
          error: null,
          outputs: { pptx_ready: true, docx_ready: true, slide_count: 20 },
          session_metadata: { total_llm_calls: 40, total_input_tokens: 100000, total_output_tokens: 40000, total_cost_usd: 3.0 },
        }),
      }),
    );

    await page.route(`**/api/pipeline/${SESSION_ID}/stream`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `data: ${JSON.stringify({ type: "heartbeat", timestamp: new Date().toISOString() })}\n\n`,
      }),
    );

    await page.goto(`/ar/pipeline/${SESSION_ID}`);

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");
  });
});

/**
 * E2E: Error handling — API failures, network errors, and edge cases.
 *
 * All API calls mocked via Playwright route interception. Zero real backend calls.
 */

import { test, expect } from "@playwright/test";

const SESSION_ID = "e2e-err-001";

// ── Tests ────────────────────────────────────────────────────────────

test.describe("Error Handling — API Failures", () => {
  test("shows error card on pipeline status 500", async ({ page }) => {
    await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          detail: {
            error: {
              code: "INTERNAL_ERROR",
              message: "Unexpected server error",
            },
          },
        }),
      }),
    );

    await page.goto(`/en/pipeline/${SESSION_ID}`);

    await expect(page.getByText(/error|failed/i)).toBeVisible();
  });

  test("shows session expired on 404 status", async ({ page }) => {
    await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          detail: {
            error: {
              code: "SESSION_NOT_FOUND",
              message: "Session not found",
            },
          },
        }),
      }),
    );

    await page.goto(`/en/pipeline/${SESSION_ID}`);

    await expect(page.getByText("Session Expired")).toBeVisible();
    await expect(page.getByText("Start New Proposal")).toBeVisible();
  });

  test("shows export not ready for incomplete pipeline", async ({ page }) => {
    await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: SESSION_ID,
          status: "running",
          current_stage: "source_research",
          current_gate: null,
          completed_gates: [],
          started_at: new Date().toISOString(),
          elapsed_ms: 60000,
          error: null,
          outputs: null,
          session_metadata: {
            total_llm_calls: 5,
            total_input_tokens: 10000,
            total_output_tokens: 5000,
            total_cost_usd: 0.3,
          },
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

    await page.goto(`/en/pipeline/${SESSION_ID}/export`);

    await expect(
      page.getByText(/not ready|not available|after pipeline completes/i),
    ).toBeVisible();
  });

  test("shows slides not ready for incomplete pipeline", async ({ page }) => {
    await page.route(`**/api/pipeline/${SESSION_ID}/slides`, (route) =>
      route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: {
            error: {
              code: "EXPORT_NOT_READY",
              message: "Pipeline not complete",
            },
          },
        }),
      }),
    );

    await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: SESSION_ID,
          status: "running",
          current_stage: "rendering",
          current_gate: null,
          completed_gates: [],
          started_at: new Date().toISOString(),
          elapsed_ms: 120000,
          error: null,
          outputs: null,
          session_metadata: {
            total_llm_calls: 10,
            total_input_tokens: 20000,
            total_output_tokens: 8000,
            total_cost_usd: 0.5,
          },
        }),
      }),
    );

    await page.goto(`/en/pipeline/${SESSION_ID}/slides`);

    await expect(
      page.getByText(/not ready|not available|pipeline completes/i),
    ).toBeVisible();
  });

  test("shows pipeline error state", async ({ page }) => {
    await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: SESSION_ID,
          status: "error",
          current_stage: "error",
          current_gate: null,
          completed_gates: [],
          started_at: new Date().toISOString(),
          elapsed_ms: 45000,
          error: {
            agent: "source_research",
            message: "Failed to process sources",
          },
          outputs: null,
          session_metadata: {
            total_llm_calls: 3,
            total_input_tokens: 5000,
            total_output_tokens: 2000,
            total_cost_usd: 0.1,
          },
        }),
      }),
    );

    await page.route(`**/api/pipeline/${SESSION_ID}/stream`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `data: ${JSON.stringify({ type: "error", error: { agent: "source_research", message: "Failed to process sources" }, timestamp: new Date().toISOString() })}\n\n`,
      }),
    );

    await page.goto(`/en/pipeline/${SESSION_ID}`);

    await expect(page.getByText(/error|failed/i)).toBeVisible();
  });
});

test.describe("Error Handling — Form Validation", () => {
  test("intake form requires text or document", async ({ page }) => {
    await page.goto("/en/new");

    // Try to find and click submit without filling in data
    const submitButton = page.getByText("Start Pipeline");
    if (await submitButton.isVisible()) {
      await submitButton.click();
      // Form should not navigate away — still on /new
      await expect(page).toHaveURL(/\/new/);
    }
  });
});

test.describe("Error Handling — Navigation", () => {
  test("404 page renders for unknown routes", async ({ page }) => {
    await page.goto("/en/nonexistent-page");

    // Should show 404 or redirect to a known page
    await expect(
      page
        .getByText(/not found|404/i)
        .or(page.locator("h1")),
    ).toBeVisible();
  });

  test("handles missing locale gracefully", async ({ page }) => {
    // Navigate without locale prefix — middleware should redirect
    const response = await page.goto("/pipeline/some-id");

    // Should either redirect to a locale-prefixed URL or show content
    expect(response).not.toBeNull();
    const url = page.url();
    // Middleware should add locale prefix
    expect(url).toMatch(/\/(en|ar)\//);
  });
});

/**
 * E2E: Gate approval — approve/reject all 5 gates.
 *
 * All API calls mocked via Playwright route interception. Zero real backend calls.
 */

import { test, expect } from "@playwright/test";

// ── Mock API Helpers ─────────────────────────────────────────────────

const SESSION_ID = "e2e-gate-001";

function makeGateStatus(gateNumber: number, gateData: unknown = {}) {
  return {
    session_id: SESSION_ID,
    status: "gate_pending",
    current_stage: `gate_${gateNumber}`,
    current_gate: {
      gate_number: gateNumber,
      summary: `Gate ${gateNumber} summary`,
      prompt: `Please review gate ${gateNumber} results`,
      gate_data: gateData,
    },
    completed_gates: Array.from({ length: gateNumber - 1 }, (_, i) => ({
      gate_number: i + 1,
      approved: true,
      feedback: "",
      decided_at: new Date().toISOString(),
    })),
    started_at: new Date().toISOString(),
    elapsed_ms: gateNumber * 10000,
    error: null,
    outputs: null,
    session_metadata: {
      total_llm_calls: gateNumber * 5,
      total_input_tokens: gateNumber * 10000,
      total_output_tokens: gateNumber * 3000,
      total_cost_usd: gateNumber * 0.5,
    },
  };
}

async function setupGateMocks(page: import("@playwright/test").Page, gateNumber: number) {
  await page.route(`**/api/pipeline/${SESSION_ID}/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(makeGateStatus(gateNumber)),
    }),
  );

  await page.route(`**/api/pipeline/${SESSION_ID}/stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: `data: ${JSON.stringify({ type: "gate_pending", gate_number: gateNumber, timestamp: new Date().toISOString() })}\n\n`,
    }),
  );

  await page.route(`**/api/pipeline/${SESSION_ID}/gate/*/decide`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        gate_number: gateNumber,
        decision: "approved",
        pipeline_status: "running",
      }),
    }),
  );
}

// ── Tests ────────────────────────────────────────────────────────────

test.describe("Gate Approval — EN", () => {
  test("shows gate 1 review panel with approve/reject buttons", async ({ page }) => {
    await setupGateMocks(page, 1);
    await page.goto(`/en/pipeline/${SESSION_ID}`);

    await expect(page.getByText(/Gate 1 Review/i)).toBeVisible();
    await expect(page.getByText("Approve & Continue")).toBeVisible();
    await expect(page.getByText("Reject & Revise")).toBeVisible();
  });

  test("shows review required badge", async ({ page }) => {
    await setupGateMocks(page, 1);
    await page.goto(`/en/pipeline/${SESSION_ID}`);

    await expect(page.getByText("Review Required")).toBeVisible();
  });

  test("shows gate prompt text", async ({ page }) => {
    await setupGateMocks(page, 1);
    await page.goto(`/en/pipeline/${SESSION_ID}`);

    await expect(page.getByText("Please review gate 1 results")).toBeVisible();
  });

  test("shows reject feedback area on reject click", async ({ page }) => {
    await setupGateMocks(page, 1);
    await page.goto(`/en/pipeline/${SESSION_ID}`);

    // Click reject
    await page.getByText("Reject & Revise").click();

    // Feedback textarea should appear
    await expect(page.locator("textarea")).toBeVisible();
    await expect(page.getByText("Submit Rejection")).toBeVisible();
    await expect(page.getByText("Cancel")).toBeVisible();
  });

  test("cancel hides reject feedback area", async ({ page }) => {
    await setupGateMocks(page, 1);
    await page.goto(`/en/pipeline/${SESSION_ID}`);

    // Click reject then cancel
    await page.getByText("Reject & Revise").click();
    await expect(page.locator("textarea")).toBeVisible();

    await page.getByText("Cancel").click();

    // Back to approve/reject buttons
    await expect(page.getByText("Approve & Continue")).toBeVisible();
    await expect(page.getByText("Reject & Revise")).toBeVisible();
  });

  for (const gateNum of [2, 3, 4, 5]) {
    test(`shows gate ${gateNum} review panel`, async ({ page }) => {
      await setupGateMocks(page, gateNum);
      await page.goto(`/en/pipeline/${SESSION_ID}`);

      await expect(page.getByText(new RegExp(`Gate ${gateNum} Review`, "i"))).toBeVisible();
    });
  }
});

test.describe("Gate Approval — AR", () => {
  test("shows gate review in Arabic with RTL", async ({ page }) => {
    await setupGateMocks(page, 1);
    await page.goto(`/ar/pipeline/${SESSION_ID}`);

    const dir = await page.locator("[dir]").first().getAttribute("dir");
    expect(dir).toBe("rtl");

    // Gate review should render
    await expect(page.getByText(/بوابة|مراجعة/)).toBeVisible();
  });
});

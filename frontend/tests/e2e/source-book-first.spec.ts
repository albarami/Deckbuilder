import { expect, test } from "@playwright/test";

test.describe("Source-Book-first real-route smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      class MockEventSource {
        onopen: ((event: Event) => void) | null = null;
        onmessage: ((event: MessageEvent) => void) | null = null;
        onerror: ((event: Event) => void) | null = null;
        constructor(_url: string) {}
        close() {}
      }
      // @ts-expect-error test shim
      window.EventSource = MockEventSource;
    });

    await page.route("http://localhost:8000/api/**", async (route) => {
      const url = route.request().url();
      const method = route.request().method();

      if (url.endsWith("/api/pipeline/sessions")) {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ sessions: [] }) });
      }
      if (url.endsWith("/api/upload") && method === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            uploads: [
              {
                upload_id: "upload-1",
                filename: "RFP.pdf",
                size_bytes: 1024,
                content_type: "application/pdf",
                extracted_text_length: 2400,
                detected_language: "en",
              },
            ],
          }),
        });
      }
      if (url.endsWith("/api/pipeline/start") && method === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session_id: "session-e2e",
            status: "running",
            created_at: "2026-03-25T10:00:00Z",
            stream_url: "/api/pipeline/session-e2e/stream",
            pipeline_url: "/pipeline/session-e2e",
          }),
        });
      }
      if (/\/api\/pipeline\/[^/]+\/status$/.test(url)) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session_id: "session-e2e",
            status: "gate_pending",
            current_stage: "source_book_generation",
            current_stage_label: "Source Book",
            current_step_number: 3,
            current_gate_number: 3,
            current_gate: {
              gate_number: 3,
              agent_name: "reviewer",
              summary: "Source Book ready for review",
              prompt: "Review source book",
              payload_type: "source_book_review",
              gate_data: {
                source_book_title: "Source Book",
                total_word_count: 4200,
                section_count: 7,
                sections: [
                  { section_id: "1", title: "Executive Summary", preview_paragraph: "..." },
                  { section_id: "2", title: "Client Context", preview_paragraph: "..." },
                  { section_id: "3", title: "Problem Framing", preview_paragraph: "..." },
                  { section_id: "4", title: "Solution Approach", preview_paragraph: "..." },
                  { section_id: "5", title: "Evidence Package", preview_paragraph: "..." },
                  { section_id: "6", title: "Delivery Blueprint", preview_paragraph: "..." },
                  { section_id: "7", title: "Risks and Assumptions", preview_paragraph: "..." },
                ],
                quality_summary: { reviewer_score: 92, benchmark_passed: true, evidence_count: 25, blueprint_count: 13 },
                evidence_summary: { evidence_ledger_entries: 25, external_source_count: 16 },
                blueprint_summary: { total_entries: 13, covered_sections: ["Executive Summary"] },
                docx_ready: true,
              },
              available_actions: ["approve", "reject"],
            },
            completed_gates: [
              { gate_number: 1, approved: true, feedback: "", decided_at: "2026-03-25T10:02:00Z" },
              { gate_number: 2, approved: true, feedback: "", decided_at: "2026-03-25T10:04:00Z" },
            ],
            started_at: "2026-03-25T10:00:00Z",
            elapsed_ms: 300000,
            error: null,
            outputs: {
              pptx_ready: false,
              docx_ready: true,
              source_index_ready: false,
              gap_report_ready: false,
              slide_count: 0,
              preview_ready: false,
              deliverables: [{ key: "docx", label: "Source Book DOCX", ready: true }],
            },
            session_metadata: {
              total_llm_calls: 12,
              total_input_tokens: 12000,
              total_output_tokens: 5400,
              total_cost_usd: 1.2,
            },
            agent_runs: [],
            deliverables: [{ key: "docx", label: "Source Book DOCX", ready: true }],
            rfp_name: "RFP",
            issuing_entity: "Entity",
          }),
        });
      }
      if (url.includes("/api/pipeline/session-e2e/export/docx")) {
        return route.fulfill({
          status: 200,
          headers: {
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "Content-Disposition": "attachment; filename=source-book.docx",
          },
          body: "docx",
        });
      }

      return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });
  });

  test("real routes: intake -> pipeline gate3 source book + PPT suppression", async ({ page }) => {
    await page.goto("/en/new");

    await page.locator("input[type='file']").setInputFiles({
      name: "RFP.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("pdf"),
    });
    await page.locator("#config-sector").selectOption("Government");
    await page.locator("#config-geography").selectOption("Saudi Arabia");
    await page.locator("#rfp-text-paste").fill("Optional pasted intake text");
    await page.getByTestId("start-pipeline-btn").click();

    await expect(page).toHaveURL(/\/en\/pipeline\/session-e2e$/);
    await page.reload();
    await expect(page.getByTestId("gate-3-source-book")).toBeVisible();
    await expect(page.getByTestId("gate-3-docx-download")).toBeVisible();
    await expect(page.getByText("Section Preview").first()).toBeVisible();
    await expect(page.locator("a[href*='/slides']")).toHaveCount(0);
  });

  test("real route: slides page shows PPT coming soon", async ({ page }) => {
    await page.goto("/en/pipeline/session-e2e/slides");
    await expect(page.getByRole("heading", { name: /coming soon/i })).toBeVisible();
  });
});

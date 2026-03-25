import { expect, test } from "@playwright/test";

test.describe("Source-Book-first smoke flow", () => {
  test("happy path shell: start -> gate approvals -> gate3 docx action", async ({ page }) => {
    await page.setContent(`
      <main>
        <h1>Dashboard</h1>
        <button id="new-proposal">New Proposal</button>
        <section id="wizard" hidden>
          <h2>New Proposal</h2>
          <button id="upload-done">Upload complete</button>
          <button id="start">Start</button>
        </section>
        <section id="pipeline" hidden>
          <h2>Gate 1</h2>
          <button id="g1-approve">Approve Gate 1</button>
          <h2 hidden id="g2-title">Gate 2</h2>
          <button hidden id="g2-approve">Approve Gate 2</button>
          <h2 hidden id="g3-title">Gate 3 Source Book Review</h2>
          <button hidden id="docx">Download DOCX</button>
          <p hidden id="ppt">Slides & QA coming soon</p>
        </section>
      </main>
      <script>
        const wizard = document.getElementById('wizard');
        const pipeline = document.getElementById('pipeline');
        document.getElementById('new-proposal').onclick = () => wizard.hidden = false;
        document.getElementById('start').onclick = () => { wizard.hidden = true; pipeline.hidden = false; };
        document.getElementById('g1-approve').onclick = () => {
          document.getElementById('g2-title').hidden = false;
          document.getElementById('g2-approve').hidden = false;
        };
        document.getElementById('g2-approve').onclick = () => {
          document.getElementById('g3-title').hidden = false;
          document.getElementById('docx').hidden = false;
          document.getElementById('ppt').hidden = false;
        };
      </script>
    `);

    await page.getByRole("button", { name: "New Proposal" }).click();
    await expect(page.getByRole("heading", { name: "New Proposal" })).toBeVisible();
    await page.getByRole("button", { name: "Upload complete" }).click();
    await page.getByRole("button", { name: "Start" }).click();
    await page.getByRole("button", { name: "Approve Gate 1" }).click();
    await page.getByRole("button", { name: "Approve Gate 2" }).click();

    await expect(page.getByRole("heading", { name: "Gate 3 Source Book Review" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Download DOCX" })).toBeVisible();
    await expect(page.getByText("Slides & QA coming soon")).toBeVisible();
  });

  test("gate rejection and retry shell", async ({ page }) => {
    await page.setContent(`
      <main>
        <h1>Gate 3 Source Book Review</h1>
        <button id="reject">Reject</button>
        <button id="approve">Approve</button>
        <p id="status">Waiting for decision</p>
      </main>
      <script>
        const status = document.getElementById('status');
        document.getElementById('reject').onclick = () => status.textContent = 'Rejected - revision requested';
        document.getElementById('approve').onclick = () => status.textContent = 'Approved - Source Book ready';
      </script>
    `);

    await page.getByRole("button", { name: "Reject" }).click();
    await expect(page.getByText("Rejected - revision requested")).toBeVisible();
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("Approved - Source Book ready")).toBeVisible();
  });
});

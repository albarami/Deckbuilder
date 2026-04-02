import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ArtifactViewerShell } from "./ArtifactViewerShell";

describe("ArtifactViewerShell", () => {
  it("renders title and children when not loading/error/empty", () => {
    render(
      <ArtifactViewerShell title="Evidence Ledger">
        <p>Table goes here</p>
      </ArtifactViewerShell>
    );

    expect(screen.getByText("Evidence Ledger")).toBeInTheDocument();
    expect(screen.getByText("Table goes here")).toBeInTheDocument();
  });

  it("renders subtitle when provided", () => {
    render(
      <ArtifactViewerShell title="Ledger" subtitle="12 entries found">
        <p>Content</p>
      </ArtifactViewerShell>
    );

    expect(screen.getByText("12 entries found")).toBeInTheDocument();
  });

  it("shows loading spinner when isLoading (children hidden)", () => {
    render(
      <ArtifactViewerShell title="Ledger" isLoading>
        <p>Should not appear</p>
      </ArtifactViewerShell>
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("Should not appear")).not.toBeInTheDocument();
  });

  it("shows error message when error is set (children hidden)", () => {
    render(
      <ArtifactViewerShell title="Ledger" error="Failed to load data">
        <p>Should not appear</p>
      </ArtifactViewerShell>
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Failed to load data");
    expect(screen.queryByText("Should not appear")).not.toBeInTheDocument();
  });

  it("shows empty message when isEmpty (children hidden)", () => {
    render(
      <ArtifactViewerShell title="Ledger" isEmpty emptyMessage="Nothing here">
        <p>Should not appear</p>
      </ArtifactViewerShell>
    );

    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.queryByText("Should not appear")).not.toBeInTheDocument();
  });

  it("renders download button and calls onDownload when clicked", async () => {
    const user = userEvent.setup();
    const handleDownload = vi.fn();

    render(
      <ArtifactViewerShell title="Ledger" onDownload={handleDownload} downloadLabel="Download JSON">
        <p>Content</p>
      </ArtifactViewerShell>
    );

    const downloadButton = screen.getByRole("button", { name: /download json/i });
    expect(downloadButton).toBeInTheDocument();

    await user.click(downloadButton);
    expect(handleDownload).toHaveBeenCalledTimes(1);
  });

  it("does not render download button when onDownload is not provided", () => {
    render(
      <ArtifactViewerShell title="Ledger">
        <p>Content</p>
      </ArtifactViewerShell>
    );

    expect(screen.queryByRole("button", { name: /download/i })).not.toBeInTheDocument();
  });
});

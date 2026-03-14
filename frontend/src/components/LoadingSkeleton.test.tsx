/**
 * LoadingSkeleton component tests.
 *
 * Tests the different skeleton variants and their rendering.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoadingSkeleton } from "./LoadingSkeleton";

describe("LoadingSkeleton", () => {
  it("renders with aria status role", () => {
    render(<LoadingSkeleton />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders with loading test id", () => {
    render(<LoadingSkeleton />);
    expect(screen.getByTestId("loading-skeleton")).toBeInTheDocument();
  });

  it("has screen reader text", () => {
    render(<LoadingSkeleton />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders card variant by default", () => {
    const { container } = render(<LoadingSkeleton />);
    // Card skeleton has a rounded-full element (avatar placeholder)
    const roundedFull = container.querySelector(".rounded-full");
    expect(roundedFull).toBeInTheDocument();
  });

  it("renders line variant", () => {
    const { container } = render(<LoadingSkeleton variant="line" count={4} />);
    const lines = container.querySelectorAll(".bg-sg-mist.h-4");
    expect(lines.length).toBe(4);
  });

  it("renders grid variant", () => {
    const { container } = render(<LoadingSkeleton variant="grid" count={6} />);
    const gridItems = container.querySelectorAll(".aspect-video");
    expect(gridItems.length).toBe(6);
  });

  it("renders form variant", () => {
    const { container } = render(<LoadingSkeleton variant="form" />);
    // Form skeleton has rounded-lg elements for input fields
    const fields = container.querySelectorAll(".rounded-lg.bg-sg-mist");
    expect(fields.length).toBeGreaterThanOrEqual(3);
  });

  it("renders table variant", () => {
    const { container } = render(<LoadingSkeleton variant="table" count={5} />);
    // Table has header row + data rows
    const rows = container.querySelectorAll(".flex.gap-4");
    // 1 header + 5 data rows = 6
    expect(rows.length).toBe(6);
  });

  it("applies animate-pulse class", () => {
    const { container } = render(<LoadingSkeleton />);
    const skeleton = container.firstChild;
    expect(skeleton).toHaveClass("animate-pulse");
  });

  it("applies custom className", () => {
    render(<LoadingSkeleton className="custom-class" />);
    expect(screen.getByTestId("loading-skeleton")).toHaveClass("custom-class");
  });
});

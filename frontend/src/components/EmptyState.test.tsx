/**
 * EmptyState component tests.
 *
 * Tests the no-data state with different icons and actions.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders with title", () => {
    render(<EmptyState title="No items found" />);
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    expect(screen.getByText("No items found")).toBeInTheDocument();
  });

  it("renders description when provided", () => {
    render(
      <EmptyState title="Empty" description="Nothing to show here." />,
    );
    expect(screen.getByText("Nothing to show here.")).toBeInTheDocument();
  });

  it("renders action button when provided", () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        title="No proposals"
        action={{ label: "Create New", onClick }}
      />,
    );
    const button = screen.getByText("Create New");
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders without action button by default", () => {
    render(<EmptyState title="Empty" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders custom children instead of default icon", () => {
    render(
      <EmptyState title="Custom">
        <div data-testid="custom-icon">Custom Icon</div>
      </EmptyState>,
    );
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    render(<EmptyState title="Empty" className="my-custom-class" />);
    expect(screen.getByTestId("empty-state")).toHaveClass("my-custom-class");
  });

  it("renders with document icon by default", () => {
    const { container } = render(<EmptyState title="Empty" />);
    // Default icon is document — renders an SVG inside a rounded-full div
    const iconContainer = container.querySelector(".rounded-full");
    expect(iconContainer).toBeInTheDocument();
    const svg = iconContainer?.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });
});

/**
 * Sidebar component tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "./Sidebar";

// ── Mocks ──────────────────────────────────────────────────────────────

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const messages: Record<string, string> = {
      "nav.dashboard": "Dashboard",
      "nav.newProposal": "New Proposal",
      "nav.history": "History",
    };
    return messages[key] ?? key;
  },
}));

// Mock i18n routing
let mockPathname = "/";
vi.mock("@/i18n/routing", () => ({
  usePathname: () => mockPathname,
  Link: ({
    href,
    children,
    className,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
    [key: string]: unknown;
  }) => (
    <a href={href} className={className} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/hooks/use-is-ppt-enabled", () => ({
  useIsPptEnabled: () => false,
}));

// ── Tests ──────────────────────────────────────────────────────────────

describe("Sidebar", () => {
  beforeEach(() => {
    mockPathname = "/";
  });

  it("renders all navigation items", () => {
    render(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("New Proposal")).toBeInTheDocument();
    expect(screen.getByText("History")).toBeInTheDocument();
  });

  it("has navigation landmark", () => {
    render(<Sidebar />);
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("highlights dashboard as active on root path", () => {
    mockPathname = "/";
    render(<Sidebar />);
    const dashboardLink = screen.getByText("Dashboard").closest("a");
    expect(dashboardLink).toHaveAttribute("aria-current", "page");
  });

  it("highlights new proposal as active on /new path", () => {
    mockPathname = "/new";
    render(<Sidebar />);
    const newLink = screen.getByText("New Proposal").closest("a");
    expect(newLink).toHaveAttribute("aria-current", "page");

    const dashboardLink = screen.getByText("Dashboard").closest("a");
    expect(dashboardLink).not.toHaveAttribute("aria-current");
  });

  it("renders version info", () => {
    render(<Sidebar />);
    expect(screen.getByText("DeckForge v0.1.0")).toBeInTheDocument();
  });

  it("renders correct hrefs", () => {
    render(<Sidebar />);
    const dashboardLink = screen.getByText("Dashboard").closest("a");
    expect(dashboardLink).toHaveAttribute("href", "/");

    const newLink = screen.getByText("New Proposal").closest("a");
    expect(newLink).toHaveAttribute("href", "/new");

    const historyLink = screen.getByText("History").closest("a");
    expect(historyLink).toHaveAttribute("href", "/history");
  });
});

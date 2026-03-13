/**
 * TopBar component tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { TopBar } from "./TopBar";

// ── Mocks ──────────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const messages: Record<string, string> = {
      "app.name": "DeckForge",
      "common.switchToArabic": "Switch to Arabic",
      "common.switchToEnglish": "Switch to English",
    };
    return messages[key] ?? key;
  },
}));

const mockLocaleStore = {
  locale: "en" as "en" | "ar",
  direction: "ltr" as "ltr" | "rtl",
  isRtl: false,
  setLocale: vi.fn(),
};

vi.mock("@/stores/locale-store", () => ({
  useLocaleStore: (selector?: (state: typeof mockLocaleStore) => unknown) =>
    selector ? selector(mockLocaleStore) : mockLocaleStore,
}));

vi.mock("@/i18n/routing", () => ({
  Link: ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

// ── Tests ──────────────────────────────────────────────────────────────

describe("TopBar", () => {
  beforeEach(() => {
    mockLocaleStore.locale = "en";
    mockLocaleStore.direction = "ltr";
    mockLocaleStore.isRtl = false;
  });

  it("renders brand name", () => {
    render(<TopBar />);
    expect(screen.getByText("DeckForge")).toBeInTheDocument();
  });

  it("renders SG logo SVG", () => {
    render(<TopBar />);
    expect(
      screen.getByLabelText("Strategic Gears logo"),
    ).toBeInTheDocument();
  });

  it("renders locale switcher with Arabic label when locale is EN", () => {
    render(<TopBar />);
    const switcher = screen.getByLabelText("Switch to Arabic");
    expect(switcher).toBeInTheDocument();
    expect(switcher).toHaveAttribute("href", "/ar");
  });

  it("renders locale switcher with English label when locale is AR", () => {
    mockLocaleStore.locale = "ar";
    render(<TopBar />);
    const switcher = screen.getByLabelText("Switch to English");
    expect(switcher).toBeInTheDocument();
    expect(switcher).toHaveAttribute("href", "/en");
  });

  it("renders user avatar placeholder", () => {
    render(<TopBar />);
    expect(screen.getByLabelText("User")).toBeInTheDocument();
    expect(screen.getByText("D")).toBeInTheDocument();
  });
});

/**
 * TopBar component tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { TopBar } from "./TopBar";

// ── matchMedia polyfill for jsdom ──────────────────────────────────────
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// ── Mocks ──────────────────────────────────────────────────────────────

vi.mock("next/image", () => ({
  default: (props: Record<string, unknown>) => {
    // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text, @typescript-eslint/no-unused-vars
    const { priority, fill, ...rest } = props;
    return <img {...rest} />;
  },
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const messages: Record<string, string> = {
      "app.name": "DeckForge",
      "app.company": "Strategic Gears",
      "common.switchToArabic": "Switch to Arabic",
      "common.switchToEnglish": "Switch to English",
      "common.themeLight": "Switch to light mode",
      "common.themeDark": "Switch to dark mode",
    };
    return messages[key] ?? key;
  },
}));

vi.mock("@/stores/theme-store", () => ({
  useThemeStore: () => ({
    preference: "system",
    resolved: "light",
    hydrated: true,
    initialize: vi.fn(),
    toggle: vi.fn(),
    setPreference: vi.fn(),
  }),
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
    expect(screen.getByText("Strategic Gears")).toBeInTheDocument();
  });

  it("renders SG logo image", () => {
    render(<TopBar />);
    expect(
      screen.getByAltText("Strategic Gears logo"),
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
    expect(screen.getByText("SG")).toBeInTheDocument();
  });
});

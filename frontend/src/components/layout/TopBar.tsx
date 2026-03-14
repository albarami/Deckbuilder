/**
 * TopBar — Brand header with logo, locale switcher, and user avatar placeholder.
 *
 * Extracted from the original [locale]/layout.tsx header into a standalone component.
 * RTL-aware: flex direction is auto-mirrored by Tailwind's RTL utilities.
 */

"use client";

import { useTranslations } from "next-intl";
import { useLocaleStore } from "@/stores/locale-store";
import { Link } from "@/i18n/routing";

export function TopBar() {
  const t = useTranslations();
  const { locale } = useLocaleStore();

  const otherLocale = locale === "en" ? "ar" : "en";
  const switchLabel =
    locale === "en" ? t("common.switchToArabic") : t("common.switchToEnglish");

  return (
    <header className="border-b border-sg-navy/10 bg-sg-navy text-sg-white">
      <div className="flex h-14 items-center justify-between px-4">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-3">
          <svg
            width="28"
            height="28"
            viewBox="0 0 32 32"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-label="Strategic Gears logo"
          >
            <circle cx="16" cy="16" r="14" fill="#0F9ED5" />
            <path
              d="M10 16L14 20L22 12"
              stroke="white"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="font-display text-lg font-semibold tracking-tight">
            {t("app.name")}
          </span>
        </Link>

        {/* Right side: locale + user */}
        <div className="flex items-center gap-3">
          {/* Locale switcher */}
          <a
            href={`/${otherLocale}`}
            className="rounded-md border border-white/20 px-3 py-1.5 text-xs font-medium text-white/90 transition-colors hover:bg-white/10 hover:text-white"
            aria-label={switchLabel}
          >
            {locale === "en" ? "\u0627\u0644\u0639\u0631\u0628\u064a\u0629" : "English"}
          </a>

          {/* User avatar placeholder (stub for M11 — no real auth) */}
          <div
            className="flex h-8 w-8 items-center justify-center rounded-full bg-sg-teal text-xs font-bold text-white"
            aria-label="User"
            title="Developer"
          >
            D
          </div>
        </div>
      </div>
    </header>
  );
}

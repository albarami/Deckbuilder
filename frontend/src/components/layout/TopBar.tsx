/**
 * TopBar — Brand header with logo, locale switcher, and user avatar placeholder.
 *
 * Extracted from the original [locale]/layout.tsx header into a standalone component.
 * RTL-aware: flex direction is auto-mirrored by Tailwind's RTL utilities.
 */

"use client";

import { useEffect } from "react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { Globe, MoonStar, SunMedium } from "lucide-react";
import { useLocaleStore } from "@/stores/locale-store";
import { useThemeStore } from "@/stores/theme-store";
import { Link } from "@/i18n/routing";

export function TopBar() {
  const t = useTranslations();
  const { locale } = useLocaleStore();
  const { resolved, initialize, toggle } = useThemeStore();

  const otherLocale = locale === "en" ? "ar" : "en";
  const switchLabel =
    locale === "en" ? t("common.switchToArabic") : t("common.switchToEnglish");

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
    <header className="border-b border-white/5 bg-sg-navy text-sg-white shadow-sg-card dark:border-slate-800 dark:bg-slate-950">
      <div className="flex h-16 items-center justify-between gap-4 px-6">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <div className="rounded-lg bg-white/5 p-1.5">
            <Image
              src="/sg-gear.svg"
              alt={`${t("app.company")} logo`}
              width={34}
              height={30}
              priority
            />
          </div>
          <div className="min-w-0">
            <p className="truncate font-display text-base font-semibold tracking-tight text-white">
              {t("app.company")}
            </p>
            <p className="truncate text-xs font-medium uppercase tracking-[0.18em] text-white/55">
              {t("app.name")}
            </p>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggle}
            className="inline-flex items-center gap-2 rounded-md border border-white/15 px-3 py-1.5 text-xs font-medium text-white/80 transition-colors duration-200 hover:bg-white/10 hover:text-white"
            aria-label={
              resolved === "dark" ? t("common.themeLight") : t("common.themeDark")
            }
            title={
              resolved === "dark" ? t("common.themeLight") : t("common.themeDark")
            }
          >
            {resolved === "dark" ? (
              <SunMedium className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <MoonStar className="h-3.5 w-3.5" aria-hidden="true" />
            )}
          </button>
          <a
            href={`/${otherLocale}`}
            className="inline-flex items-center gap-2 rounded-md border border-white/15 px-3 py-1.5 text-xs font-medium text-white/80 transition-colors duration-200 hover:bg-white/10 hover:text-white"
            aria-label={switchLabel}
          >
            <Globe className="h-3.5 w-3.5" aria-hidden="true" />
            {locale === "en" ? "\u0627\u0644\u0639\u0631\u0628\u064a\u0629" : "English"}
          </a>

          <div
            className="flex h-8 w-8 items-center justify-center rounded-full bg-sg-teal text-xs font-bold text-white shadow-sg-glow-blue"
            aria-label="User"
            title={t("app.company")}
          >
            SG
          </div>
        </div>
      </div>
    </header>
  );
}

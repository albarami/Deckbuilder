/**
 * LocaleLayoutClient — Client component that renders the app shell.
 *
 * Provides: TopBar + Sidebar + main content area.
 * Syncs the URL-based locale into the Zustand locale store.
 */

"use client";

import { useEffect } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { Sidebar } from "@/components/layout/Sidebar";
import { useLocaleStore } from "@/stores/locale-store";
import type { Locale } from "@/i18n/config";

interface LocaleLayoutClientProps {
  locale: Locale;
  children: React.ReactNode;
}

export function LocaleLayoutClient({
  locale,
  children,
}: LocaleLayoutClientProps) {
  const setLocale = useLocaleStore((s) => s.setLocale);

  // Sync locale from URL into Zustand store
  useEffect(() => {
    setLocale(locale);
  }, [locale, setLocale]);

  return (
    <>
      {/* Top bar — full width */}
      <TopBar />

      {/* Content area — sidebar + main */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto px-page py-section">
          <div className="mx-auto max-w-5xl">{children}</div>
        </main>
      </div>
    </>
  );
}

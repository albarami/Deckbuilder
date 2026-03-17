/**
 * LocaleLayoutClient — Client component that renders the app shell.
 *
 * Provides: AuthProvider + TopBar + Sidebar + main content area.
 * Syncs the URL-based locale into the Zustand locale store.
 * Wraps content in ErrorBoundary for catch-all error handling.
 */

"use client";

import { useEffect } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { Sidebar } from "@/components/layout/Sidebar";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider } from "@/lib/auth/context";
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
    <AuthProvider>
      <TopBar />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-[1280px]">
            <ErrorBoundary>
              {children}
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </AuthProvider>
  );
}

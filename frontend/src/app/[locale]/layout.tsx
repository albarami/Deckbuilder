import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { getDirection } from "@/i18n/config";
import type { Locale } from "@/i18n/config";

interface LocaleLayoutProps {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}

export default async function LocaleLayout({
  children,
  params,
}: LocaleLayoutProps) {
  const { locale } = await params;

  // Validate locale
  if (!routing.locales.includes(locale as typeof routing.locales[number])) {
    notFound();
  }

  const messages = await getMessages();
  const dir = getDirection(locale as Locale);

  return (
    <div dir={dir} lang={locale} className="min-h-screen">
      <NextIntlClientProvider messages={messages}>
        {/* Top navigation bar */}
        <header className="bg-sg-navy text-sg-white">
          <div className="mx-auto max-w-7xl px-page py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <svg
                width="32"
                height="32"
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
              <span className="font-display text-xl font-semibold tracking-tight">
                DeckForge
              </span>
            </div>
            <nav className="flex items-center gap-4">
              <LocaleSwitcher currentLocale={locale as Locale} />
            </nav>
          </div>
        </header>

        {/* Main content area */}
        <main className="mx-auto max-w-7xl px-page py-section">
          {children}
        </main>
      </NextIntlClientProvider>
    </div>
  );
}

/**
 * Locale switcher component — toggles between EN and AR.
 */
function LocaleSwitcher({ currentLocale }: { currentLocale: Locale }) {
  const otherLocale = currentLocale === "en" ? "ar" : "en";
  const label = currentLocale === "en" ? "العربية" : "English";

  return (
    <a
      href={`/${otherLocale}`}
      className="rounded-md border border-white/20 px-3 py-1.5 text-sm font-medium text-white/90 transition-colors hover:bg-white/10 hover:text-white"
    >
      {label}
    </a>
  );
}

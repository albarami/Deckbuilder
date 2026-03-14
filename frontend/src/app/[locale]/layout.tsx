import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { getDirection } from "@/i18n/config";
import type { Locale } from "@/i18n/config";
import { LocaleLayoutClient } from "./LocaleLayoutClient";

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
    <div dir={dir} lang={locale} className="flex h-screen flex-col">
      <NextIntlClientProvider messages={messages}>
        <LocaleLayoutClient locale={locale as Locale}>
          {children}
        </LocaleLayoutClient>
      </NextIntlClientProvider>
    </div>
  );
}

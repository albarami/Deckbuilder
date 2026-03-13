/**
 * i18n Configuration
 *
 * Supported locales: English (LTR) and Arabic (RTL).
 * Locale detection is URL-path-based: /en/... or /ar/...
 */

export const locales = ["en", "ar"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "en";

/** RTL locales for layout direction */
export const rtlLocales: readonly Locale[] = ["ar"] as const;

export function isRtl(locale: Locale): boolean {
  return (rtlLocales as readonly string[]).includes(locale);
}

export function getDirection(locale: Locale): "ltr" | "rtl" {
  return isRtl(locale) ? "rtl" : "ltr";
}

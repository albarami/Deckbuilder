/**
 * Locale Store — Zustand state for language and layout direction.
 *
 * This store provides client-side locale state that syncs with
 * the URL-based locale from next-intl. It allows components to
 * read locale/direction without prop drilling.
 */

import { create } from "zustand";
import type { Locale } from "@/i18n/config";
import { isRtl, getDirection } from "@/i18n/config";

interface LocaleState {
  locale: Locale;
  direction: "ltr" | "rtl";
  isRtl: boolean;
}

interface LocaleActions {
  /** Set the active locale (called by layout on mount) */
  setLocale: (locale: Locale) => void;
}

export type LocaleStore = LocaleState & LocaleActions;

export const useLocaleStore = create<LocaleStore>((set) => ({
  locale: "en",
  direction: "ltr",
  isRtl: false,

  setLocale: (locale) =>
    set({
      locale,
      direction: getDirection(locale),
      isRtl: isRtl(locale),
    }),
}));

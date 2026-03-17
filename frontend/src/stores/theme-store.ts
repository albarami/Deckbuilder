"use client";

import { create } from "zustand";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "deckforge-theme";

interface ThemeState {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  hydrated: boolean;
  initialize: () => void;
  setPreference: (preference: ThemePreference) => void;
  toggle: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  preference: "system",
  resolved: "light",
  hydrated: false,
  initialize: () => {
    if (typeof window === "undefined") return;

    const stored = window.localStorage.getItem(STORAGE_KEY) as ThemePreference | null;
    const preference = stored ?? "system";
    const resolved = resolveTheme(preference);
    applyTheme(resolved);

    set({ preference, resolved, hydrated: true });

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (get().preference !== "system") return;
      const nextResolved = resolveTheme("system");
      applyTheme(nextResolved);
      set({ resolved: nextResolved });
    };

    media.addEventListener("change", onChange);
  },
  setPreference: (preference) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, preference);
    }
    const resolved = resolveTheme(preference);
    applyTheme(resolved);
    set({ preference, resolved });
  },
  toggle: () => {
    const next = get().resolved === "dark" ? "light" : "dark";
    get().setPreference(next);
  },
}));

function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === "light" || preference === "dark") {
    return preference;
  }

  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(resolved: ResolvedTheme) {
  if (typeof document === "undefined") return;

  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.style.colorScheme = resolved;
}

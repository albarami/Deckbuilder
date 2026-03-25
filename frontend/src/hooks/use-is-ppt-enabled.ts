"use client";

const PPT_TRUE_VALUES = new Set(["1", "true", "yes", "on"]);

export function useIsPptEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_ENABLE_PPT ?? "";
  return PPT_TRUE_VALUES.has(raw.trim().toLowerCase());
}

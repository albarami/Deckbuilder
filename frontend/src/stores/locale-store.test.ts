/**
 * Tests for locale-store.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useLocaleStore } from "./locale-store";

beforeEach(() => {
  useLocaleStore.getState().setLocale("en");
});

describe("LocaleStore", () => {
  it("defaults to English LTR", () => {
    const state = useLocaleStore.getState();
    expect(state.locale).toBe("en");
    expect(state.direction).toBe("ltr");
    expect(state.isRtl).toBe(false);
  });

  it("switches to Arabic RTL", () => {
    useLocaleStore.getState().setLocale("ar");

    const state = useLocaleStore.getState();
    expect(state.locale).toBe("ar");
    expect(state.direction).toBe("rtl");
    expect(state.isRtl).toBe(true);
  });

  it("switches back to English LTR", () => {
    useLocaleStore.getState().setLocale("ar");
    useLocaleStore.getState().setLocale("en");

    const state = useLocaleStore.getState();
    expect(state.locale).toBe("en");
    expect(state.direction).toBe("ltr");
    expect(state.isRtl).toBe(false);
  });
});

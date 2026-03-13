import { Inter, IBM_Plex_Sans, IBM_Plex_Sans_Arabic, IBM_Plex_Mono } from "next/font/google";

/**
 * Strategic Gears Font Stack
 *
 * Production: Euclid Flex (commercial, loaded locally via public/fonts/)
 * Development: Inter (Google Font, visually similar geometric sans-serif)
 *
 * To use Euclid Flex in production:
 * 1. Place .woff2 files in public/fonts/ (EuclidFlex-Regular, Medium, Semibold, Bold)
 * 2. Switch the displayFont export below to the localFont variant
 *
 * Body fonts:
 * - IBM Plex Sans: Body text (English)
 * - IBM Plex Sans Arabic: Body text (Arabic)
 * - IBM Plex Mono: Code/technical data
 */

// ── Display font (headings, navigation, prominent labels) ─────────────
// Development substitute for Euclid Flex (geometric sans-serif)
export const displayFont = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

// ── IBM Plex Sans (body text, English) ────────────────────────────────
export const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

// ── IBM Plex Sans Arabic (body text, Arabic) ──────────────────────────
export const ibmPlexSansArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-arabic",
  display: "swap",
});

// ── IBM Plex Mono (code, session IDs) ─────────────────────────────────
export const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

/*
 * ── Euclid Flex (production) ──────────────────────────────────────────
 * Uncomment and replace displayFont export when font files are available:
 *
 * import localFont from "next/font/local";
 *
 * export const displayFont = localFont({
 *   src: [
 *     { path: "../../public/fonts/EuclidFlex-Regular.woff2", weight: "400", style: "normal" },
 *     { path: "../../public/fonts/EuclidFlex-Medium.woff2", weight: "500", style: "normal" },
 *     { path: "../../public/fonts/EuclidFlex-Semibold.woff2", weight: "600", style: "normal" },
 *     { path: "../../public/fonts/EuclidFlex-Bold.woff2", weight: "700", style: "normal" },
 *   ],
 *   variable: "--font-display",
 *   display: "swap",
 *   fallback: ["Inter", "system-ui", "sans-serif"],
 * });
 */

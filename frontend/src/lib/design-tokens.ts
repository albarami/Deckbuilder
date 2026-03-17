/**
 * Strategic Gears Design Tokens
 *
 * Single source of truth for brand colors, typography, and spacing.
 * These values are mirrored in tailwind.config.ts for utility classes.
 * Use these constants when you need programmatic access to design values.
 */

// ── Brand Colors ──────────────────────────────────────────────────────
export const colors = {
  /** Primary brand — headers, dark surfaces, sidebar backgrounds */
  navy: "#0E2841",
  /** Secondary accent — hover states, secondary buttons */
  teal: "#156082",
  /** Interactive — links, active states, focus rings */
  blue: "#0F9ED5",
  /** CTA — alerts, progress indicators, call-to-action buttons */
  orange: "#E97132",
  /** Body text — default text color */
  slate: "#2D3748",
  /** Background — page background, card surfaces */
  mist: "#F0F4F8",
  /** Content areas — card interiors, modals */
  white: "#FFFFFF",
  /** Dividers — borders, input outlines */
  border: "#D2D6DC",
} as const;

// ── Typography ────────────────────────────────────────────────────────
export const fontFamily = {
  /** Brand display font — headings, navigation, prominent labels */
  display: "Euclid Flex",
  /** Body text (English/Latin) */
  body: "IBM Plex Sans",
  /** Body text (Arabic) */
  arabic: "IBM Plex Sans Arabic",
  /** Monospace — code, session IDs, technical data */
  mono: "IBM Plex Mono",
} as const;

export const fontSize = {
  /** Page titles, hero text */
  h1: "2rem",       // 32px
  /** Section headings */
  h2: "1.5rem",     // 24px
  /** Subsection headings */
  h3: "1.25rem",    // 20px
  /** Card titles, labels */
  h4: "1.125rem",   // 18px
  /** Body text */
  body: "1rem",     // 16px
  /** Secondary text, captions */
  sm: "0.875rem",   // 14px
  /** Tertiary text, labels */
  xs: "0.75rem",    // 12px
} as const;

export const fontWeight = {
  regular: "400",
  medium: "500",
  semibold: "600",
  bold: "700",
} as const;

// ── Spacing ───────────────────────────────────────────────────────────
export const spacing = {
  /** Page-level padding */
  page: "2rem",      // 32px
  /** Card internal padding */
  card: "1.5rem",    // 24px
  /** Between major sections */
  section: "2.5rem", // 40px
  /** Compact gap between items */
  compact: "1rem",   // 16px
} as const;

// ── Border Radius ─────────────────────────────────────────────────────
export const borderRadius = {
  sm: "0.375rem",    // 6px
  md: "0.5rem",      // 8px
  lg: "0.75rem",     // 12px
  full: "9999px",
} as const;

// ── Shadows ───────────────────────────────────────────────────────────
export const shadows = {
  /** Cards, dropdowns */
  card: "0 1px 3px rgba(14, 40, 65, 0.08), 0 1px 2px rgba(14, 40, 65, 0.06)",
  /** Elevated elements, modals */
  elevated: "0 4px 6px rgba(14, 40, 65, 0.07), 0 2px 4px rgba(14, 40, 65, 0.06)",
  /** Focused inputs */
  focus: "0 0 0 3px rgba(15, 158, 213, 0.3)",
  /** Active pipeline stage glow */
  glowTeal:
    "0 0 0 1px rgba(21, 96, 130, 0.18), 0 10px 24px rgba(21, 96, 130, 0.18), 0 0 24px rgba(15, 158, 213, 0.16)",
  /** Active agent / status glow */
  glowBlue:
    "0 0 0 1px rgba(15, 158, 213, 0.18), 0 8px 20px rgba(15, 158, 213, 0.14), 0 0 18px rgba(15, 158, 213, 0.12)",
} as const;

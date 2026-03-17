import type { Metadata } from "next";
import { displayFont, ibmPlexSans, ibmPlexMono } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Strategic Gears | DeckForge",
  description:
    "Strategic Gears' enterprise proposal generation system for creating, reviewing, governing, and exporting source-backed consulting proposals.",
};

/**
 * Root layout — provides global font CSS variables.
 * Locale-specific layout (dir, lang) is handled in [locale]/layout.tsx.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html suppressHydrationWarning>
      <body
        className={`${displayFont.variable} ${ibmPlexSans.variable} ${ibmPlexMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}

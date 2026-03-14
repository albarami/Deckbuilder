import type { Metadata } from "next";
import { displayFont, ibmPlexSans, ibmPlexMono } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "DeckForge — Strategic Proposal Engine",
  description:
    "Enterprise proposal generation engine for Strategic Gears consultants. Create, review, and export branded proposals.",
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

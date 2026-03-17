import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "sg-navy": "#0E2841",
        "sg-teal": "#156082",
        "sg-blue": "#0F9ED5",
        "sg-orange": "#E97132",
        "sg-slate": "#2D3748",
        "sg-mist": "#F0F4F8",
        "sg-white": "#FFFFFF",
        "sg-border": "#D2D6DC",
      },
      fontFamily: {
        display: ["Euclid Flex", "system-ui", "sans-serif"],
        body: ["IBM Plex Sans", "system-ui", "sans-serif"],
        arabic: ["IBM Plex Sans Arabic", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      boxShadow: {
        "sg-card":
          "0 1px 3px rgba(14, 40, 65, 0.08), 0 1px 2px rgba(14, 40, 65, 0.06)",
        "sg-elevated":
          "0 4px 6px rgba(14, 40, 65, 0.07), 0 2px 4px rgba(14, 40, 65, 0.06)",
        "sg-glow-teal":
          "0 0 0 1px rgba(21, 96, 130, 0.18), 0 10px 24px rgba(21, 96, 130, 0.18), 0 0 24px rgba(15, 158, 213, 0.16)",
        "sg-glow-blue":
          "0 0 0 1px rgba(15, 158, 213, 0.18), 0 8px 20px rgba(15, 158, 213, 0.14), 0 0 18px rgba(15, 158, 213, 0.12)",
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-down": {
          "0%": { opacity: "0", transform: "translateY(-12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulse: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        "shimmer-bar": {
          "0%": { "background-position": "200% 0" },
          "100%": { "background-position": "-200% 0" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 240ms ease-out",
        "fade-in-down": "fade-in-down 240ms ease-out",
        pulse: "pulse 2.2s ease-in-out infinite",
        "shimmer-bar": "shimmer-bar 2s ease-in-out infinite",
      },
      spacing: {
        "page": "2rem",
        "card": "1.5rem",
        "section": "2.5rem",
        "compact": "1rem",
      },
    },
  },
  plugins: [],
};
export default config;

import type { Config } from "tailwindcss";

const config: Config = {
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

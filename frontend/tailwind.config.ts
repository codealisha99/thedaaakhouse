import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F4ECD8",
        envelope: "#FBF6EA",
        kraft: "#C9A978",
        kraftdark: "#A9854F",
        postred: "#C8102E",
        postreddark: "#9C0B23",
        postalnavy: "#1B2A49",
        postalnavydeep: "#101B33",
        airmailblue: "#2E6FBF",
        airmailred: "#D64545",
        ink: "#1A1A1A",
        stampurple: "#5B3A8C",
        postmark: "#5C6B7A",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
        hand: ["var(--font-hand)", "cursive"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        paper: "0 1px 2px rgba(26,26,26,.18), 0 4px 14px rgba(26,26,26,.14)",
        paperlift: "0 2px 4px rgba(26,26,26,.18), 0 12px 28px rgba(26,26,26,.22)",
        stamp: "0 2px 0 rgba(26,26,26,.25)",
      },
    },
  },
  plugins: [],
};
export default config;

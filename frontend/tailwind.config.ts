import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        sage: "var(--sage)",
        green: "var(--green)",
        greendeep: "var(--green-deep)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        danger: "var(--danger)",
        ok: "var(--ok)",
      },
      fontFamily: {
        pixel: ["var(--font-pixel)", "monospace"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        hard: "4px 4px 0 var(--shadow)",
        hardsm: "2px 2px 0 var(--shadow)",
        hardlg: "6px 6px 0 var(--shadow)",
      },
    },
  },
  plugins: [],
};
export default config;

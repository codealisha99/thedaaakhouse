import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { ink: "#0f172a", accent: "#6d28d9" },
    },
  },
  plugins: [],
};
export default config;

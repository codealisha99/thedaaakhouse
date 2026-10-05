import type { Metadata } from "next";
import { Caveat, Courier_Prime, Fraunces, Inter } from "next/font/google";
import Shell from "@/components/shell";
import { ThemeProvider } from "@/components/post/theme";
import "./globals.css";

const serif = Fraunces({ subsets: ["latin"], variable: "--font-serif", display: "swap" });
const mono = Courier_Prime({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-mono", display: "swap" });
const hand = Caveat({ subsets: ["latin"], variable: "--font-hand", display: "swap" });
const sans = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "thedaaakhouse — Job-search operating system",
  description: "One place to track applications, tailor resumes, check ATS, and prep interviews.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${serif.variable} ${mono.variable} ${hand.variable} ${sans.variable} bg-paper font-sans text-ink antialiased`}>
        {/* SVG defs for ink-bleed filter used by rubber stamps */}
        <svg width="0" height="0" aria-hidden="true" style={{ position: "absolute" }}>
          <defs>
            <filter id="ink-bleed">
              <feTurbulence type="fractalNoise" baseFrequency="0.6" numOctaves="2" result="n" />
              <feDisplacementMap in="SourceGraphic" in2="n" scale="1.6" />
            </filter>
          </defs>
        </svg>
        <ThemeProvider>
          <Shell>{children}</Shell>
        </ThemeProvider>
      </body>
    </html>
  );
}

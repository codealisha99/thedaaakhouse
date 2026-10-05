import type { Metadata } from "next";
import { Pixelify_Sans, Space_Mono } from "next/font/google";
import Shell from "@/components/shell";
import "./globals.css";

const pixel = Pixelify_Sans({ subsets: ["latin"], variable: "--font-pixel", display: "swap" });
const mono = Space_Mono({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "thedaaakhouse — Job-search operating system",
  description: "One place to track applications, tailor resumes, check ATS, and prep interviews.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${pixel.variable} ${mono.variable} font-mono antialiased`}>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}

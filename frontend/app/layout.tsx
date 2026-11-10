import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import Shell from "@/components/shell";
import AuthProvider from "@/components/auth-provider";
import { ToastProvider } from "@/components/toast";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });
const display = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--font-instrument", display: "swap" });

export const metadata: Metadata = {
  title: "thedaaakhouse — every job application, tracked like registered post",
  description:
    "Track each application with its job description, the resume you sent, an ATS score that shows its maths, interview prep, and every status change.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f1ea" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1013" },
  ],
};

// Runs before paint: applies the saved/system theme and marks JS as available
// (scroll reveals only hide content when JS can reveal it again).
const bootScript = `try{var d=document.documentElement,s=localStorage.getItem("tdh-dark");d.classList.add("js");if(s==="1"||(s===null&&matchMedia("(prefers-color-scheme: dark)").matches))d.classList.add("dark")}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: bootScript }} />
      </head>
      <body className={`${sans.variable} ${mono.variable} ${display.variable} font-sans text-[15px] antialiased`}>
        <AuthProvider>
          <ToastProvider>
            <Shell>{children}</Shell>
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

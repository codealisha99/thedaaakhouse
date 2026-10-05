import type { Metadata } from "next";
import Shell from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Darkhouse — Job-search operating system",
  description: "One place to track applications, tailor resumes, check ATS, and prep interviews.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}

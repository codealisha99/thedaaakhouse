"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, token } from "@/lib/api";
import { LabelTape } from "./post/postal";
import { useTheme } from "./post/theme";

const NAV: { section: string; links: { href: string; label: string; postal: string }[] }[] = [
  {
    section: "Applications",
    links: [
      { href: "/applications", label: "Overview", postal: "The Front Counter" },
      { href: "/applications/new", label: "Job Analyzer", postal: "Letter Opening Desk" },
      { href: "/applications/company", label: "Company Research", postal: "The Directory" },
      { href: "/applications/interview", label: "Interview Prep", postal: "Appointment Slips" },
    ],
  },
  {
    section: "Job Tracker",
    links: [{ href: "/tracker", label: "Tracker", postal: "Pigeonholes" }],
  },
  {
    section: "Resume",
    links: [
      { href: "/resume", label: "My Resumes", postal: "The Filing Cabinet" },
      { href: "/resume/tailor", label: "Tailor Resume", postal: "The Tailoring Table" },
      { href: "/resume/ats", label: "ATS Checker", postal: "Customs & Inspection" },
    ],
  },
];

function Wordmark() {
  return (
    <Link href="/tracker" className="group flex items-center gap-3">
      <span className="flex h-14 w-14 shrink-0 rotate-[-6deg] items-center justify-center rounded-full border-[3px] border-dashed border-kraft text-2xl transition-transform group-hover:rotate-3" aria-hidden="true">
        🕊️
      </span>
      <span>
        <span className="block font-serif text-lg font-bold leading-none tracking-tight text-paper">thedaaakhouse</span>
        <span className="mt-1 block font-mono text-[10px] uppercase tracking-[0.2em] text-kraft">Job-search operating system</span>
      </span>
    </Link>
  );
}

function NavList({ user, onNav, bottom = false }: { user: string | null; onNav?: () => void; bottom?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const { plain, night, sound, togglePlain, toggleNight, toggleSound } = useTheme();
  return (
    <div className="flex h-full flex-col">
      {!bottom && <div className="px-5 pb-2 pt-6"><Wordmark /></div>}
      <nav className={`flex-1 space-y-5 overflow-y-auto px-3 ${bottom ? "py-2" : "py-4"}`}>
        {NAV.map((group) => (
          <div key={group.section}>
            <div className="px-2 pb-1.5"><LabelTape>{group.section}</LabelTape></div>
            <ul className="space-y-1">
              {group.links.map((l) => {
                const active = pathname === l.href || (l.href !== "/tracker" && pathname.startsWith(l.href + "/"));
                return (
                  <li key={l.href} className={active ? "translate-x-1" : ""}>
                    <Link
                      href={l.href}
                      onClick={onNav}
                      className={active
                        ? "block -rotate-[0.5deg] rounded-r-md rounded-l-[2px] border-l-4 border-postred bg-kraft px-3 py-2 shadow-stamp"
                        : "block rounded-md px-3 py-2 text-paper/80 hover:bg-white/10 hover:text-paper"}
                    >
                      <span className={`block text-sm font-bold ${active ? "text-postalnavy" : ""}`}>{l.label}</span>
                      <span className={`postal-copy block font-hand text-base italic leading-tight ${active ? "text-postalnavy/70" : "text-kraft/80"}`}>{l.postal}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-white/15 p-4">
        {user ? (
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-mono text-xs text-paper/80">{user}</span>
            <button
              onClick={() => { token.clear(); router.push("/login"); }}
              className="min-h-[44px] rounded-md border border-kraft/60 px-2.5 text-xs font-bold text-kraft hover:bg-white/10"
            >
              Log out
            </button>
          </div>
        ) : (
          <Link href="/login" onClick={onNav} className="block text-sm font-bold text-paper">
            Log in
            <span className="postal-copy block font-hand text-base italic text-kraft/80">Sign the Register</span>
          </Link>
        )}
        <div className="mt-3 flex gap-1.5">
          {[
            { label: plain ? "Rich mode" : "Plain mode", fn: togglePlain, on: plain },
            { label: night ? "Day shift" : "Night shift", fn: toggleNight, on: night },
            { label: sound ? "Mute" : "Sound", fn: toggleSound, on: sound },
          ].map((t) => (
            <button key={t.label} onClick={t.fn}
              className={`min-h-[44px] flex-1 rounded-md border px-1 font-mono text-[10px] uppercase tracking-wider ${t.on ? "border-kraft bg-kraft/20 text-kraft" : "border-white/20 text-paper/60 hover:text-paper"}`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (pathname.startsWith("/login")) { setChecked(true); return; }
    if (!token.get()) { router.replace("/login"); return; }
    api.me()
      .then((me) => { setUser(me.username); setChecked(true); })
      .catch(() => { setUser(null); setChecked(true); });
  }, [pathname, router]);

  if (pathname.startsWith("/login")) return <>{children}</>;
  if (!checked) return <div className="desk-surface min-h-screen p-8 font-mono text-sm text-postmark">Opening the post office…</div>;

  return (
    <div className="desk-surface desk-vignette flex min-h-screen">
      {/* desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 overflow-y-auto bg-postalnavy bg-[radial-gradient(ellipse_at_top,rgba(201,169,120,0.12),transparent_60%)] md:block">
        <NavList user={user} />
      </aside>
      {/* mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 overflow-y-auto bg-postalnavy shadow-paperlift">
            <NavList user={user} onNav={() => setOpen(false)} />
          </aside>
        </div>
      )}
      {/* mobile mail-slot nav */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t-4 border-double border-kraft bg-postalnavy px-2 py-1 md:hidden" aria-label="Primary">
        {[
          { href: "/applications", label: "Counter", icon: "🏤" },
          { href: "/tracker", label: "Holes", icon: "🗂️" },
          { href: "/resume", label: "Files", icon: "🗄️" },
        ].map((l) => (
          <Link key={l.href} href={l.href} className="flex min-h-[48px] min-w-[64px] flex-col items-center justify-center rounded-md text-paper/80">
            <span className="text-xl" aria-hidden="true">{l.icon}</span>
            <span className="font-mono text-[10px] uppercase">{l.label}</span>
          </Link>
        ))}
        <button onClick={() => setOpen(true)} className="flex min-h-[48px] min-w-[64px] flex-col items-center justify-center rounded-md text-paper/80" aria-label="Open full menu">
          <span className="text-xl" aria-hidden="true">☰</span>
          <span className="font-mono text-[10px] uppercase">Menu</span>
        </button>
      </nav>
      <div className="min-w-0 flex-1">
        <div className="sticky top-0 z-30 border-b border-kraft/40 bg-paper/90 px-4 py-2.5 backdrop-blur md:hidden">
          <button onClick={() => setOpen(true)} className="min-h-[44px] rounded-md border border-kraft px-3 font-mono text-sm font-bold text-postalnavy">
            ☰ thedaaakhouse
          </button>
        </div>
        <main className="mx-auto max-w-6xl px-4 pb-24 pt-6 md:px-8 md:pb-10">
          <div key={pathname} className="sheet-in">{children}</div>
        </main>
      </div>
    </div>
  );
}

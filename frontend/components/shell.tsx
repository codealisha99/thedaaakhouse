"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, token } from "@/lib/api";

const NAV: { section: string; links: { href: string; label: string }[] }[] = [
  {
    section: "Applications",
    links: [
      { href: "/applications", label: "Overview" },
      { href: "/applications/new", label: "Job Analyzer" },
      { href: "/applications/company", label: "Company Research" },
      { href: "/applications/interview", label: "Interview Prep" },
    ],
  },
  {
    section: "Job Tracker",
    links: [{ href: "/tracker", label: "Tracker" }],
  },
  {
    section: "Resume",
    links: [
      { href: "/resume", label: "My Resumes" },
      { href: "/resume/tailor", label: "Tailor Resume" },
      { href: "/resume/ats", label: "ATS Checker" },
    ],
  },
];

function Wordmark() {
  return (
    <Link href="/tracker" className="focus-term flex items-center gap-2">
      <svg width="26" height="20" viewBox="0 0 26 20" fill="none" aria-hidden="true">
        <rect x="1" y="1" width="24" height="18" stroke="currentColor" strokeWidth="2" />
        <path d="M1 3 L13 12 L25 3" stroke="currentColor" strokeWidth="2" />
      </svg>
      <span className="font-pixel text-xl font-bold uppercase leading-none">thedaaakhouse</span>
    </Link>
  );
}

function NavList({ user, onNav }: { user: string | null; onNav?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const on = localStorage.getItem("tdh-dark") === "1";
    setDark(on);
    document.documentElement.classList.toggle("dark", on);
  }, []);
  function toggleDark() {
    setDark((v) => {
      document.documentElement.classList.toggle("dark", !v);
      try { localStorage.setItem("tdh-dark", !v ? "1" : "0"); } catch { /* noop */ }
      return !v;
    });
  }

  return (
    <div className="flex h-full flex-col">
      <div className="px-4 pb-2 pt-5">
        <Wordmark />
        <p className="mt-1 font-mono text-xs text-muted">Job-search operating system</p>
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-2 py-3">
        {NAV.map((group) => (
          <div key={group.section}>
            <p className="px-2 pb-1 font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
              {group.section}
            </p>
            <ul className="space-y-0.5">
              {group.links.map((l) => {
                const active = pathname === l.href || (l.href !== "/tracker" && pathname.startsWith(l.href + "/"));
                return (
                  <li key={l.href}>
                    <Link
                      href={l.href}
                      onClick={onNav}
                      className={`focus-term flex min-h-[44px] items-center border-l-[3px] px-3 font-mono text-sm ${
                        active
                          ? "border-accent bg-green font-bold text-surface"
                          : "border-transparent text-ink hover:bg-sage"
                      }`}
                    >
                      {l.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t-2 border-green p-3">
        {user ? (
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-mono text-xs text-muted">{user}</span>
            <button
              onClick={() => { token.clear(); router.push("/login"); }}
              className="focus-term min-h-[44px] border-2 border-green bg-surface px-2.5 font-mono text-xs font-bold uppercase"
            >
              Log out
            </button>
          </div>
        ) : (
          <Link href="/login" onClick={onNav} className="font-mono text-sm font-bold uppercase underline hover:no-underline">
            Log in
          </Link>
        )}
        <button
          onClick={toggleDark}
          className="focus-term mt-2 min-h-[44px] w-full border-2 border-green bg-surface px-2 font-mono text-xs font-bold uppercase"
          aria-pressed={dark}
        >
          {dark ? "Light mode" : "Dark mode"}
        </button>
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
  if (!checked) return <div className="p-8 font-mono text-sm text-muted">LOADING<span className="cursor-blink font-bold">▊</span></div>;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-[260px] shrink-0 overflow-y-auto border-r-2 border-green md:block">
        <NavList user={user} />
      </aside>
      {/* mobile top bar + drawer */}
      <div className="sticky top-0 z-30 flex w-full items-center justify-between border-b-2 border-green px-4 py-2 md:hidden">
        <Wordmark />
        <button onClick={() => setOpen(true)} className="focus-term min-h-[44px] min-w-[44px] border-2 border-green bg-surface px-3 font-mono text-sm font-bold" aria-label="Open menu">
          [=]
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 overflow-y-auto border-r-2 border-green bg-bg shadow-hard">
            <NavList user={user} onNav={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <div className="min-w-0 flex-1">
        <main className="mx-auto max-w-6xl px-4 py-6 md:px-8">
          <div key={pathname} className="page-fade">{children}</div>
        </main>
      </div>
    </div>
  );
}

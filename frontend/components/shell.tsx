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

function SidebarBody({ user, onNav }: { user: string | null; onNav?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  return (
    <div className="flex h-full flex-col">
      <Link href="/tracker" onClick={onNav} className="px-5 pb-2 pt-6">
        <h1 className="text-lg font-bold tracking-tight">thedaaakhouse</h1>
        <p className="text-[11px] text-slate-500">Job-search operating system</p>
      </Link>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {NAV.map((group) => (
          <div key={group.section}>
            <p className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
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
                      className={`block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                        active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
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
      <div className="border-t p-4 text-sm">
        {user ? (
          <div className="flex items-center justify-between">
            <span className="truncate text-slate-600">{user}</span>
            <button
              onClick={() => { token.clear(); router.push("/login"); }}
              className="rounded-lg border px-2.5 py-1 text-xs font-medium hover:bg-slate-100"
            >
              Log out
            </button>
          </div>
        ) : (
          <Link href="/login" onClick={onNav} className="text-violet-700 hover:underline">Log in</Link>
        )}
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
  if (!checked) return <div className="p-8 text-sm text-slate-500">Loading…</div>;

  return (
    <div className="flex min-h-screen">
      {/* desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r bg-white md:block">
        <SidebarBody user={user} />
      </aside>
      {/* mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-white shadow-xl">
            <SidebarBody user={user} onNav={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="sticky top-0 z-30 border-b bg-white/90 px-4 py-2.5 backdrop-blur md:hidden">
          <button onClick={() => setOpen(true)} className="rounded-lg border px-3 py-1.5 text-sm font-medium">
            ☰ thedaaakhouse
          </button>
        </div>
        <main className="mx-auto max-w-6xl px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}

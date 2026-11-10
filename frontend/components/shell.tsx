"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, token } from "@/lib/api";
import { useAppAuth } from "@/components/auth-provider";
import { Wordmark } from "./brand";
import { CommandPalette } from "./command-palette";
import { Kbd, Skeleton, cx } from "./ds";
import { NAV, SETTINGS_NAV, activeHref, type NavItem } from "./nav";

const isPublic = (p: string) => p === "/" || p.startsWith("/login") || p.startsWith("/sign-up");

export function useTheme() {
  const [dark, setDark] = useState(false);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);
  function toggle() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("tdh-dark", next ? "1" : "0"); } catch { /* private mode */ }
    setDark(next);
  }
  return { dark, toggle };
}

export function ThemeToggle({ className }: { className?: string }) {
  const { dark, toggle } = useTheme();
  return (
    <button onClick={toggle} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className={cx("inline-flex size-9 items-center justify-center rounded-md text-ink-3 transition-colors hover:bg-sunken hover:text-ink", className)}>
      {dark ? (
        <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
      ) : (
        <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" /></svg>
      )}
    </button>
  );
}

function NavLink({ item, active, onNav }: { item: NavItem; active: boolean; onNav?: () => void }) {
  return (
    <Link href={item.href} onClick={onNav} aria-current={active ? "page" : undefined}
      className={cx(
        "group relative flex h-8 items-center rounded-md px-3 text-[14px] transition-colors duration-[var(--dur-1)]",
        active ? "bg-surface font-medium text-ink shadow-1" : "text-ink-2 hover:bg-sunken hover:text-ink",
      )}>
      <span aria-hidden="true" className={cx("absolute -left-3 h-4 w-[3px] rounded-r-full bg-accent transition-transform duration-[var(--dur-2)] ease-[var(--ease-out)]", active ? "scale-y-100" : "scale-y-0")} />
      {item.label}
    </Link>
  );
}

function Sidebar({ user, onNav, onSearch }: { user: string | null; onNav?: () => void; onSearch: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const auth = useAppAuth();
  const active = activeHref(pathname);

  async function logout() {
    if (auth.clerkEnabled) await auth.signOut();
    else token.clear();
    router.push("/login");
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <Wordmark onClick={onNav} />
      </div>
      <div className="px-3 pb-2">
        <button onClick={onSearch}
          className="flex h-9 w-full items-center gap-2 rounded-md border border-line bg-surface px-3 text-[13px] text-ink-3 shadow-1 transition-colors hover:border-line-strong hover:text-ink-2">
          <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          Jump to…
          <span className="ml-auto flex gap-0.5"><Kbd>⌘</Kbd><Kbd>K</Kbd></span>
        </button>
      </div>
      <nav aria-label="Main" className="scroll-quiet flex-1 space-y-4 overflow-y-auto px-3 py-2">
        {NAV.map((g) => (
          <div key={g.section}>
            <p className="px-3 pb-1.5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-3">{g.section}</p>
            <ul className="space-y-px">
              {g.links.map((l) => <li key={l.href}><NavLink item={l} active={active === l.href} onNav={onNav} /></li>)}
            </ul>
          </div>
        ))}
        <div className="border-t border-line pt-3">
          <p className="px-3 pb-1.5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-3">Settings</p>
          <ul className="space-y-px">
            {SETTINGS_NAV.map((l) => <li key={l.href}><NavLink item={l} active={active === l.href} onNav={onNav} /></li>)}
          </ul>
        </div>
      </nav>
      <div className="flex items-center gap-2 border-t border-line px-4 py-2.5">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand/12 font-mono text-[12px] font-medium uppercase text-brand" aria-hidden="true">
          {(user ?? "?").slice(0, 1)}
        </span>
        <span className="min-w-0 flex-1 truncate text-[13px] text-ink-2">{user ?? "Not signed in"}</span>
        <ThemeToggle />
        <button onClick={logout} className="h-8 rounded-md px-2 text-[13px] text-ink-3 transition-colors hover:bg-sunken hover:text-ink">Log out</button>
      </div>
    </div>
  );
}

function MobileDrawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.querySelector<HTMLElement>("a,button")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = prev; window.removeEventListener("keydown", onKey); };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
      <div className="overlay-in absolute inset-0 bg-ink/30" onClick={onClose} />
      <div ref={panel} className="drawer-in absolute inset-y-0 left-0 w-[min(86vw,300px)] bg-bg shadow-pop">{children}</div>
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const auth = useAppAuth();
  const [user, setUser] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [palette, setPalette] = useState(false);
  const publicRoute = isPublic(pathname);

  useEffect(() => {
    if (publicRoute) { setChecked(true); return; }
    if (auth.clerkEnabled) {
      if (!auth.loaded) { setChecked(false); return; }
      if (!auth.signedIn) { router.replace("/login"); return; }
      api.me()
        .then(() => { setUser(auth.displayName || "Account"); setChecked(true); })
        .catch(() => { setUser(null); setChecked(true); });
      return;
    }
    if (!token.get()) { router.replace("/login"); return; }
    api.me()
      .then((me) => { setUser(me.username); setChecked(true); })
      .catch(() => { setUser(null); setChecked(true); });
  }, [pathname, publicRoute, router, auth.clerkEnabled, auth.loaded, auth.signedIn, auth.displayName]);

  useEffect(() => {
    if (publicRoute) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((v) => !v); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [publicRoute]);

  useEffect(() => setDrawer(false), [pathname]);

  if (publicRoute) return <>{children}</>;

  const closeDrawer = () => setDrawer(false);
  const openSearch = () => { setDrawer(false); setPalette(true); };

  return (
    <div className="min-h-screen lg:flex">
      <a href="#main" className="sr-only z-50 rounded-md bg-ink px-3 py-2 text-on-ink focus:not-sr-only focus:fixed focus:top-3 focus:left-3">Skip to content</a>
      <aside className="sticky top-0 hidden h-screen w-[256px] shrink-0 border-r border-line lg:block">
        <Sidebar user={user} onSearch={openSearch} />
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-bg/85 px-4 backdrop-blur-md lg:hidden">
        <Wordmark />
        <div className="flex items-center gap-1">
          <button onClick={openSearch} aria-label="Jump to page" className="inline-flex size-10 items-center justify-center rounded-md text-ink-2 hover:bg-sunken">
            <svg className="size-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          </button>
          <button onClick={() => setDrawer(true)} aria-label="Open menu" aria-expanded={drawer} className="inline-flex size-10 items-center justify-center rounded-md text-ink-2 hover:bg-sunken">
            <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h10" /></svg>
          </button>
        </div>
      </header>
      <MobileDrawer open={drawer} onClose={closeDrawer}>
        <Sidebar user={user} onNav={closeDrawer} onSearch={openSearch} />
      </MobileDrawer>

      <main id="main" className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-[1180px] px-4 py-8 sm:px-6 lg:px-10 lg:py-10">
          {checked ? (
            <div key={pathname} className="rise-in">{children}</div>
          ) : (
            <div role="status" aria-label="Loading workspace" className="space-y-4">
              <Skeleton className="h-10 w-64" />
              <Skeleton className="h-4 w-96 max-w-full" />
              <Skeleton className="mt-8 h-40 w-full" />
            </div>
          )}
        </div>
      </main>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  );
}

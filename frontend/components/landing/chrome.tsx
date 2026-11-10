"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { token } from "@/lib/api";
import { useAppAuth } from "@/components/auth-provider";
import { Mark } from "@/components/brand";
import { LinkButton, cx } from "@/components/ds";
import { ThemeToggle } from "@/components/shell";

const LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#principles", label: "Principles" },
  { href: "#faq", label: "FAQ" },
];

/** True when a session exists (local token or Clerk). */
export function useSignedIn() {
  const auth = useAppAuth();
  const [local, setLocal] = useState(false);
  useEffect(() => setLocal(Boolean(token.get())), []);
  return auth.clerkEnabled ? auth.signedIn : local;
}

export function PrimaryCta({ size = "lg", label = "Start tracking" }: { size?: "md" | "lg"; label?: string }) {
  const signedIn = useSignedIn();
  return <LinkButton href={signedIn ? "/applications" : "/login"} variant="accent" size={size}>{signedIn ? "Open your workspace" : label}</LinkButton>;
}

export function LandingHeader() {
  const signedIn = useSignedIn();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 8);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <header className={cx("sticky top-0 z-40 border-b transition-[background-color,border-color] duration-[var(--dur-2)]",
      scrolled ? "border-line bg-bg/85 backdrop-blur-md" : "border-transparent")}>
      <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between gap-4 px-5 sm:px-8">
        <Link href="/" className="inline-flex items-center gap-2.5 rounded-md" aria-label="thedaaakhouse home">
          <Mark />
          <span className="text-[15px] font-semibold tracking-[-0.02em]">thedaaak<span className="text-ink-3">house</span></span>
        </Link>
        <nav aria-label="Sections" className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => <a key={l.href} href={l.href} className="rounded-md px-3 py-2 text-sm text-ink-2 transition-colors hover:text-ink">{l.label}</a>)}
        </nav>
        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          {!signedIn && <Link href="/login" className="hidden rounded-md px-3 py-2 text-sm text-ink-2 hover:text-ink sm:block">Log in</Link>}
          <LinkButton href={signedIn ? "/applications" : "/login"} variant="primary" size="sm">{signedIn ? "Open workspace" : "Get started"}</LinkButton>
        </div>
      </div>
    </header>
  );
}

/** Adds .is-visible to [data-reveal] elements as they enter the viewport. */
export function Reveal() {
  useEffect(() => {
    const els = document.querySelectorAll<HTMLElement>("[data-reveal]");
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add("is-visible"); io.unobserve(e.target); }
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.12 });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return null;
}

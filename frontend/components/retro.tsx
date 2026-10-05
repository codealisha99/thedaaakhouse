"use client";

import Link from "next/link";
import { useState } from "react";

/* ---------- Button ---------- */
export function Btn({ children, onClick, href, variant = "primary", disabled, type }: {
  children: React.ReactNode;
  onClick?: () => void;
  href?: string;
  variant?: "primary" | "secondary";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const cls = `btn-hard focus-term inline-flex min-h-[44px] items-center justify-center gap-2 border-2 border-green px-4 font-mono text-sm font-bold uppercase tracking-wide disabled:opacity-50 ${
    variant === "primary" ? "bg-accent text-ink shadow-hard" : "bg-surface text-ink shadow-hard"
  }`;
  if (href) return <a href={href} className={cls}>{children}</a>;
  return <button type={type ?? "button"} disabled={disabled} onClick={onClick} className={cls}>{children}</button>;
}

/* ---------- Card ---------- */
export function Card({ children, className = "", lift = false }: {
  children: React.ReactNode; className?: string; lift?: boolean;
}) {
  return (
    <div className={`border-2 border-green bg-surface shadow-hard ${lift ? "card-lift" : ""} ${className}`}>
      {children}
    </div>
  );
}

/* ---------- Chip ---------- */
export function Chip({ children, tone = "default", dashed = false }: {
  children: React.ReactNode;
  tone?: "default" | "sage" | "mustard" | "green" | "green-deep" | "danger" | "grey";
  dashed?: boolean;
}) {
  const tones: Record<string, string> = {
    default: "bg-surface text-ink",
    sage: "bg-sage text-ink",
    mustard: "bg-accent/25 text-ink",
    green: "bg-green text-surface",
    "green-deep": "bg-green-deep text-surface",
    danger: "bg-danger/10 text-danger",
    grey: "bg-surface text-muted",
  };
  return (
    <span className={`inline-block border-[1.5px] border-green px-2 py-0.5 font-mono text-xs shadow-hardsm ${tones[tone]} ${dashed ? "border-dashed" : ""}`}>
      {children}
    </span>
  );
}

/* ---------- StatCard ---------- */
export function StatCard({ n, label, href }: { n: number; label: string; href?: string }) {
  const inner = (
    <>
      <p className="font-pixel text-5xl font-bold uppercase leading-none text-green">{n}</p>
      <p className="mt-2 font-mono text-xs uppercase tracking-widest text-muted">{label}</p>
    </>
  );
  return (
    <Card lift className="bg-sage p-4 text-left">
      {href ? <Link href={href} className="focus-term block">{inner}</Link> : inner}
    </Card>
  );
}

/* ---------- PageHeader ---------- */
export function PageHeader({ title, subtitle, action }: {
  title: string; subtitle: string; action?: React.ReactNode;
}) {
  return (
    <div className="page-fade">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-pixel text-3xl font-bold uppercase leading-tight text-green md:text-4xl">{title}</h2>
          <p className="mt-1 font-mono text-sm text-muted">{subtitle}</p>
        </div>
        {action}
      </div>
      <div className="mt-3 h-0.5 bg-green" aria-hidden="true" />
    </div>
  );
}

/* ---------- Skeleton (blinking cursor) ---------- */
export function Skeleton({ label = "LOADING" }: { label?: string }) {
  return (
    <Card className="p-6">
      <p className="font-mono text-sm text-muted">
        {label} <span className="cursor-blink font-bold text-green">▊</span>
      </p>
    </Card>
  );
}

/* ---------- EmptyState ---------- */
export function EmptyState({ title, body, action }: {
  title: string; body: string; action?: React.ReactNode;
}) {
  return (
    <Card className="mx-auto max-w-[560px] p-8 text-center">
      <h3 className="font-pixel text-2xl font-bold uppercase text-green">{title}</h3>
      <p className="mt-2 font-mono text-sm text-muted">{body}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </Card>
  );
}

/* ---------- ErrorCard ---------- */
export function ErrorCard({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const [failed, setFailed] = useState(false);
  const [trying, setTrying] = useState(false);
  // Strip raw status prefixes ("0: ...") and collapse doubled sentences.
  const clean = message
    .replace(/^\d+:\s*/, "")
    .replace(/Check that the API.*$/i, "")
    .trim();
  return (
    <Card className={`mx-auto max-w-[560px] p-8 text-center ${failed ? "shake-once" : ""}`}>
      <h3 className="font-pixel text-2xl font-bold uppercase text-green">Can&apos;t reach the server</h3>
      <p className="mt-3 font-mono text-sm leading-relaxed">
        Backend at http://127.0.0.1:8001 isn&apos;t responding. Check that the API is running, then retry.
      </p>
      <details className="mx-auto mt-2 max-w-full text-left">
        <summary className="cursor-pointer font-mono text-xs uppercase text-muted hover:underline">Tech details</summary>
        <p className="mt-1 break-words font-mono text-xs text-muted">{clean || message}</p>
      </details>
      {onRetry && (
        <div className="mt-4 flex justify-center">
          <button
            onClick={() => {
              setTrying(true); setFailed(false);
              try { onRetry(); } finally {
                setTimeout(() => { setTrying(false); setFailed(true); }, 6000);
              }
            }}
            className="btn-hard focus-term inline-flex min-h-[44px] items-center border-2 border-green bg-surface px-5 font-mono text-sm font-bold uppercase shadow-hard"
          >
            {trying ? <>Retry<span className="cursor-blink ml-1 font-bold text-green">▊</span></> : "Retry"}
          </button>
        </div>
      )}
    </Card>
  );
}

/* ---------- Field + inputs ---------- */
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-xs font-bold uppercase tracking-widest text-muted">{label}</span>
      {children}
    </label>
  );
}

export const inputCls =
  "focus-term w-full border-2 border-green bg-surface px-3 py-2 font-mono text-sm text-ink min-h-[44px]";

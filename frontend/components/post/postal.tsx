"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { rotateFor } from "./journey";
import { useTheme } from "./theme";

/* ----------------Letterhead ---------------- */
export function Letterhead({ title, subtitle, action }: {
  title: string; subtitle: string; action?: React.ReactNode;
}) {
  return (
    <div className="sheet-in">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-serif text-3xl font-bold tracking-tight text-postalnavy md:text-4xl">{title}</h2>
          <p className="mt-1 font-mono text-sm uppercase tracking-[0.18em] text-postmark">{subtitle}</p>
        </div>
        {action}
      </div>
      <div className="airmail mt-3 h-2.5 rounded-sm" aria-hidden="true" />
    </div>
  );
}

/* ---------------- PaperCard ---------------- */
export function PaperCard({ id, children, className = "", tilt = true }: {
  id?: string; children: React.ReactNode; className?: string; tilt?: boolean;
}) {
  const reduce = useReducedMotion();
  const rot = tilt && !reduce ? rotateFor(id ?? Math.random().toString()) : "0deg";
  return (
    <motion.div
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 14, rotate: 0.6 }}
      animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0, rotate: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      whileHover={reduce ? undefined : { y: -4, rotate: 0, boxShadow: "0 2px 4px rgba(26,26,26,.18), 0 12px 28px rgba(26,26,26,.22)" }}
      className={`postal-rot paper-keep rounded-md border border-kraft/60 bg-envelope shadow-paper ${className}`}
      style={{ ["--card-rot" as string]: rot, transform: `rotate(${rot})` }}
    >
      {children}
    </motion.div>
  );
}

/* ---------------- LabelTape (section headers) ---------------- */
export function LabelTape({ children }: { children: React.ReactNode }) {
  return (
    <p className="inline-block -rotate-1 bg-postalnavy px-2.5 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.22em] text-paper shadow-stamp">
      {children}
    </p>
  );
}

/* ---------------- StickyNote ---------------- */
export function StickyNote({ children, color = "#FFF3B0" }: { children: React.ReactNode; color?: string }) {
  return (
    <div className="postal-rot paper-keep relative rounded-sm p-3 pt-5 font-hand text-lg leading-snug text-ink shadow-paper" style={{ background: color, transform: "rotate(-1deg)" }}>
      <div className="washi absolute -top-2 left-1/2 h-5 w-16 -translate-x-1/2 -rotate-2 rounded-[1px]" aria-hidden="true" />
      {children}
    </div>
  );
}

/* ---------------- WaxSealButton ("Post a new letter") ---------------- */
export function WaxSealButton({ children, onClick, href }: {
  children: React.ReactNode; onClick?: () => void; href?: string;
}) {
  const { thunk } = useTheme();
  const cls = "group inline-flex items-center gap-2.5 rounded-full bg-postred py-0 pl-1.5 pr-5 font-serif text-base font-bold text-envelope shadow-paper transition-all hover:bg-postreddark active:translate-y-0.5 active:shadow-none";
  const seal = (
    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-postreddark text-lg ring-2 ring-envelope/70 transition-transform group-active:scale-90" aria-hidden="true">
      ✉
    </span>
  );
  const inner = <>{seal}<span className="py-2">{children}</span></>;
  if (href) return <a href={href} className={cls} onClick={thunk}>{inner}</a>;
  return <button onClick={() => { thunk(); onClick?.(); }} className={cls}>{inner}</button>;
}

/* ---------------- RubberStamp (animated status) ---------------- */
export function RubberStamp({ text, color = "#C8102E", size = "md" }: {
  text: string; color?: string; size?: "sm" | "md" | "lg";
}) {
  const { thunk } = useTheme();
  const [shake, setShake] = useState(false);
  const sizes = { sm: "px-2 py-0.5 text-[11px]", md: "px-3 py-1 text-sm", lg: "px-5 py-2 text-2xl" }[size];
  return (
    <span className={shake ? "shake-on-stamp inline-block" : "inline-block"}>
      <span
        onAnimationEnd={() => setShake(false)}
        onAnimationStart={() => { setShake(true); thunk(); }}
        className={`stamp-in ink-rough inline-block rounded-[4px] border-[3px] font-mono font-bold uppercase tracking-[0.14em] ${sizes}`}
        style={{ ["--stamp-rot" as string]: "-8deg", color, borderColor: color, background: `${color}14` }}
      >
        {text}
      </span>
    </span>
  );
}

/* ---------------- Postmark (circular city+date) ---------------- */
export function Postmark({ city, date, className = "" }: { city: string; date?: string; className?: string }) {
  const d = date ?? new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }).toUpperCase();
  return (
    <div aria-hidden="true" className={`pointer-events-none flex h-20 w-20 rotate-[-12deg] items-center justify-center rounded-full border-2 border-postmark/70 text-center opacity-60 mix-blend-multiply ${className}`}>
      <div className="font-mono text-[8px] font-bold uppercase leading-tight tracking-widest text-postmark">
        {city.slice(0, 12)}<br />{d}
      </div>
    </div>
  );
}

/* ---------------- Stamp badge (perforated status) ---------------- */
export function StampBadge({ text, color = "#5B3A8C", denom }: { text: string; color?: string; denom?: string }) {
  return (
    <span className="perforated inline-flex items-center gap-1.5 px-2.5 py-1 font-mono text-[11px] font-bold uppercase tracking-widest text-envelope" style={{ background: color }}>
      ✦ {text}
      {denom && <span className="opacity-80">{denom}</span>}
    </span>
  );
}

/* ---------------- TypedMemo (telegram analysis) ---------------- */
export function TypedMemo({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="paper-keep rounded-sm border border-kraft/60 bg-envelope p-5 shadow-paper">
      <p className="border-b-2 border-dashed border-postmark/40 pb-2 font-mono text-xs font-bold uppercase tracking-[0.25em] text-postmark">
        ▚ {title} ▞
      </p>
      <div className="pt-3 font-mono text-sm leading-relaxed text-ink">{children}</div>
    </div>
  );
}

/* ---------------- TruckLoader (never a spinner) ---------------- */
export function TruckLoader({ label = "Sorting the mail…" }: { label?: string }) {
  return (
    <div className="relative overflow-hidden rounded-md border border-kraft/50 bg-envelope py-6" role="status" aria-label={label}>
      <div className="route-line absolute bottom-4 left-4 right-4" aria-hidden="true" />
      <div className="truck-roll absolute bottom-5 text-2xl" aria-hidden="true">
        🚚<span className="truck-wheel" />
      </div>
      <p className="text-center font-mono text-xs uppercase tracking-[0.2em] text-postmark">{label}</p>
    </div>
  );
}

/* ---------------- EmptyPost (empty pigeonhole) ---------------- */
export function EmptyPost({ children }: { children?: React.ReactNode }) {
  return (
    <div className="rounded-md border-2 border-dashed border-kraft bg-envelope/60 p-8 text-center shadow-inner">
      <p className="text-4xl" aria-hidden="true">🕸️</p>
      <p className="mt-2 font-hand text-2xl text-postmark">
        {children ?? <>No letters yet. Post your first application.</>}
      </p>
    </div>
  );
}

/* ---------------- ErrorNotice (service disruption) ---------------- */
export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const [state, setState] = useState<"idle" | "trying" | "failed">("idle");
  return (
    <div className="paper-keep relative mx-auto max-w-lg rotate-[-0.5deg] rounded-sm border border-kraft bg-envelope p-6 text-center shadow-paperlift">
      <div className="washi absolute -top-2.5 left-8 h-6 w-20 -rotate-6" aria-hidden="true" />
      <div className="washi absolute -top-2.5 right-8 h-6 w-20 rotate-3" aria-hidden="true" />
      <p className="font-mono text-[11px] font-bold uppercase tracking-[0.25em] text-postred">Service disruption notice</p>
      <h3 className="mt-1 font-serif text-3xl font-bold text-postalnavy">The mail truck is stuck.</h3>
      <p className="my-3 text-4xl" aria-hidden="true">🚚💨</p>
      <div className="rounded-sm border border-dashed border-postmark/50 bg-paper p-3 text-left font-mono text-xs leading-relaxed text-ink">
        <span className="font-bold">TELEGRAM — </span>{message}
      </div>
      {onRetry && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <button
            onClick={() => { setState("trying"); onRetry(); setTimeout(() => setState((s) => (s === "trying" ? "failed" : s)), 4000); }}
            className="rounded-[4px] border-[3px] border-postred px-4 py-1.5 font-mono text-sm font-bold uppercase tracking-[0.14em] text-postred transition-transform active:scale-95"
          >
            {state === "trying" ? "Trying…" : "Try again"}
          </button>
          {state === "failed" && <RubberStamp text="Still closed" color="#5C6B7A" size="sm" />}
        </div>
      )}
    </div>
  );
}

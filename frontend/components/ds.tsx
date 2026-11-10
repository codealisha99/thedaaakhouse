"use client";

/**
 * Registered Post design system primitives.
 * Tokens live in app/globals.css; rationale in docs/design/design-direction.md.
 */
import Link from "next/link";
import { useId, useState } from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export { cx };

/* ---------- Button ---------- */
type Variant = "accent" | "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANT: Record<Variant, string> = {
  accent: "bg-accent text-on-accent hover:bg-accent-hover shadow-1",
  primary: "bg-ink text-on-ink hover:bg-ink/88 shadow-1",
  secondary: "border border-line-strong bg-surface text-ink hover:border-ink-3 hover:bg-sunken/60 shadow-1",
  ghost: "text-ink-2 hover:bg-sunken hover:text-ink",
  danger: "border border-bad/40 bg-surface text-bad hover:bg-bad/8",
};
const SIZE: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-[15px] gap-2",
};

export function buttonCls(variant: Variant = "primary", size: Size = "md", extra = "") {
  return cx(
    "inline-flex shrink-0 select-none items-center justify-center rounded-md font-medium whitespace-nowrap",
    "transition-[background-color,border-color,color,transform,box-shadow] duration-[var(--dur-1)] ease-[var(--ease-out)]",
    "active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45",
    VARIANT[variant], SIZE[size], extra,
  );
}

export function Button({ variant = "primary", size = "md", busy, className, children, type = "button", ...rest }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; busy?: boolean }) {
  return (
    <button type={type} aria-busy={busy || undefined} disabled={busy || rest.disabled} className={buttonCls(variant, size, className)} {...rest}>
      {busy && <Spinner />}
      {children}
    </button>
  );
}

export function LinkButton({ href, variant = "primary", size = "md", className, children, external }: {
  href: string; variant?: Variant; size?: Size; className?: string; children: React.ReactNode; external?: boolean;
}) {
  if (external) return <a href={href} target="_blank" rel="noreferrer" className={buttonCls(variant, size, className)}>{children}</a>;
  return <Link href={href} className={buttonCls(variant, size, className)}>{children}</Link>;
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg className={cx("size-4 animate-spin", className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity=".25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/* ---------- Surfaces ---------- */
export function Panel({ children, className, as: Tag = "section", padded = true, ...rest }:
  React.HTMLAttributes<HTMLElement> & { as?: "section" | "div" | "article" | "aside"; padded?: boolean }) {
  return (
    <Tag className={cx("rounded-[10px] border border-line bg-surface shadow-1", padded && "p-5", className)} {...rest}>
      {children}
    </Tag>
  );
}

export function PanelHeader({ title, meta, action }: { title: React.ReactNode; meta?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h3 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{title}</h3>
        {meta && <p className="mt-0.5 text-[13px] text-ink-3">{meta}</p>}
      </div>
      {action}
    </div>
  );
}

/* ---------- Page header ---------- */
export function PageHeader({ eyebrow, title, description, actions }: {
  eyebrow?: string; title: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode;
}) {
  return (
    <header className="rise-in mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-line pb-6">
      <div className="min-w-0 max-w-2xl">
        {eyebrow && <Label className="mb-2 block">{eyebrow}</Label>}
        <h1 className="font-display text-[40px] leading-[1.02] tracking-[-0.01em] text-ink md:text-[46px]">{title}</h1>
        {description && <p className="mt-3 text-[15px] leading-relaxed text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Label({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cx("font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-3", className)}>{children}</span>;
}

/* ---------- Badges ---------- */
export type Tone = "neutral" | "brand" | "accent" | "ok" | "warn" | "bad";
const TONE: Record<Tone, string> = {
  neutral: "border-line-strong/70 bg-sunken text-ink-2",
  brand: "border-brand/25 bg-brand/8 text-brand",
  accent: "border-accent/30 bg-accent/8 text-accent",
  ok: "border-ok/30 bg-ok/8 text-ok",
  warn: "border-warn/30 bg-warn/10 text-warn",
  bad: "border-bad/30 bg-bad/8 text-bad",
};
export function Badge({ tone = "neutral", children, className, dot }: { tone?: Tone; children: React.ReactNode; className?: string; dot?: boolean }) {
  return (
    <span className={cx("inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 text-xs font-medium", TONE[tone], className)}>
      {dot && <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />}
      {children}
    </span>
  );
}

/** Small skill / keyword token. */
export function Tag({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "ok" | "bad" }) {
  const t = { neutral: "bg-sunken text-ink-2", ok: "bg-ok/10 text-ok", bad: "bg-bad/8 text-bad" }[tone];
  return <span className={cx("inline-flex items-center rounded-[5px] px-2 py-0.5 font-mono text-[12px]", t)}>{children}</span>;
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-line-strong bg-surface px-1 font-mono text-[11px] text-ink-3">{children}</kbd>;
}

/** Tracking number shown on every application. */
export function TrackingId({ id, className }: { id: string; className?: string }) {
  return <span className={cx("font-mono text-[12px] tracking-wide text-ink-3", className)}>DH-{id.replace(/-/g, "").slice(0, 6).toUpperCase()}</span>;
}

/* ---------- Score meter ---------- */
export function scoreTone(score: number | null | undefined): Tone {
  if (score == null) return "neutral";
  return score >= 75 ? "ok" : score >= 50 ? "warn" : "bad";
}
export function Meter({ value, max = 100, tone, label, className }: { value: number; max?: number; tone?: Tone; label?: string; className?: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const t = tone ?? scoreTone(pct);
  const bar = { neutral: "bg-ink-3", brand: "bg-brand", accent: "bg-accent", ok: "bg-ok", warn: "bg-warn", bad: "bg-bad" }[t];
  return (
    <div className={cx("h-1.5 w-full overflow-hidden rounded-full bg-sunken", className)} role="meter" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={max} aria-label={label}>
      <div className={cx("h-full rounded-full transition-[width] duration-700 ease-[var(--ease-out)]", bar)} style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Big numeric score with its meter. */
export function Score({ value, label, caption }: { value: number | null; label: string; caption?: React.ReactNode }) {
  return (
    <div>
      <Label>{label}</Label>
      <p className="mt-1 font-mono text-4xl font-medium tabular tracking-tight text-ink">
        {value == null ? "—" : Math.round(value)}
        {value != null && <span className="ml-1 text-base text-ink-3">/100</span>}
      </p>
      {value != null && <Meter value={value} className="mt-3" label={label} />}
      {caption && <p className="mt-2 text-[13px] text-ink-3">{caption}</p>}
    </div>
  );
}

/* ---------- Forms ---------- */
export const inputCls = "control control-input";
export const selectCls = "control control-select";
export const textareaCls = "control control-textarea";

export function Field({ label, hint, error, children, className }: {
  label: string; hint?: React.ReactNode; error?: string | null; children: React.ReactNode; className?: string;
}) {
  return (
    <label className={cx("block", className)}>
      <span className="mb-1.5 block text-[13px] font-medium text-ink-2">{label}</span>
      {children}
      {error ? <span className="mt-1.5 block text-[13px] text-bad" role="alert">{error}</span>
        : hint ? <span className="mt-1.5 block text-[12px] text-ink-3">{hint}</span> : null}
    </label>
  );
}

/* ---------- Tabs ---------- */
export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: readonly T[]; value: T; onChange: (t: T) => void; label: string }) {
  const id = useId();
  function onKey(e: React.KeyboardEvent, i: number) {
    const dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!dir) return;
    e.preventDefault();
    const next = tabs[(i + dir + tabs.length) % tabs.length];
    onChange(next);
    document.getElementById(`${id}-${next}`)?.focus();
  }
  return (
    <div role="tablist" aria-label={label} className="scroll-quiet -mx-1 flex gap-1 overflow-x-auto border-b border-line px-1">
      {tabs.map((t, i) => {
        const on = t === value;
        return (
          <button
            key={t} id={`${id}-${t}`} role="tab" aria-selected={on} tabIndex={on ? 0 : -1}
            onClick={() => onChange(t)} onKeyDown={(e) => onKey(e, i)}
            className={cx(
              "relative h-10 shrink-0 rounded-t-md px-3 text-sm transition-colors duration-[var(--dur-1)]",
              on ? "font-medium text-ink" : "text-ink-3 hover:text-ink",
            )}
          >
            {t}
            <span aria-hidden="true" className={cx("absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent transition-transform duration-[var(--dur-2)] ease-[var(--ease-out)]", on ? "scale-x-100" : "scale-x-0")} />
          </button>
        );
      })}
    </div>
  );
}

/** Segmented control for small sets of views. */
export function Segmented<T extends string>({ options, value, onChange, label }: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-line-strong bg-sunken p-0.5">
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={o.value === value} onClick={() => onChange(o.value)}
          className={cx("h-8 rounded-[5px] px-3 text-[13px] transition-all duration-[var(--dur-1)]",
            o.value === value ? "bg-surface font-medium text-ink shadow-1" : "text-ink-3 hover:text-ink")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- States ---------- */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} aria-hidden="true" />;
}

/** Page-level loading placeholder: a header line and a few rows. */
export function LoadingBlock({ rows = 4, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-3">
      <span className="sr-only">{label}…</span>
      <Skeleton className="h-5 w-48" />
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-14 w-full" />)}
    </div>
  );
}

export function EmptyState({ title, body, action, icon }: { title: string; body?: React.ReactNode; action?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="rise-in flex flex-col items-center rounded-[10px] border border-dashed border-line-strong px-6 py-12 text-center">
      <div className="mb-4 text-ink-3" aria-hidden="true">{icon ?? <EnvelopeGlyph />}</div>
      <h3 className="font-display text-2xl text-ink">{title}</h3>
      {body && <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-2">{body}</p>}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}

export function EnvelopeGlyph({ className = "size-9" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 36 36" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="4" y="8" width="28" height="20" rx="2" />
      <path d="m4.5 9 13.5 10L31.5 9" />
    </svg>
  );
}

const isNetwork = (m: string) => /unable to reach|timed out|failed to fetch/i.test(m);

export function ErrorState({ message, onRetry, title }: { message: string; onRetry?: () => void | Promise<unknown>; title?: string }) {
  const [busy, setBusy] = useState(false);
  const network = isNetwork(message);
  return (
    <div role="alert" className="rise-in rounded-[10px] border border-bad/25 bg-bad/5 p-6">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-bad/12 text-bad" aria-hidden="true">!</span>
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-ink">{title ?? (network ? "Can’t reach the server" : "Something went wrong")}</h3>
          <p className="mt-1 break-words text-sm text-ink-2">
            {network ? "The API isn’t responding. Check that the backend is running, then try again." : message}
          </p>
          {network && <p className="mt-2 break-words font-mono text-xs text-ink-3">{message}</p>}
          {onRetry && (
            <Button variant="secondary" size="sm" className="mt-4" busy={busy}
              onClick={async () => { setBusy(true); try { await onRetry(); } finally { setBusy(false); } }}>
              Try again
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

/** Inline feedback line (form results, operation outcomes). */
export function Notice({ tone = "neutral", children, className }: { tone?: Tone; children: React.ReactNode; className?: string }) {
  const t = {
    neutral: "border-line bg-sunken/60 text-ink-2", brand: "border-brand/25 bg-brand/5 text-ink",
    accent: "border-accent/25 bg-accent/5 text-ink", ok: "border-ok/25 bg-ok/5 text-ink",
    warn: "border-warn/30 bg-warn/8 text-ink", bad: "border-bad/25 bg-bad/5 text-bad",
  }[tone];
  return <div role={tone === "bad" ? "alert" : "status"} className={cx("rise-in rounded-md border px-3.5 py-2.5 text-sm", t, className)}>{children}</div>;
}

/* ---------- Data list ---------- */
export function DefList({ items }: { items: { label: string; value: React.ReactNode }[] }) {
  return (
    <dl className="divide-y divide-line">
      {items.map((i) => (
        <div key={i.label} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
          <dt className="text-ink-3">{i.label}</dt>
          <dd className="min-w-0 text-right text-ink">{i.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export const linkCls = "text-brand underline decoration-brand/30 underline-offset-[3px] transition-colors hover:decoration-brand";

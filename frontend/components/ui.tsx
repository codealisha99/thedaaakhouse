"use client";

import { STATUSES } from "@/types";
import { chipForStage, stageFor, stageOf } from "./post/journey";
import { Chip, EmptyState as RetroEmpty, ErrorCard, Skeleton } from "./retro";

/** Backwards-compatible shells: same export names, retro rendering. */

export function Spinner() {
  return <Skeleton />;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <ErrorCard message={message} onRetry={onRetry} />;
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <RetroEmpty title="Empty" body={typeof children === "string" ? children : "Nothing here yet."} />;
}

export function StatusBadge({ status, updatedAt }: { status: string; updatedAt?: string | null }) {
  const key = stageFor(status, updatedAt ?? null);
  const stage = stageOf(key);
  const chip = chipForStage(key);
  return <Chip tone={chip.tone} dashed={chip.dashed}>{stage.title}</Chip>;
}

export function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="font-mono text-xs text-muted">—</span>;
  const tone = score >= 75 ? "green-deep" : score >= 50 ? "mustard" : "danger";
  return <Chip tone={tone as "green-deep" | "mustard" | "danger"}>ATS {score.toFixed(0)}</Chip>;
}

export function StatusSelect({ value, onChange, small }: {
  value: string; onChange: (s: string) => void; small?: boolean;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`focus-term border-2 border-green bg-surface font-mono font-bold ${small ? "min-h-[44px] px-1.5 text-xs" : "min-h-[44px] px-2.5 text-sm"}`}
    >
      {STATUSES.map((s) => (
        <option key={s} value={s}>{s.replace("_", " ")}</option>
      ))}
    </select>
  );
}

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

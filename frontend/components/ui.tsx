"use client";

import { STATUSES } from "@/types";
import { stageFor, stageOf } from "./post/journey";
import { EmptyPost, ErrorNotice, RubberStamp, TruckLoader } from "./post/postal";

/** Backwards-compatible shells: same names, postal rendering.
 *  Pages migrate to the post/* library one by one. */

export function Spinner() {
  return <TruckLoader />;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  // Deduplicate the doubled backend-unreachable phrasing at the source.
  const clean = message.replace(/Check that the API server is running\.?\s*/i, "").trim();
  return <ErrorNotice message={clean || message} onRetry={onRetry} />;
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <EmptyPost>{children}</EmptyPost>;
}

export function StatusBadge({ status, updatedAt }: { status: string; updatedAt?: string | null }) {
  const stage = stageOf(stageFor(status, updatedAt ?? null));
  return <RubberStamp text={stage.stamp} color={stage.color} size="sm" />;
}

export function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="font-mono text-xs text-postmark">—</span>;
  const color = score >= 75 ? "#1E7B4D" : score >= 50 ? "#B7791F" : "#C8102E";
  return <RubberStamp text={`ATS ${score.toFixed(0)}`} color={color} size="sm" />;
}

export function StatusSelect({ value, onChange, small }: {
  value: string; onChange: (s: string) => void; small?: boolean;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`rounded-md border border-kraft bg-envelope font-mono font-bold ${small ? "px-1.5 py-1 text-xs" : "px-2.5 py-1.5 text-sm"}`}
    >
      {STATUSES.map((s) => (
        <option key={s} value={s}>{s.replace("_", " ")}</option>
      ))}
    </select>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-mono text-xs font-bold uppercase tracking-[0.18em] text-postmark">{label}</span>
      {children}
    </label>
  );
}

export const inputCls = "w-full rounded-md border border-kraft bg-envelope px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-postred/60";

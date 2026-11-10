"use client";

import { ROUTE, STAGES, STATUS_LABEL, stageFor, stageOf, type StageKey } from "@/lib/journey";
import { STATUSES } from "@/types";
import { cx, selectCls } from "./ds";

/** Status pill coloured by its route stage. */
export function StageBadge({ status, updatedAt, stamp }: { status: string; updatedAt?: string | null; stamp?: boolean }) {
  const stage = stageOf(stageFor(status, updatedAt ?? null));
  return (
    <span
      className={cx("inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 text-xs font-medium", stamp && "stamp")}
      style={{ color: stage.color, borderColor: `color-mix(in srgb, ${stage.color} 35%, transparent)`, background: `color-mix(in srgb, ${stage.color} 9%, transparent)` }}
    >
      <span className={cx("size-1.5 rounded-full bg-current", stage.key === "dead" && "bg-transparent ring-1 ring-current")} aria-hidden="true" />
      {stage.title}
    </span>
  );
}

/**
 * The route: five forward stops; returned / dead letters branch off where they stopped.
 * `compact` renders a thin inline version for list rows.
 */
export function StageRoute({ status, updatedAt, history, compact }: {
  status: string; updatedAt?: string | null; history?: { to: string }[]; compact?: boolean;
}) {
  const current = stageFor(status, updatedAt ?? null);
  const offRoute = current === "return" || current === "dead";
  // Furthest forward stop reached, using history when the letter left the route.
  const reached = Math.max(
    ROUTE.indexOf(current),
    ...(history ?? []).map((h) => ROUTE.indexOf(stageFor(h.to, null))),
    offRoute ? 1 : 0,
  );
  const exit = offRoute ? stageOf(current) : null;

  if (compact) {
    return (
      <div className="flex items-center gap-1" aria-label={`Stage: ${stageOf(current).title}`}>
        {ROUTE.map((k, i) => (
          <span key={k} className={cx("h-1 w-4 rounded-full", i <= reached ? "" : "bg-line")}
            style={i <= reached ? { background: exit && i === reached ? exit.color : i === reached ? "var(--accent)" : "var(--ink-3)" } : undefined} />
        ))}
      </div>
    );
  }

  return (
    <ol className="relative flex items-start justify-between" aria-label="Application route">
      <span className="absolute inset-x-3 top-[7px] h-px bg-line-strong" aria-hidden="true" />
      <span className="draw absolute left-3 top-[7px] h-px bg-ink" aria-hidden="true"
        style={{ width: `calc((100% - 24px) * ${reached / (ROUTE.length - 1)})` }} />
      {ROUTE.map((k, i) => {
        const s = stageOf(k);
        const done = i < reached;
        const here = i === reached;
        const color = here ? (exit ? exit.color : "var(--accent)") : undefined;
        return (
          <li key={k} className="relative z-10 flex w-0 flex-1 flex-col items-center text-center first-of-type:items-start first-of-type:text-left last-of-type:items-end last-of-type:text-right">
            <span
              className={cx("relative block size-[15px] rounded-full border-2", here && "ping-once",
                done ? "border-ink bg-ink" : here ? "bg-surface" : "border-line-strong bg-surface")}
              style={color ? { borderColor: color, color } : undefined}
              aria-current={here ? "step" : undefined}
            >
              {here && <span className="absolute inset-[3px] rounded-full bg-current" />}
            </span>
            <span className={cx("mt-2 hidden text-[12px] leading-tight sm:block", here ? "font-medium text-ink" : done ? "text-ink-2" : "text-ink-3")}>{s.title}</span>
            {here && exit && <span className="mt-0.5 hidden text-[11px] font-medium sm:block" style={{ color: exit.color }}>{exit.title}</span>}
          </li>
        );
      })}
    </ol>
  );
}

/** Horizontal distribution bar across all stages. */
export function StageDistribution({ counts }: { counts: Record<StageKey, number> }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return (
    <div>
      <div className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-sunken" role="img"
        aria-label={STAGES.map((s) => `${s.title} ${counts[s.key]}`).join(", ")}>
        {total > 0 && STAGES.map((s) => counts[s.key] > 0 && (
          <span key={s.key} className="h-full transition-[width] duration-700 ease-[var(--ease-out)]"
            style={{ width: `${(counts[s.key] / total) * 100}%`, background: s.color }} />
        ))}
      </div>
      <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4 xl:grid-cols-7">
        {STAGES.map((s) => (
          <li key={s.key} className="min-w-0">
            <p className="flex items-center gap-1.5 text-[12px] text-ink-3">
              <span className="size-2 shrink-0 rounded-[2px]" style={{ background: s.color }} aria-hidden="true" />
              <span className="leading-tight">{s.title}</span>
            </p>
            <p className="mt-0.5 font-mono text-xl tabular text-ink">{counts[s.key]}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function StatusSelect({ value, onChange, small, label = "Status" }: { value: string; onChange: (s: string) => void; small?: boolean; label?: string }) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}
      className={cx(selectCls, "w-auto", small && "h-8 text-[13px]")}>
      {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
    </select>
  );
}

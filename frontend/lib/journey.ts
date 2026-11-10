/** Application status -> postal route stage. */

export interface Stage {
  key: StageKey;
  title: string;
  blurb: string;
  /** CSS colour reference so stage colour follows light/dark tokens. */
  color: string;
}

export type StageKey = "drafted" | "posted" | "transit" | "out" | "delivered" | "return" | "dead";

export const STAGES: Stage[] = [
  { key: "drafted", title: "Drafted", blurb: "Saved, not sent yet", color: "var(--stage-drafted)" },
  { key: "posted", title: "Posted", blurb: "Applied", color: "var(--stage-posted)" },
  { key: "transit", title: "In transit", blurb: "Assessment / screening", color: "var(--stage-transit)" },
  { key: "out", title: "Out for delivery", blurb: "Interviewing", color: "var(--stage-out)" },
  { key: "delivered", title: "Delivered", blurb: "Offer", color: "var(--stage-delivered)" },
  { key: "return", title: "Returned", blurb: "Rejected", color: "var(--stage-return)" },
  { key: "dead", title: "Dead letter", blurb: "Withdrawn or 30+ days silent", color: "var(--stage-dead)" },
];

/** The forward route (terminal side-exits excluded). */
export const ROUTE: StageKey[] = ["drafted", "posted", "transit", "out", "delivered"];

const STATUS_TO_STAGE: Record<string, StageKey> = {
  saved: "drafted", applied: "posted", oa: "transit", interview: "out",
  final_round: "out", offer: "delivered", rejected: "return", withdrawn: "dead",
};

export const STAGE_TO_STATUS: Record<StageKey, string> = {
  drafted: "saved", posted: "applied", transit: "oa", out: "interview",
  delivered: "offer", return: "rejected", dead: "withdrawn",
};

export const STATUS_LABEL: Record<string, string> = {
  saved: "Saved", applied: "Applied", oa: "Assessment", interview: "Interview",
  final_round: "Final round", offer: "Offer", rejected: "Rejected", withdrawn: "Withdrawn",
};

const DAY = 24 * 3600 * 1000;
export const TERMINAL: StageKey[] = ["delivered", "return", "dead"];

export function daysSince(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? null : Math.floor((Date.now() - t) / DAY);
}

export function stageFor(status: string, updatedAt: string | null): StageKey {
  const base = STATUS_TO_STAGE[status] ?? "drafted";
  // Ghosted: a live application untouched for 30+ days becomes a dead letter.
  const age = daysSince(updatedAt);
  if (!TERMINAL.includes(base) && age != null && age > 30) return "dead";
  return base;
}

export function stageOf(key: string): Stage {
  return STAGES.find((s) => s.key === key) ?? STAGES[0];
}

export function relativeDays(iso: string | null | undefined): string {
  const d = daysSince(iso);
  if (d == null) return "—";
  if (d <= 0) return "today";
  if (d === 1) return "yesterday";
  if (d < 30) return `${d}d ago`;
  return new Date(iso as string).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

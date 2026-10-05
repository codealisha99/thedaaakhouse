/** Postal journey mapping: backend status -> mail stage. */

export interface Stage {
  key: string;
  title: string;
  blurb: string;
  stamp: string;
  color: string; // tailwind-safe hex for inline styles
}

export const STAGES: Stage[] = [
  { key: "drafted", title: "Drafted", blurb: "still at the writing desk", stamp: "DRAFTED", color: "#5C6B7A" },
  { key: "posted", title: "Posted", blurb: "in the mailbag", stamp: "POSTED", color: "#C8102E" },
  { key: "transit", title: "In Transit", blurb: "awaiting reply", stamp: "IN TRANSIT", color: "#2E6FBF" },
  { key: "out", title: "Out for Delivery", blurb: "interview scheduled", stamp: "OUT FOR DELIVERY", color: "#5B3A8C" },
  { key: "delivered", title: "Delivered", blurb: "signed for — offer!", stamp: "DELIVERED", color: "#1E7B4D" },
  { key: "return", title: "Return to Sender", blurb: "rejected", stamp: "RETURN TO SENDER", color: "#D64545" },
  { key: "dead", title: "Dead Letter Office", blurb: "ghosted 30+ days", stamp: "DEAD LETTER", color: "#5C6B7A" },
];

const STATUS_TO_STAGE: Record<string, string> = {
  saved: "drafted",
  applied: "posted",
  oa: "transit",
  interview: "out",
  final_round: "out",
  offer: "delivered",
  rejected: "return",
  withdrawn: "dead",
};

export function stageFor(status: string, updatedAt: string | null): string {
  const base = STATUS_TO_STAGE[status] ?? "drafted";
  // Ghosted: non-terminal, untouched for 30+ days -> Dead Letter Office.
  if (!["delivered", "return", "dead"].includes(base) && updatedAt) {
    const age = Date.now() - new Date(updatedAt).getTime();
    if (age > 30 * 24 * 3600 * 1000) return "dead";
  }
  return base;
}

export function stageOf(key: string): Stage {
  return STAGES.find((s) => s.key === key) ?? STAGES[0];
}

/** Deterministic pseudo-random rotation in [-1.5deg, 1.5deg] from any id. */
export function rotateFor(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  const deg = ((h % 300) / 100 - 1.5).toFixed(2);
  return `${deg}deg`;
}

/** Short PIN-code style reference from a UUID. */
export function pinFor(id: string): string {
  return id.replace(/-/g, "").slice(0, 6).toUpperCase();
}

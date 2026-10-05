import { STATUSES, type AppStatus } from "@/types";

export function Spinner() {
  return <p className="animate-pulse text-sm text-slate-500">Loading…</p>;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <p className="font-medium">Couldn&apos;t load this.</p>
      <p className="mt-1">{message}</p>
      <p className="mt-1 text-red-600">Check that the API server is running, then try again.</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 rounded-lg border px-3 py-1 text-xs font-medium hover:bg-white">
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed bg-white p-8 text-center text-sm text-slate-500">
      {children}
    </div>
  );
}

const STATUS_STYLES: Record<AppStatus, string> = {
  saved: "bg-slate-100 text-slate-700",
  applied: "bg-blue-100 text-blue-800",
  oa: "bg-cyan-100 text-cyan-800",
  interview: "bg-violet-100 text-violet-800",
  final_round: "bg-purple-100 text-purple-800",
  offer: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-800",
  withdrawn: "bg-stone-200 text-stone-600",
};

export function StatusBadge({ status }: { status: string }) {
  const cls = (STATUS_STYLES as Record<string, string>)[status] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status.replace("_", " ")}
    </span>
  );
}

export function StatusSelect({ value, onChange, small }: {
  value: string; onChange: (s: string) => void; small?: boolean;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`rounded-lg border bg-white font-medium ${small ? "px-1.5 py-1 text-xs" : "px-2.5 py-1.5 text-sm"}`}
    >
      {STATUSES.map((s) => (
        <option key={s} value={s}>{s.replace("_", " ")}</option>
      ))}
    </select>
  );
}

export function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="text-xs text-slate-400">—</span>;
  const cls = score >= 75 ? "bg-emerald-100 text-emerald-800" : score >= 50 ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${cls}`}>
      {score.toFixed(0)}
    </span>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      {children}
    </label>
  );
}

export const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500";

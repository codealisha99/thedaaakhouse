"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ArenaSession } from "@/types";

export default function ArenaRun({ params }: { params: { id: string } }) {
  const [s, setS] = useState<ArenaSession | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setS(await api.getArena(params.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed.");
    }
  }, [params.id]);

  useEffect(() => { load(); }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      setS(await api.answerArena(params.id, draft));
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !s) return <p className="text-sm text-red-600">{error}</p>;
  if (!s) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight">
          {s.mode.replace("_", " ")} · {s.difficulty}
        </h2>
        <p className="text-sm text-slate-500">
          Question {Math.min(s.answered + 1, s.total)}/{s.total} · {s.status}
          {s.average_score != null ? ` · avg ${(s.average_score * 100).toFixed(0)}%` : ""}
        </p>
        <div className="mt-1 h-1.5 rounded bg-slate-100">
          <div className="h-1.5 rounded bg-violet-500" style={{ width: `${s.total ? (100 * s.answered) / s.total : 0}%` }} />
        </div>
      </div>

      {s.turns.map((t, i) => (
        <div key={i} className="rounded-xl border bg-white p-4 text-sm">
          <p className="font-semibold">Q{i + 1}. {t.question.question}</p>
          <p className="mt-1 text-xs text-slate-500">{t.question.topic} · {t.question.difficulty} · {t.question.source}</p>
          <p className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-2 text-slate-700">{t.answer}</p>
          <div className={`mt-2 rounded-lg p-2.5 ${t.evaluation.verdict === "strong" ? "bg-emerald-50" : t.evaluation.verdict === "partial" ? "bg-amber-50" : "bg-red-50"}`}>
            <p><strong>{t.evaluation.verdict}</strong> ({Math.round(t.evaluation.score * 100)}%) — {t.evaluation.feedback}</p>
            {t.evaluation.follow_up && <p className="mt-1">{t.evaluation.follow_up}</p>}
          </div>
        </div>
      ))}

      {s.status === "active" && s.current && (
        <form onSubmit={submit} className="rounded-xl border bg-white p-4 text-sm">
          <p className="font-semibold">Q{s.answered + 1}. {s.current.question}</p>
          <p className="mt-1 text-xs text-slate-500">
            {s.current.topic} · {s.current.reason}
            {s.current.hints.length > 0 && <> · Hint: {s.current.hints[0]}</>}
            {s.current.complexity && <> · Target: {s.current.complexity}</>}
          </p>
          {s.current.tests.length > 0 && (
            <p className="mt-1 font-mono text-xs text-slate-600">Tests: {s.current.tests.join(" | ")}</p>
          )}
          <textarea
            className="mt-2 min-h-28 w-full rounded-lg border px-3 py-2"
            placeholder="Type your answer…"
            value={draft} onChange={(e) => setDraft(e.target.value)}
          />
          {error && <p className="mt-1 text-red-600">{error}</p>}
          <button type="submit" disabled={busy || !draft.trim()}
            className="mt-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            {busy ? "Evaluating…" : "Submit answer"}
          </button>
        </form>
      )}

      {s.status === "complete" && s.summary && (
        <div className="rounded-xl border bg-white p-4 text-sm">
          <h3 className="font-semibold">Session summary</h3>
          <p className="mt-1">Strengths: {s.summary.strengths.join(", ") || "—"}</p>
          <p>Weaknesses: {s.summary.weaknesses.join(", ") || "—"}</p>
          <ul className="mt-1">
            {Object.entries(s.summary.by_category).map(([c, v]) => (
              <li key={c}>{c}: {(Number(v) * 100).toFixed(0)}%</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

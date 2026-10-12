"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { StudyPlan, TopicAnswer } from "@/types";

const STATUS_STYLE: Record<string, string> = {
  not_started: "bg-slate-100 text-slate-600",
  in_progress: "bg-blue-100 text-blue-800",
  mastered: "bg-emerald-100 text-emerald-800",
  needs_revision: "bg-amber-100 text-amber-800",
};

export default function PlanDetail({ params }: { params: { id: string } }) {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, TopicAnswer>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setPlan(await api.getPlan(params.id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed.");
    }
  }, [params.id]);

  useEffect(() => { load(); }, [load]);

  async function submitAnswer(term: string) {
    setBusy(true);
    try {
      const res = await api.answerTopic(params.id, term, drafts[term] ?? "");
      setResults((r) => ({ ...r, [term]: res }));
      await load();
    } catch (e) {
      setResults((r) => ({ ...r, [term]: {
        topic: term, score: 0, verdict: "needs_revision", hits: [], missed: [],
        feedback: e instanceof Error ? e.message : "Submit failed.",
        progress: { status: "needs_revision", attempts: 0, correct: 0 },
      }}));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!plan) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="mx-auto max-w-2xl space-y-3">
      <div>
        <h2 className="text-xl font-bold tracking-tight">{plan.title}</h2>
        <p className="text-sm text-slate-500">
          {plan.topics.filter((t) => t.progress.status === "mastered").length}/{plan.topics.length} mastered
        </p>
      </div>
      {plan.topics.map((t) => (
        <div key={t.term} className="rounded-xl border bg-white p-4 text-sm">
          <button onClick={() => setOpen(open === t.term ? null : t.term)} className="flex w-full items-center justify-between gap-2 text-left">
            <span>
              <strong>#{t.order} {t.term}</strong>{" "}
              <span className="text-xs text-slate-500">
                {t.known ? "· revision" : "· new"} · {t.progress.attempts} attempt(s)
              </span>
            </span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[t.progress.status] ?? STATUS_STYLE.not_started}`}>
              {t.progress.status.replace("_", " ")}
            </span>
          </button>
          {open === t.term && (
            <div className="mt-3 space-y-3 border-t pt-3">
              {t.resume_evidence && (
                <p className="rounded-lg bg-emerald-50 p-2 text-xs">Your evidence: {t.resume_evidence}</p>
              )}
              {t.levels.map((l) => (
                <div key={l.name}>
                  <p className="font-semibold">{l.name}</p>
                  <p className="text-slate-600">{l.prompt}</p>
                </div>
              ))}
              <div>
                <p className="font-semibold">Exercises</p>
                <ul className="list-disc pl-5 text-slate-600">
                  {t.exercises.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="font-semibold">Knowledge check</p>
                <p className="text-slate-600">{t.check.question}</p>
                <textarea
                  className="mt-2 min-h-20 w-full rounded-lg border px-3 py-2"
                  placeholder="Write your answer…"
                  value={drafts[t.term] ?? ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [t.term]: e.target.value }))}
                />
                <button onClick={() => submitAnswer(t.term)} disabled={busy || !(drafts[t.term] ?? "").trim()}
                  className="mt-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
                  Check answer
                </button>
                {results[t.term] && (
                  <div className={`mt-2 rounded-lg p-2.5 ${results[t.term].verdict === "correct" ? "bg-emerald-50" : "bg-amber-50"}`}>
                    <p><strong>{results[t.term].verdict === "correct" ? "Correct" : "Needs revision"}</strong> ({Math.round(results[t.term].score * 100)}%)</p>
                    <p>{results[t.term].feedback}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

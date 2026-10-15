"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Field, inputCls } from "@/components/ui";
import { Letterhead, TypedMemo } from "@/components/post/postal";
import { api, token } from "@/lib/api";
import type { Resume } from "@/types";

interface Attempt {
  n: number;
  version_id: string;
  score: number;
  improved: boolean;
  strategy: string;
  missing: string[];
  categories?: Record<string, number | null>;
  newly_matched?: string[];
  newly_missing?: string[];
  lines_in?: number;
  lines_out?: number;
}

interface StageEvent {
  order: number;
  stage: string;
  status: string;
  summary: string;
  source: string;
}

interface RunOut {
  id: string;
  application_id: string;
  initial_score: number;
  attempts: Attempt[];
  final_version_id: string | null;
  final_score: number | null;
  status: string;
  stop_reason: string | null;
  gaps: string[];
  latex_status: string | null;
  pdf_ready: boolean;
  stage_trace?: StageEvent[];
}

const STEPS = ["Master Resume", "Job Description", "Check ATS", "Optimize", "Final Resume"] as const;

export default function Optimize() {
  const [step, setStep] = useState(0);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [resumeId, setResumeId] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [jd, setJd] = useState("");
  const [appId, setAppId] = useState("");
  const [run, setRun] = useState<RunOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listResumes().then((r) => {
      setResumes(r);
      if (r.length > 0) setResumeId(r[0].id);
    }).catch((e) => setError(e instanceof Error ? e.message : "Load failed."));
  }, []);

  async function checkAts(e: React.FormEvent) {
    e.preventDefault();
    if (!jd.trim()) {
      setError("Paste a job description first.");
      return;
    }
    setError(null); setBusy(true);
    try {
      const app = await api.createApp({
        company: company || "Untitled", role: role || "Untitled role",
        raw_jd: jd, status: "saved",
        date_saved: new Date().toISOString().slice(0, 10),
      });
      setAppId(app.id);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save job description.");
    } finally {
      setBusy(false);
    }
  }

  async function optimize() {
    if (!resumeId) {
      setError("Select a master resume first (step 1).");
      return;
    }
    setError(null); setBusy(true);
    try {
      const out = await api.runOptimize(appId, resumeId);
      setRun(out);
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Optimization failed.");
    } finally {
      setBusy(false);
    }
  }

  function download(kind: "latex" | "pdf") {
    if (!run) return;
    const t = token.get();
    const url = kind === "latex" ? api.optimizeLatexUrl(run.id) : api.optimizePdfUrl(run.id);
    fetch(url, { headers: t ? { Authorization: `Bearer ${t}` } : {} })
      .then((r) => { if (!r.ok) throw new Error(`Download failed (${r.status})`); return r.blob(); })
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `resume-${run.id.slice(0, 8)}.${kind === "latex" ? "tex" : "pdf"}`;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Download failed."));
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Letterhead title="ATS Optimization" subtitle="Master resume → tailored resume → LaTeX" />
      <ol className="flex flex-wrap gap-1.5">
        {STEPS.map((s, i) => (
          <li key={s}>
            <button onClick={() => { if (i <= step) { setStep(i); setError(null); } }}
              disabled={i > step}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ${i === step ? "bg-slate-900 text-white" : i < step ? "border bg-emerald-50" : "border bg-white opacity-50"}`}>
              {i + 1}. {s}
            </button>
          </li>
        ))}
      </ol>
      {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}

      {step === 0 && (
        <div className="space-y-3 rounded-xl border bg-white p-5">
          <h3 className="font-semibold">Step 1 — choose the master resume (never modified)</h3>
          {resumes.length === 0 ? (
            <p className="text-sm text-slate-500">
              No resumes yet. <Link href="/resume" className="text-violet-700 hover:underline">Upload one first →</Link>
            </p>
          ) : (
            <ul className="space-y-1.5">
              {resumes.map((r) => (
                <li key={r.id}>
                  <label className="flex cursor-pointer items-center gap-2 rounded-lg border p-2.5 text-sm">
                    <input type="radio" name="master" checked={resumeId === r.id} onChange={() => setResumeId(r.id)} />
                    <span className="font-medium">{r.filename}</span>
                    <span className="text-xs text-slate-500">{r.parse_status}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          <button onClick={() => resumeId && setStep(1)} disabled={!resumeId}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            Continue →
          </button>
        </div>
      )}

      {step === 1 && (
        <form onSubmit={checkAts} className="space-y-3 rounded-xl border bg-white p-5">
          <h3 className="font-semibold">Step 2 — paste the job description (no URL needed)</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Company"><input className={inputCls} value={company} onChange={(e) => setCompany(e.target.value)} /></Field>
            <Field label="Role"><input className={inputCls} value={role} onChange={(e) => setRole(e.target.value)} /></Field>
          </div>
          <Field label="Job description">
            <textarea className={`${inputCls} min-h-48 font-mono text-xs`} value={jd}
              onChange={(e) => setJd(e.target.value)} placeholder="Paste the complete job description…" />
          </Field>
          <button type="submit" disabled={busy}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            {busy ? "Saving…" : "Save & continue →"}
          </button>
        </form>
      )}

      {step === 2 && <StepCheck appId={appId} resumeId={resumeId} onDone={() => setStep(3)} />}

      {step === 3 && (
        <div className="space-y-3 rounded-xl border bg-white p-5">
          <h3 className="font-semibold">Step 4 — optimize (auto-tailors below 90, accepts at 92, max 3 attempts)</h3>
          <button onClick={optimize} disabled={busy}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            {busy ? "Optimizing… (each attempt re-scores)" : "Run optimization"}
          </button>
        </div>
      )}

      {step === 4 && run && (
        <div className="space-y-4">
          <div className={`rounded-xl border p-5 ${run.status === "accepted" ? "bg-emerald-50" : "bg-amber-50"}`}>
            <h3 className="font-semibold">
              Step 5 — {run.status === "accepted" ? "Accepted ✓" : "Target not reached"} · final {run.final_score?.toFixed(1)}
            </h3>
            <p className="text-sm text-slate-600">
              Initial {run.initial_score.toFixed(1)} → {run.attempts.length} attempt(s). {run.stop_reason}
            </p>
            {run.gaps.length > 0 && (
              <p className="mt-1 text-sm">Remaining gaps: {run.gaps.slice(0, 8).join(", ")}</p>
            )}
          </div>
          <div className="rounded-xl border bg-white p-5 text-sm">
            <h4 className="font-semibold">Attempts (same scoring throughout)</h4>
            <ul className="mt-2 space-y-1.5">
              {run.attempts.map((a) => (
                <li key={a.n} className="rounded-lg bg-slate-50 p-2.5">
                  <p>Attempt {a.n}: <strong>{a.score.toFixed(1)}</strong> {a.improved ? "▲ improved" : "— no gain"} · {a.strategy}</p>
                  {a.missing.length > 0 && <p className="text-xs text-slate-500">Still missing: {a.missing.slice(0, 6).join(", ")}</p>}
                  {(a.newly_matched?.length ?? 0) > 0 && <p className="text-xs text-emerald-700">Newly matched: {a.newly_matched!.slice(0, 6).join(", ")}</p>}
                  {(a.newly_missing?.length ?? 0) > 0 && <p className="text-xs text-red-600">Newly missing: {a.newly_missing!.slice(0, 6).join(", ")}</p>}
                  {a.lines_in != null && a.lines_out != null && a.lines_in !== a.lines_out && (
                    <p className="text-xs text-slate-500">Lines: {a.lines_in} → {a.lines_out} (zero-overlap bullets listed as omitted, not hidden)</p>
                  )}
                </li>
              ))}
              {run.attempts.length === 0 && <li className="text-slate-500">No tailoring runs needed.</li>}
            </ul>
          </div>
          {(run.stage_trace ?? []).length > 0 && (
            <details className="rounded-xl border bg-white p-5 text-sm" open>
              <summary className="cursor-pointer font-semibold">
                Workflow trace ({run.stage_trace!.length} stages — every step accounted for)
              </summary>
              <ol className="mt-2 space-y-1.5">
                {run.stage_trace!.map((s, i) => (
                  <li key={i} className={`rounded-lg p-2.5 ${
                    s.status === "failed" ? "bg-red-50" : s.status === "skipped" ? "bg-slate-50" : "bg-emerald-50/60"}`}>
                    <p>
                      <span className="font-mono text-xs text-slate-500">{String(s.order).padStart(2, "0")}</span>{" "}
                      <strong className="font-mono text-xs">{s.stage}</strong>{" "}
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        s.status === "failed" ? "bg-red-100 text-red-800"
                        : s.status === "skipped" ? "bg-slate-100 text-slate-600"
                        : "bg-emerald-100 text-emerald-800"}`}>{s.status}</span>
                    </p>
                    {s.summary && <p className="mt-0.5 text-slate-600">{s.summary}</p>}
                  </li>
                ))}
              </ol>
            </details>
          )}
          <div className="flex flex-wrap gap-2">
            <button onClick={() => download("latex")}
              className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-slate-50">
              Download .tex
            </button>
            {run.pdf_ready
              ? <button onClick={() => download("pdf")} className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-slate-50">Download PDF</button>
              : <p className="self-center text-xs text-slate-500">No compiled PDF — pdflatex unavailable; compile the .tex with a LaTeX distribution.</p>}
            {run.final_version_id && (
              <Link href={`/resume/versions/${run.final_version_id}`} className="self-center text-sm text-violet-700 hover:underline">
                Inspect final version →
              </Link>
            )}
          </div>
        </div>
      )}

      <TypedMemo title="Honesty rules">
        <p>Tailoring only reorders and trims your real bullets. Missing requirements are reported, never invented. A stuck score returns the best valid version, not a passing one.</p>
      </TypedMemo>
    </div>
  );
}

function StepCheck({ appId, resumeId, onDone }: { appId: string; resumeId: string; onDone: () => void }) {
  const [out, setOut] = useState<{ score: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setBusy(true);
    api.runAtsV2(appId, { resume_id: resumeId })
      .then((r) => { setOut({ score: r.score }); })
      .catch((e) => setError(e instanceof Error ? e.message : "ATS check failed."))
      .finally(() => setBusy(false));
  }, [appId, resumeId]);

  return (
    <div className="rounded-xl border bg-white p-5">
      <h3 className="font-semibold">Step 3 — initial ATS score</h3>
      {busy && <p className="text-sm text-slate-500">Scoring master resume…</p>}
      {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
      {out && (
        <>
          <p className="mt-2 font-serif text-5xl font-bold">{out.score.toFixed(0)}<span className="text-xl text-slate-400">/100</span></p>
          <p className="text-sm text-slate-600">
            {out.score < 90 ? "Below 90 — optimization will tailor automatically." : "At or above 90 — no automatic tailoring."}
          </p>
          <button onClick={onDone} className="mt-3 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white">
            Continue →
          </button>
        </>
      )}
    </div>
  );
}

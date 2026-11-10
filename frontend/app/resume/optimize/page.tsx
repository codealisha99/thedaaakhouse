"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Badge, Button, EmptyState, Field, LinkButton, Label, Notice, PageHeader, Panel, PanelHeader,
  Score, Spinner, Tag, cx, inputCls, linkCls, textareaCls,
} from "@/components/ds";
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

type Trend = "improved" | "regressed" | "no-gain";

const STEPS = ["Master Resume", "Job Description", "Check ATS", "Optimize", "Final Resume"] as const;

const TREND: Record<Trend, { label: string; tone: "ok" | "bad" | "neutral"; bar: string }> = {
  improved: { label: "▲ improved", tone: "ok", bar: "bg-ok" },
  regressed: { label: "▼ regressed", tone: "bad", bar: "bg-bad" },
  "no-gain": { label: "— no gain", tone: "neutral", bar: "bg-ink-3" },
};

/** Trend compares each attempt with the score before it (initial for attempt 1). */
function trendOf(a: Attempt, previous: number): Trend {
  if (a.improved) return "improved";
  return a.score < previous ? "regressed" : "no-gain";
}

function downloadRunFile(runId: string, kind: "latex" | "pdf"): Promise<void> {
  const t = token.get();
  const url = kind === "latex" ? api.optimizeLatexUrl(runId) : api.optimizePdfUrl(runId);
  return fetch(url, { headers: t ? { Authorization: `Bearer ${t}` } : {} })
    .then((r) => { if (!r.ok) throw new Error(`Download failed (${r.status})`); return r.blob(); })
    .then((blob) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `resume-${runId.slice(0, 8)}.${kind === "latex" ? "tex" : "pdf"}`;
      a.click();
      URL.revokeObjectURL(a.href);
    });
}

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
    downloadRunFile(run.id, kind).catch((e) => setError(e instanceof Error ? e.message : "Download failed."));
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Resume · Optimize"
        title="Optimize resume"
        description="Master resume to tailored resume to LaTeX. Every attempt is scored the same way, so the progression is comparable."
      />
      <StepNav step={step} onGo={(i) => { setStep(i); setError(null); }} />
      {error && <Notice tone="bad">{error}</Notice>}

      {step === 0 && (
        <StepResume resumes={resumes} resumeId={resumeId} onPick={setResumeId} onContinue={() => resumeId && setStep(1)} />
      )}
      {step === 1 && (
        <StepJob
          company={company} role={role} jd={jd} busy={busy}
          onCompany={setCompany} onRole={setRole} onJd={setJd} onSubmit={checkAts}
        />
      )}
      {step === 2 && <StepCheck appId={appId} resumeId={resumeId} onDone={() => setStep(3)} />}
      {step === 3 && (
        <Panel className="space-y-4">
          <PanelHeader title="Run optimization" meta="Auto-tailors below 90, accepts at 92, and stops after 3 attempts." />
          <Button variant="accent" busy={busy} onClick={optimize}>
            {busy ? "Optimizing… each attempt re-scores" : "Run optimization"}
          </Button>
        </Panel>
      )}
      {step === 4 && run && <RunResult run={run} onDownload={download} />}

      <Panel>
        <Label>Honesty rules</Label>
        <p className="mt-2 text-sm leading-relaxed text-ink-2">
          Tailoring only reorders and trims your real bullets. Missing requirements are reported, never invented.
          A stuck score returns the best valid version, not a passing one.
        </p>
      </Panel>
    </div>
  );
}

function StepNav({ step, onGo }: { step: number; onGo: (i: number) => void }) {
  return (
    <ol aria-label="Optimization steps" className="flex flex-wrap gap-2">
      {STEPS.map((s, i) => {
        const done = i < step;
        const current = i === step;
        return (
          <li key={s}>
            <button
              type="button" onClick={() => onGo(i)} disabled={i > step}
              aria-current={current ? "step" : undefined}
              className={cx(
                "inline-flex h-9 items-center gap-2 rounded-md border px-3 text-[13px] transition-colors duration-[var(--dur-1)] disabled:pointer-events-none disabled:opacity-45",
                current ? "border-ink bg-ink font-medium text-on-ink"
                  : done ? "border-ok/30 bg-ok/8 text-ok hover:bg-ok/12"
                  : "border-line bg-surface text-ink-3",
              )}
            >
              <span className="font-mono text-[11px] tabular">{i + 1}</span>
              {s}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function StepResume({ resumes, resumeId, onPick, onContinue }: {
  resumes: Resume[]; resumeId: string; onPick: (id: string) => void; onContinue: () => void;
}) {
  return (
    <Panel className="space-y-4">
      <PanelHeader title="Choose the master resume" meta="Step 1. The master is never modified." />
      {resumes.length === 0 ? (
        <EmptyState
          title="No resumes yet"
          body="Upload a master resume first, then come back here."
          action={<LinkButton href="/resume" variant="secondary">Upload a resume</LinkButton>}
        />
      ) : (
        <fieldset>
          <legend className="sr-only">Master resume</legend>
          <ul className="stagger space-y-2">
            {resumes.map((r) => (
              <li key={r.id}>
                <label className={cx(
                  "flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors duration-[var(--dur-1)]",
                  resumeId === r.id ? "border-ink bg-sunken/60" : "border-line hover:border-ink-3",
                )}>
                  <input type="radio" name="master" checked={resumeId === r.id} onChange={() => onPick(r.id)}
                    className="size-4 shrink-0 accent-[var(--ink)]" />
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{r.filename}</span>
                  <span className="font-mono text-[12px] text-ink-3">{r.parse_status}</span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
      )}
      <Button variant="accent" disabled={!resumeId} onClick={onContinue}>Continue</Button>
    </Panel>
  );
}

function StepJob({ company, role, jd, busy, onCompany, onRole, onJd, onSubmit }: {
  company: string; role: string; jd: string; busy: boolean;
  onCompany: (v: string) => void; onRole: (v: string) => void; onJd: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
}) {
  return (
    <form onSubmit={onSubmit}>
      <Panel className="space-y-4">
        <PanelHeader title="Paste the job description" meta="Step 2. No URL needed." />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Company"><input className={inputCls} value={company} onChange={(e) => onCompany(e.target.value)} /></Field>
          <Field label="Role"><input className={inputCls} value={role} onChange={(e) => onRole(e.target.value)} /></Field>
        </div>
        <Field label="Job description">
          <textarea className={cx(textareaCls, "font-mono text-[13px]")} rows={12} value={jd}
            onChange={(e) => onJd(e.target.value)} placeholder="Paste the complete job description…" />
        </Field>
        <Button type="submit" variant="accent" busy={busy}>{busy ? "Saving…" : "Save and continue"}</Button>
      </Panel>
    </form>
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
    <Panel className="space-y-4">
      <PanelHeader title="Initial ATS score" meta="Step 3. Scoring the master resume." />
      {busy && <div className="flex items-center gap-2 text-sm text-ink-3"><Spinner />Scoring master resume…</div>}
      {error && <Notice tone="bad">{error}</Notice>}
      {out && (
        <>
          <Score value={out.score} label="Initial" caption={out.score < 90
            ? "Below 90. Optimization will tailor automatically."
            : "At or above 90. No automatic tailoring."} />
          <Button variant="accent" onClick={onDone}>Continue</Button>
        </>
      )}
    </Panel>
  );
}

function RunResult({ run, onDownload }: { run: RunOut; onDownload: (kind: "latex" | "pdf") => void }) {
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[1fr_300px]">
      <div className="stagger space-y-6">
        <ScoreProgression initial={run.initial_score} attempts={run.attempts} />
        <AttemptList attempts={run.attempts} initial={run.initial_score} />
        {(run.stage_trace ?? []).length > 0 && <StageTrace stages={run.stage_trace ?? []} />}
      </div>
      <Outcome run={run} onDownload={onDownload} />
    </div>
  );
}

/** Score per attempt as a bar sequence: initial first, then each attempt, coloured by trend. */
function ScoreProgression({ initial, attempts }: { initial: number; attempts: Attempt[] }) {
  const bars: { key: string; label: string; score: number; trend?: Trend }[] = [{ key: "initial", label: "Initial", score: initial }];
  attempts.reduce((prev, a) => {
    bars.push({ key: `a${a.n}`, label: `#${a.n}`, score: a.score, trend: trendOf(a, prev) });
    return a.score;
  }, initial);
  return (
    <Panel>
      <PanelHeader title="Score progression" meta="Same scoring on every attempt. Bars are out of 100." />
      <div className="overflow-x-auto">
        <div className="flex h-44 min-w-full items-end gap-3">
          {bars.map((b) => (
            <div key={b.key} className="flex min-w-12 flex-1 flex-col items-center gap-1.5">
              <span className="font-mono text-[12px] tabular text-ink">{b.score.toFixed(1)}</span>
              <div className="relative flex h-24 w-full items-end justify-center">
                <div className={cx("w-full max-w-10 rounded-t-sm", b.trend ? TREND[b.trend].bar : "bg-ink-3")}
                  style={{ height: `${Math.max(0, Math.min(100, b.score))}%` }}
                  role="img" aria-label={`${b.label}: ${b.score.toFixed(1)}${b.trend ? `, ${TREND[b.trend].label.replace(/^[^a-z]+/, "")}` : ""}`} />
              </div>
              <span className="font-mono text-[11px] text-ink-3">{b.label}</span>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function AttemptList({ attempts, initial }: { attempts: Attempt[]; initial: number }) {
  if (attempts.length === 0) {
    return <Panel><p className="text-sm text-ink-3">No tailoring runs needed.</p></Panel>;
  }
  const previous = (i: number) => (i === 0 ? initial : attempts[i - 1].score);
  return (
    <Panel>
      <PanelHeader title="Attempts" meta="What each attempt changed against the score before it." />
      <ul className="stagger space-y-3">
        {attempts.map((a, i) => {
          const trend = trendOf(a, previous(i));
          const delta = a.score - previous(i);
          return (
            <li key={a.n} className="rounded-md border border-line p-3.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-ink"><span className="font-mono tabular">Attempt {a.n}</span> · {a.strategy}</p>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm tabular text-ink">{a.score.toFixed(1)}</span>
                  <span className="font-mono text-[12px] tabular text-ink-3">{delta >= 0 ? "+" : ""}{delta.toFixed(1)}</span>
                  <Badge tone={TREND[trend].tone}>{TREND[trend].label}</Badge>
                </div>
              </div>
              {a.lines_in != null && a.lines_out != null && a.lines_in !== a.lines_out && (
                <p className="mt-1.5 text-[12px] text-ink-3">
                  Lines {a.lines_in} → {a.lines_out}. Zero-overlap bullets are listed as omitted, not hidden.
                </p>
              )}
              <TagRow label="Newly matched" tone="ok" items={a.newly_matched ?? []} />
              <TagRow label="Newly missing" tone="bad" items={a.newly_missing ?? []} />
              <TagRow label="Still missing" tone="neutral" items={a.missing} />
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function TagRow({ label, tone, items }: { label: string; tone: "ok" | "bad" | "neutral"; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
      <Label className="mr-1">{label}</Label>
      {items.map((x) => <Tag key={x} tone={tone}>{x}</Tag>)}
    </div>
  );
}

function StageTrace({ stages }: { stages: StageEvent[] }) {
  return (
    <details open className="rounded-[10px] border border-line bg-surface p-5 shadow-1">
      <summary className="cursor-pointer list-none">
        <span className="text-[15px] font-semibold text-ink">Workflow trace</span>
        <span className="ml-2 text-[13px] text-ink-3">{stages.length} stages, every step accounted for</span>
      </summary>
      <ol className="mt-4 space-y-2">
        {stages.map((s, i) => (
          <li key={i} className="rounded-md border border-line p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[11px] tabular text-ink-3">{String(s.order).padStart(2, "0")}</span>
              <span className="font-mono text-[12px] text-ink">{s.stage}</span>
              <Badge tone={s.status === "failed" ? "bad" : s.status === "skipped" ? "neutral" : "ok"}>{s.status}</Badge>
            </div>
            {s.summary && <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">{s.summary}</p>}
          </li>
        ))}
      </ol>
    </details>
  );
}

function Outcome({ run, onDownload }: { run: RunOut; onDownload: (kind: "latex" | "pdf") => void }) {
  const accepted = run.status === "accepted";
  return (
    <Panel as="aside" className="space-y-5 lg:sticky lg:top-6">
      <Notice tone={accepted ? "ok" : "warn"}>{accepted ? "Accepted" : "Target not reached"}</Notice>
      <div>
        <Label>Final score</Label>
        <p className="mt-1 font-mono text-4xl font-medium tabular tracking-tight text-ink">
          {run.final_score == null ? "—" : run.final_score.toFixed(1)}
          {run.final_score != null && <span className="ml-1 text-base text-ink-3">/100</span>}
        </p>
        <p className="mt-1 text-[13px] text-ink-3">
          Initial {run.initial_score.toFixed(1)} → {run.attempts.length} attempt{run.attempts.length === 1 ? "" : "s"}
        </p>
      </div>
      {run.stop_reason && <p className="text-sm leading-relaxed text-ink-2">{run.stop_reason}</p>}
      {run.gaps.length > 0 && (
        <div>
          <Label>Remaining gaps</Label>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {run.gaps.map((g) => <Tag key={g} tone="bad">{g}</Tag>)}
          </div>
        </div>
      )}
      <div className="space-y-2 border-t border-line pt-4">
        <Button variant="secondary" className="w-full" onClick={() => onDownload("latex")}>Download .tex</Button>
        {run.pdf_ready
          ? <Button variant="secondary" className="w-full" onClick={() => onDownload("pdf")}>Download PDF</Button>
          : <p className="text-[13px] text-ink-3">No compiled PDF. pdflatex is unavailable, so compile the .tex with a LaTeX distribution.</p>}
        {run.final_version_id && (
          <Link href={`/resume/versions/${run.final_version_id}`} className={cx(linkCls, "block pt-1 text-center text-sm")}>
            Inspect final version →
          </Link>
        )}
      </div>
    </Panel>
  );
}

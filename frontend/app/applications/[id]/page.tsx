"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorBox, ScoreBadge, Spinner, StatusBadge, StatusSelect, Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { ApplicationDetail, ResumeVersion } from "@/types";

const TABS = ["Overview", "Job Description", "Company", "Resume", "ATS", "Interview"] as const;

export default function AppDetail({ params }: { params: { id: string } }) {
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      setDetail(await api.getApp(params.id));
      setState("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
      setState("error");
    }
  }, [params.id]);

  useEffect(() => { load(); }, [load]);

  async function patch(patch: Record<string, unknown>, note?: string) {
    setBusy(true); setMsg(null);
    try {
      const updated = await api.patchApp(params.id, patch as never);
      setDetail((d) => (d ? { ...d, application: { ...d.application, ...updated } } : d));
      setMsg(note ?? "Saved.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function run<T>(fn: () => Promise<T>, note: string) {
    setBusy(true); setMsg(null);
    try {
      await fn();
      await load();
      setMsg(note);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Operation failed.");
    } finally {
      setBusy(false);
    }
  }

  if (state === "loading") return <Spinner />;
  if (state === "error" || !detail) return <ErrorBox message={error} onRetry={load} />;
  const a = detail.application;

  return (
    <div className="space-y-5">
      <div className="rounded-xl border bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight">{a.company || "Untitled"} · {a.role}</h2>
            <p className="text-sm text-slate-500">{a.location ?? ""}{a.job_url ? <> · <a href={a.job_url} target="_blank" rel="noreferrer" className="text-violet-700 hover:underline">posting ⧉</a></> : null}</p>
          </div>
          <div className="flex items-center gap-2">
            <ScoreBadge score={a.ats_score} />
            <StatusBadge status={a.status} />
            <StatusSelect small value={a.status} onChange={(s) => patch({ status: s }, "Status updated.")} />
          </div>
        </div>
        {msg && <p className="mt-2 text-sm text-slate-600">{msg}</p>}
      </div>

      <nav className="flex gap-1.5 overflow-x-auto">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-medium ${tab === t ? "bg-slate-900 text-white" : "border bg-white hover:bg-slate-100"}`}>
            {t}
          </button>
        ))}
      </nav>

      <div className="rounded-xl border bg-white p-5">
        {tab === "Overview" && <OverviewTab appId={params.id} detail={detail} patch={patch} busy={busy} />}
        {tab === "Job Description" && <JdTab detail={detail} />}
        {tab === "Company" && <CompanyTab appId={params.id} detail={detail} run={run} busy={busy} />}
        {tab === "Resume" && <ResumeTab appId={params.id} detail={detail} run={run} busy={busy} reload={load} />}
        {tab === "ATS" && <AtsTab appId={params.id} detail={detail} run={run} busy={busy} />}
        {tab === "Interview" && <PrepTab appId={params.id} detail={detail} run={run} busy={busy} />}
      </div>
    </div>
  );
}

function OverviewTab({ detail, patch, busy }: {
  detail: ApplicationDetail; appId: string;
  patch: (p: Record<string, unknown>, note?: string) => Promise<void>; busy: boolean;
}) {
  const a = detail.application;
  const [notes, setNotes] = useState(a.notes);
  // Sync when the application (re)loads; blur-saves only on actual edits.
  useEffect(() => { setNotes(detail.application.notes); }, [detail.application.id, detail.application.notes]);
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date saved"><input className={inputCls} type="date" defaultValue={a.date_saved ?? ""} onBlur={(e) => patch({ date_saved: e.target.value || null })} /></Field>
          <Field label="Date applied"><input className={inputCls} type="date" defaultValue={a.date_applied ?? ""} onBlur={(e) => patch({ date_applied: e.target.value || null })} /></Field>
          <Field label="Salary"><input className={inputCls} defaultValue={a.salary ?? ""} onBlur={(e) => patch({ salary: e.target.value || null })} /></Field>
          <Field label="Interview date"><input className={inputCls} defaultValue={a.interview_date ?? ""} placeholder="2026-10-20 10:00" onBlur={(e) => patch({ interview_date: e.target.value || null })} /></Field>
        </div>
        <Field label="Next step"><input className={inputCls} defaultValue={a.next_step ?? ""} onBlur={(e) => patch({ next_step: e.target.value || null })} /></Field>
        <Field label="Notes">
          <textarea className={`${inputCls} min-h-28`} value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={() => { if (notes !== a.notes) patch({ notes }); }} />
        </Field>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold">Timeline</h3>
        {a.status_history.length === 0 ? (
          <p className="text-sm text-slate-500">No events yet.</p>
        ) : (
          <ol className="space-y-2 text-sm">
            {[...a.status_history].reverse().map((h, i) => (
              <li key={i} className="rounded-lg bg-slate-50 px-3 py-2">
                {h.from ? <><StatusBadge status={h.from} /> → </> : "Created as "}
                <StatusBadge status={h.to} />
                <span className="ml-2 text-xs text-slate-400">{new Date(h.at).toLocaleString()}</span>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-3 text-xs text-slate-400">
          Attached resume: {detail.attached_version?.label ?? "none"} ·
          ATS runs: {detail.ats_history.length} · Prep plans: {detail.interview_preps.length}
        </p>
      </div>
    </div>
  );
}

function JdTab({ detail }: { detail: ApplicationDetail }) {
  const a = detail.application;
  const jd = a.jd_analysis;
  return (
    <div className="space-y-4 text-sm">
      {!a.raw_jd && <EmptyState>No job description saved. Edit this application from the Tracker to paste one.</EmptyState>}
      {jd && (
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h3 className="mb-1 font-semibold">Required skills ({jd.skills.length})</h3>
            <div className="flex flex-wrap gap-1.5">
              {jd.skills.map((s) => <span key={s} className="rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-medium text-violet-800">{s}</span>)}
            </div>
            <h3 className="mb-1 mt-4 font-semibold">Top keywords</h3>
            <div className="flex flex-wrap gap-1.5">
              {jd.keywords.slice(0, 20).map((k) => <span key={k.term} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs">{k.term} ×{k.count}</span>)}
            </div>
            {jd.experience_years != null && <p className="mt-3">Experience required: <strong>{jd.experience_years}+ years</strong></p>}
          </div>
          <div>
            <h3 className="mb-1 font-semibold">Responsibilities</h3>
            <ul className="list-disc space-y-1 pl-5 text-slate-700">
              {jd.responsibilities.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        </div>
      )}
      {a.raw_jd && (
        <details>
          <summary className="cursor-pointer text-violet-700">Raw job description ({a.raw_jd.length} chars)</summary>
          <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs">{a.raw_jd}</pre>
        </details>
      )}
    </div>
  );
}

function CompanyTab({ appId, detail, run, busy }: {
  appId: string; detail: ApplicationDetail;
  run: <T>(fn: () => Promise<T>, note: string) => Promise<void>; busy: boolean;
}) {
  const [website, setWebsite] = useState("");
  const latest = detail.research[0];
  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap gap-2">
        <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://company.com (optional)"
          className="min-w-64 flex-1 rounded-lg border px-3 py-1.5" />
        <button disabled={busy} onClick={() => run(() => api.runResearch(appId, website || undefined), "Research saved.")}
          className="rounded-lg bg-slate-900 px-4 py-1.5 font-medium text-white disabled:opacity-40">
          Run research
        </button>
      </div>
      {!latest && <EmptyState>No research yet. Paste the company website and run it — findings are extracted from the real page, with sources.</EmptyState>}
      {latest && (
        <div className="space-y-2">
          <p><strong>{latest.name}</strong>{latest.website ? <> · <a href={latest.website} target="_blank" rel="noreferrer" className="text-violet-700 hover:underline">{latest.website}</a></> : null}</p>
          {(latest.profile.extracted_statements as string[] ?? []).map((s, i) => <p key={i} className="rounded-lg bg-slate-50 p-2.5">“{s}”</p>)}
          {((latest.profile.technology_signals as string[]) ?? []).length > 0 && (
            <p>Tech signals: {((latest.profile.technology_signals as string[]) ?? []).join(", ")}</p>
          )}
          <p className="text-xs text-slate-400">Sources: {latest.sources.map((s) => s.source_url).join(", ") || "none recorded"}</p>
        </div>
      )}
    </div>
  );
}

function ResumeTab({ appId, detail, run, busy, reload }: {
  appId: string; detail: ApplicationDetail;
  run: <T>(fn: () => Promise<T>, note: string) => Promise<void>; busy: boolean; reload: () => void;
}) {
  return (
    <div className="space-y-3 text-sm">
      <p>Attached version: <strong>{detail.attached_version?.label ?? "none"}</strong></p>
      {detail.versions.length === 0 && <EmptyState>No tailored versions for this application yet.</EmptyState>}
      <ul className="space-y-2">
        {detail.versions.map((v: ResumeVersion) => (
          <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3">
            <div>
              <p className="font-medium">{v.label}</p>
              <p className="text-xs text-slate-500">ATS before: {v.ats_score ?? "—"} · missing: {v.missing_keywords.slice(0, 5).join(", ") || "none"}</p>
            </div>
            <div className="flex gap-2">
              {detail.application.resume_version_id !== v.id && (
                <button disabled={busy} onClick={() => run(() => api.attachVersion(appId, v.id), "Version attached.")}
                  className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50">Attach</button>
              )}
              <Link href={`/resume/ats?app=${appId}&version=${v.id}`} className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50">Check ATS</Link>
            </div>
          </li>
        ))}
      </ul>
      <Link href={`/resume/tailor?app=${appId}`} className="inline-block rounded-lg bg-slate-900 px-4 py-2 font-medium text-white">
        Tailor a resume for this JD →
      </Link>
    </div>
  );
}

function AtsTab({ appId, detail, run, busy }: {
  appId: string; detail: ApplicationDetail;
  run: <T>(fn: () => Promise<T>, note: string) => Promise<void>; busy: boolean;
}) {
  const latest = detail.ats_history[0];
  return (
    <div className="space-y-3 text-sm">
      <button disabled={busy || !detail.application.resume_version_id}
        onClick={() => run(() => api.runAts(appId, {}), "ATS analysis complete.")}
        className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-40">
        Run ATS on attached resume
      </button>
      {!detail.application.resume_version_id && <p className="text-slate-500">Attach a resume version first (Resume tab).</p>}
      {detail.ats_history.length === 0 && <EmptyState>No ATS runs yet.</EmptyState>}
      {latest && (
        <div className="space-y-3">
          <p className="text-lg">Score: <ScoreBadge score={latest.score} /> <span className="text-xs text-slate-400">{latest.breakdown.methodology}</span></p>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="font-semibold">Matched ({latest.breakdown.skills_matched.length})</p>
              <p className="text-slate-700">{latest.breakdown.skills_matched.join(", ") || "—"}</p>
            </div>
            <div className="rounded-lg bg-red-50 p-3">
              <p className="font-semibold">Missing ({latest.breakdown.skills_missing.length})</p>
              <p>{latest.breakdown.skills_missing.join(", ") || "—"}</p>
            </div>
          </div>
          {latest.breakdown.formatting_issues.length > 0 && (
            <p>Formatting issues: {latest.breakdown.formatting_issues.join(" · ")}</p>
          )}
          <div>
            <p className="font-semibold">Recommendations</p>
            <ul className="list-disc space-y-1 pl-5 text-slate-700">
              {latest.breakdown.recommendations.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function PrepTab({ appId, detail, run, busy }: {
  appId: string; detail: ApplicationDetail;
  run: <T>(fn: () => Promise<T>, note: string) => Promise<void>; busy: boolean;
}) {
  const latest = detail.interview_preps[0];
  return (
    <div className="space-y-3 text-sm">
      <button disabled={busy} onClick={() => run(() => api.runPrep(appId), "Interview plan generated.")}
        className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-40">
        Generate interview plan
      </button>
      {!latest && <EmptyState>No prep plan yet. Generated from this JD — each question says why it exists.</EmptyState>}
      {latest && (
        <div className="space-y-2">
          <p><strong>Topics:</strong> {latest.plan.topics.join(", ")}</p>
          {latest.plan.focus_areas.length > 0 && <p><strong>Focus (missing from your resume):</strong> {latest.plan.focus_areas.join(", ")}</p>}
          <ol className="space-y-2">
            {latest.plan.questions.map((q, i) => (
              <li key={i} className="rounded-lg border p-3">
                <p className="font-medium">{i + 1}. {q.question}</p>
                <p className="mt-1 text-xs text-slate-500">{q.category} · {q.reason} · <em>{q.source}</em></p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

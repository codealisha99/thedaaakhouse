"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ErrorBox, Field, ScoreBadge, Spinner, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { Application, ATSBreakdown, Resume, ResumeVersion } from "@/types";

function AtsInner() {
  const params = useSearchParams();
  const [apps, setApps] = useState<Application[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [appId, setAppId] = useState(params.get("app") ?? "");
  const [source, setSource] = useState<string>(params.get("version") ? `v:${params.get("version")}` : "");
  const [out, setOut] = useState<{ score: number; breakdown: ATSBreakdown } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([api.listApps({}), api.listResumes(), api.listVersions()])
      .then(([a, r, v]) => {
        setApps(a); setResumes(r); setVersions(v);
        if (!params.get("app") && a.length > 0) setAppId(a[0].id);
        setLoaded(true);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "load failed"));
  }, [params]);

  useEffect(() => {
    if (appId) {
      api.listVersions(appId).then(setVersions).catch(() => {});
    }
  }, [appId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setOut(null); setBusy(true);
    try {
      const payload = source.startsWith("v:")
        ? { resume_version_id: source.slice(2) }
        : { resume_id: source.slice(2) };
      setOut(await api.runAts(appId, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "ATS run failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return <Spinner />;
  if (error && apps.length === 0) return <ErrorBox message={error} />;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight">ATS Checker</h2>
        <p className="text-sm text-slate-500">Real computed score: 50% keywords · 25% skills · 15% experience · 10% formatting.</p>
      </div>
      <form onSubmit={submit} className="space-y-3 rounded-xl border bg-white p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Application">
            <select className={inputCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
              {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
            </select>
          </Field>
          <Field label="Resume / version">
            <select className={inputCls} value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="" disabled>Select…</option>
              <optgroup label="Master resumes">
                {resumes.map((r) => <option key={r.id} value={`r:${r.id}`}>{r.filename}</option>)}
              </optgroup>
              <optgroup label="Tailored versions">
                {versions.map((v) => <option key={v.id} value={`v:${v.id}`}>{v.label}</option>)}
              </optgroup>
            </select>
          </Field>
        </div>
        {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
        <button type="submit" disabled={busy || !appId || !source}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "Analyzing…" : "Run ATS check"}
        </button>
      </form>
      {out && (
        <div className="space-y-3 rounded-xl border bg-white p-5 text-sm">
          <p className="text-lg">Score: <ScoreBadge score={out.score} /> <span className="text-xs text-slate-400">{out.breakdown.methodology}</span></p>
          <p>Keyword match: {out.breakdown.keyword_match}% · Skills: {out.breakdown.skills_match}% · Experience: {out.breakdown.experience_match}% · Formatting: {out.breakdown.formatting_score}%</p>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="font-semibold">Matched skills</p>
              <p>{out.breakdown.skills_matched.join(", ") || "—"}</p>
            </div>
            <div className="rounded-lg bg-red-50 p-3">
              <p className="font-semibold">Missing skills</p>
              <p>{out.breakdown.skills_missing.join(", ") || "—"}</p>
            </div>
          </div>
          <div>
            <p className="font-semibold">Recommendations</p>
            <ul className="list-disc space-y-1 pl-5">
              {out.breakdown.recommendations.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Ats() {
  return (
    <Suspense fallback={<Spinner />}>
      <AtsInner />
    </Suspense>
  );
}

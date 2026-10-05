"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ErrorBox, Field, Spinner, inputCls } from "@/components/ui";
import { LabelTape, Letterhead, RubberStamp, TypedMemo } from "@/components/post/postal";
import { api } from "@/lib/api";
import type { Application, ATSBreakdown, Resume, ResumeVersion } from "@/types";

function verdict(score: number): { text: string; color: string } {
  if (score >= 75) return { text: "Approved", color: "#1E7B4D" };
  if (score >= 50) return { text: "Held for review", color: "#B7791F" };
  return { text: "Rejected", color: "#C8102E" };
}

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
    if (appId) api.listVersions(appId).then(setVersions).catch(() => {});
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
    <div className="mx-auto max-w-2xl space-y-5">
      <Letterhead title="Customs & Inspection" subtitle="ATS Checker · every parcel gets stamped" />
      <form onSubmit={submit} className="paper-keep space-y-3 rounded-sm border border-kraft/60 bg-envelope p-5 shadow-paper">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Parcel (application)">
            <select className={inputCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
              {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
            </select>
          </Field>
          <Field label="Contents (resume)">
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
        {error && <p className="font-mono text-sm text-postred">{error}</p>}
        <button type="submit" disabled={busy || !appId || !source}
          className="min-h-[44px] rounded-[4px] border-[3px] border-postalnavy px-5 py-1.5 font-mono text-sm font-bold uppercase tracking-[0.14em] text-postalnavy transition-transform active:scale-95 disabled:opacity-40">
          {busy ? "Inspecting…" : "Send through customs"}
        </button>
      </form>

      {out && (
        <div className="space-y-4" key={out.score}>
          <div className="paper-keep flex items-center justify-center gap-4 rounded-sm border border-kraft/60 bg-envelope p-6 shadow-paper">
            <RubberStamp text={verdict(out.score).text} color={verdict(out.score).color} size="lg" />
            <p className="font-serif text-5xl font-bold text-postalnavy">{out.score.toFixed(0)}</p>
          </div>
          <TypedMemo title={`Clearance form · ${out.breakdown.methodology}`}>
            <p>Keywords {out.breakdown.keyword_match}% · Skills {out.breakdown.skills_match}% · Experience {out.breakdown.experience_match}% · Formatting {out.breakdown.formatting_score}%</p>
            <p className="mt-2"><LabelTape>Cleared</LabelTape></p>
            <p>{out.breakdown.skills_matched.join(", ") || "—"}</p>
            <p className="mt-2 text-postred"><strong>HELD:</strong> {out.breakdown.skills_missing.join(", ") || "—"}</p>
            {out.breakdown.formatting_issues.length > 0 && (
              <p className="mt-2"><strong>Packaging faults:</strong> {out.breakdown.formatting_issues.join(" · ")}</p>
            )}
            <ul className="mt-2 list-none space-y-1">
              {out.breakdown.recommendations.map((r, i) => <li key={i}>☐ {r}</li>)}
            </ul>
          </TypedMemo>
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

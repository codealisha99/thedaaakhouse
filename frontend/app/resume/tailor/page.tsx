"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ErrorBox, Field, Spinner, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { Application, Resume } from "@/types";

function TailorInner() {
  const params = useSearchParams();
  const [apps, setApps] = useState<Application[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [appId, setAppId] = useState(params.get("app") ?? "");
  const [resumeId, setResumeId] = useState("");
  const [result, setResult] = useState<{ id: string } | null>(null);
  const [detail, setDetail] = useState<import("@/types").ResumeVersion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([api.listApps({}), api.listResumes()])
      .then(([a, r]) => {
        setApps(a); setResumes(r);
        if (!params.get("app") && a.length > 0) setAppId(a[0].id);
        if (r.length > 0) setResumeId(r[0].id);
        setLoaded(true);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "load failed"));
  }, [params]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setResult(null); setDetail(null); setBusy(true);
    try {
      const v = await api.tailor(appId, resumeId);
      setResult({ id: v.id });
      setDetail(await api.getVersion(v.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tailoring failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return <Spinner />;
  if (error && apps.length === 0) return <ErrorBox message={error} />;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h2 className="font-serif text-3xl font-bold tracking-tight text-postalnavy">Tailor Resume</h2>
        <p className="postal-copy font-hand text-xl italic text-postmark">The Tailoring Table</p>
        <p className="text-sm text-postmark">Extractive only — bullets are reordered by JD relevance, never rewritten. Missing terms are reported, not filled.</p>
      </div>
      <form onSubmit={submit} className="space-y-3 paper-keep rounded-sm border border-kraft/60 bg-envelope shadow-paper p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Application">
            <select className={inputCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
              {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
            </select>
          </Field>
          <Field label="Master resume">
            <select className={inputCls} value={resumeId} onChange={(e) => setResumeId(e.target.value)}>
              {resumes.map((r) => <option key={r.id} value={r.id}>{r.filename}</option>)}
            </select>
          </Field>
        </div>
        {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
        <button type="submit" disabled={busy || !appId || !resumeId}
          className="rounded-md bg-postred px-4 py-2 text-sm font-serif font-bold text-envelope disabled:opacity-40">
          {busy ? "Tailoring…" : "Create tailored version"}
        </button>
      </form>
      {result && detail && (
        <div className="space-y-3 paper-keep rounded-sm border border-kraft/60 bg-envelope shadow-paper p-5 text-sm">
          <p className="font-semibold text-emerald-700">Version created and attached to the application. <Link href={`/applications/${appId}`} className="underline">Open workspace →</Link></p>
          <h3 className="font-semibold">Optimization changes ({(detail.changes ?? []).length})</h3>
          <ul className="space-y-2">
            {(detail.changes ?? []).slice(0, 10).map((c, i) => (
              <li key={i} className="rounded-lg bg-slate-50 p-2.5">
                <p><code className="text-xs">{c.operation}</code> — {c.reason}</p>
                {c.target_requirement && <p className="text-xs text-postmark">JD requirement → {c.target_requirement}</p>}
                {c.source_evidence.length > 0 && <p className="text-xs text-postmark">Supported by: {c.source_evidence[0]}</p>}
              </li>
            ))}
          </ul>
          {(detail.missing_keywords ?? []).length > 0 && (
            <p className="text-amber-800">Missing from your profile (not added): {(detail.missing_keywords ?? []).slice(0, 8).join(", ")}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function Tailor() {
  return (
    <Suspense fallback={<Spinner />}>
      <TailorInner />
    </Suspense>
  );
}

"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorBox, Field, Spinner, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { Application, ApplicationDetail } from "@/types";

export default function CompanyResearch() {
  const [apps, setApps] = useState<Application[]>([]);
  const [appId, setAppId] = useState("");
  const [website, setWebsite] = useState("");
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.listApps({})
      .then((a) => { setApps(a); if (a.length > 0) setAppId(a[0].id); setLoaded(true); })
      .catch((e) => { setError(e instanceof Error ? e.message : "load failed"); setLoaded(true); });
  }, []);

  useEffect(() => {
    if (appId) api.getApp(appId).then(setDetail).catch(() => {});
  }, [appId]);

  async function run() {
    setBusy(true); setError(null);
    try {
      await api.runResearch(appId, website || undefined);
      setDetail(await api.getApp(appId));
      setWebsite("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Research failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return <Spinner />;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight">Company Research</h2>
        <p className="text-sm text-slate-500">Extracted from the real company page — every claim keeps its source.</p>
      </div>
      <div className="space-y-3 rounded-xl border bg-white p-5">
        <Field label="Application">
          <select className={inputCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
            {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
          </select>
        </Field>
        <div className="flex gap-2">
          <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://company.com"
            className={`${inputCls} flex-1`} />
          <button onClick={run} disabled={busy || !appId}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            {busy ? "Fetching…" : "Research"}
          </button>
        </div>
        {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
      </div>
      {(detail?.research ?? []).length === 0
        ? <EmptyState>No research for this application yet.</EmptyState>
        : (
          <div className="space-y-3">
            {(detail?.research ?? []).map((r) => (
              <div key={r.id} className="rounded-xl border bg-white p-5 text-sm">
                <p><strong>{r.name}</strong>{r.website ? <> · <a href={r.website} target="_blank" rel="noreferrer" className="text-violet-700 hover:underline">{r.website}</a></> : " · no URL given"}</p>
                {((r.profile.extracted_statements as string[]) ?? []).map((s, i) => <p key={i} className="mt-2 rounded-lg bg-slate-50 p-2.5">“{s}”</p>)}
                {((r.profile.technology_signals as string[]) ?? []).length > 0 && <p className="mt-2">Tech signals: {(r.profile.technology_signals as string[]).join(", ")}</p>}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

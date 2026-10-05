"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorBox, Field, Spinner, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { Application, ApplicationDetail } from "@/types";

export default function Interview() {
  const [apps, setApps] = useState<Application[]>([]);
  const [appId, setAppId] = useState("");
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
      await api.runPrep(appId);
      setDetail(await api.getApp(appId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return <Spinner />;
  const latest = detail?.interview_preps[0];

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight">Interview Prep</h2>
        <p className="text-sm text-slate-500">Derived from the application&apos;s JD — every question states its reason.</p>
      </div>
      <div className="flex gap-2 rounded-xl border bg-white p-5">
        <div className="flex-1">
          <Field label="Application">
            <select className={inputCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
              {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
            </select>
          </Field>
        </div>
        <button onClick={run} disabled={busy || !appId}
          className="self-end rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "Generating…" : "Generate"}
        </button>
      </div>
      {error && <ErrorBox message={error} />}
      {!latest ? <EmptyState>No prep plan for this application yet.</EmptyState> : (
        <div className="space-y-2 rounded-xl border bg-white p-5 text-sm">
          <p><strong>Topics:</strong> {latest.plan.topics.join(", ")}</p>
          {latest.plan.focus_areas.length > 0 && <p><strong>Focus:</strong> {latest.plan.focus_areas.join(", ")}</p>}
          <ol className="space-y-2">
            {latest.plan.questions.map((ques, i) => (
              <li key={i} className="rounded-lg border p-3">
                <p className="font-medium">{i + 1}. {ques.question}</p>
                <p className="mt-1 text-xs text-slate-500">{ques.category} · {ques.reason} · <em>{ques.source}</em></p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

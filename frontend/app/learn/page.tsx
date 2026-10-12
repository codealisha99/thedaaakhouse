"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Field, inputCls } from "@/components/ui";
import { Letterhead, TypedMemo, WaxSealButton } from "@/components/post/postal";
import { api } from "@/lib/api";
import type { Application, StudyPlanSummary } from "@/types";

export default function LearnHub() {
  const [apps, setApps] = useState<Application[]>([]);
  const [plans, setPlans] = useState<StudyPlanSummary[]>([]);
  const [appId, setAppId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.listApps({}), api.listPlans()])
      .then(([a, p]) => {
        setApps(a); setPlans(p);
        setAppId((current) => current || (a.length > 0 ? a[0].id : ""));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed."));
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setBusy(true);
    try {
      const plan = await api.createPlan(appId);
      setPlans([{
        id: plan.id, application_id: plan.application_id, title: plan.title,
        topics: plan.topics.length, mastered: 0, created_at: plan.created_at,
      }, ...plans]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Plan creation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Letterhead title="Learning Hub" subtitle="Study plans built from your JDs, tracked topic by topic" />
      <form onSubmit={create} className="flex gap-2 rounded-xl border bg-white p-4">
        <div className="flex-1">
          <Field label="Application">
            <select className={inputCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
              {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
            </select>
          </Field>
        </div>
        <button type="submit" disabled={busy || !appId}
          className="self-end rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "Building…" : "New plan"}
        </button>
      </form>
      {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
      {plans.length === 0
        ? <p className="rounded-xl border border-dashed bg-white p-6 text-sm text-slate-500">No study plans yet. Missing JD terms become lessons; known skills become revision.</p>
        : (
          <ul className="space-y-2">
            {plans.map((p) => (
              <li key={p.id} className="rounded-xl border bg-white p-4 text-sm">
                <Link href={`/learn/${p.id}`} className="font-semibold text-violet-700 hover:underline">{p.title}</Link>
                <p className="text-xs text-slate-500">{p.mastered}/{p.topics} topics mastered</p>
                <div className="mt-1 h-1.5 rounded bg-slate-100">
                  <div className="h-1.5 rounded bg-emerald-500" style={{ width: `${p.topics ? (100 * p.mastered) / p.topics : 0}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
      <TypedMemo title="How it works">
        <p>Each plan ranks missing JD terms first, links lessons to your real resume evidence, and checks answers against expected points — retry loops on what you miss.</p>
      </TypedMemo>
      <WaxSealButton href="/tracker">Back to tracker</WaxSealButton>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Button, EmptyState, ErrorState, Field, Label, LoadingBlock, PageHeader, Panel, PanelHeader, Tag, selectCls } from "@/components/ds";
import { StageBadge } from "@/components/route";
import { api } from "@/lib/api";
import type { Application, ApplicationDetail, InterviewPlan } from "@/types";

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

  if (!loaded) return <LoadingBlock rows={3} />;
  const latest = detail?.interview_preps[0];
  const selected = apps.find((a) => a.id === appId);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Interview"
        title="Interview prep"
        description="Derived from the application's job description. Every question states its reason."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[320px_1fr]">
        <Panel className="space-y-4 lg:sticky lg:top-6">
          <PanelHeader title="Application" meta="Generate a plan from its job description" />
          <Field label="Application">
            <select className={selectCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
              {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
            </select>
          </Field>
          {selected && <StageBadge status={selected.status} updatedAt={selected.updated_at} />}
          <Button variant="accent" className="w-full" onClick={run} disabled={busy || !appId}>
            {busy ? "Generating…" : "Generate plan"}
          </Button>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
        </Panel>
        <div>
          {!latest ? (
            <EmptyState title="No prep plan for this application yet" body="Generate one from the panel. Each question says why it exists." />
          ) : (
            <Panel>
              <PanelHeader title="Plan" meta={selected ? `${selected.company} · ${selected.role}` : undefined} />
              <PrepPlan plan={latest.plan} />
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

function PrepPlan({ plan }: { plan: InterviewPlan }) {
  return (
    <div className="space-y-5">
      <dl className="space-y-4 text-sm">
        <div>
          <dt className="mb-2"><Label>Topics</Label></dt>
          <dd className="flex flex-wrap gap-1.5">{plan.topics.map((t) => <Tag key={t}>{t}</Tag>)}</dd>
        </div>
        {plan.focus_areas.length > 0 && (
          <div>
            <dt className="mb-2"><Label>Focus</Label></dt>
            <dd className="flex flex-wrap gap-1.5">{plan.focus_areas.map((f) => <Tag key={f} tone="bad">{f}</Tag>)}</dd>
          </div>
        )}
      </dl>
      <ol className="stagger space-y-3">
        {plan.questions.map((q, i) => (
          <li key={i} className="rounded-md border border-line p-4">
            <p className="font-medium leading-snug text-ink">
              <span className="mr-2 font-mono text-ink-3 tabular">{String(i + 1).padStart(2, "0")}</span>
              {q.question}
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-3">{q.category} · {q.reason} · <em>{q.source}</em></p>
          </li>
        ))}
      </ol>
    </div>
  );
}

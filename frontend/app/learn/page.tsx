"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Button, EmptyState, Field, LinkButton, Meter, Notice, PageHeader, Panel, PanelHeader, cx, linkCls, selectCls,
} from "@/components/ds";
import { api } from "@/lib/api";
import type { Application, StudyPlanSummary } from "@/types";

const TOUCH_LINK = cx(linkCls, "inline-flex min-h-9 items-center");

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
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Learning"
        title="Learning hub"
        description="Study plans built from your job descriptions, tracked topic by topic."
        actions={<LinkButton href="/tracker" variant="secondary">Back to tracker</LinkButton>}
      />
      {error && <Notice tone="bad" className="mb-5">{error}</Notice>}
      <div className="grid items-start gap-5 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-5">
          <form onSubmit={create}>
            <Panel className="space-y-4">
              <PanelHeader title="New study plan" />
              <Field label="Application">
                <select className={selectCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
                  {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
                </select>
              </Field>
              <Button type="submit" variant="accent" busy={busy} disabled={!appId} className="w-full">
                {busy ? "Building…" : "New plan"}
              </Button>
            </Panel>
          </form>
          <Panel>
            <PanelHeader title="How it works" />
            <p className="text-[14px] leading-relaxed text-ink-2">
              Each plan ranks missing JD terms first, links lessons to your real resume evidence, and checks answers against expected points — retry loops on what you miss.
            </p>
          </Panel>
        </aside>
        <section aria-label="Study plans">
          {plans.length === 0 ? (
            <EmptyState title="No study plans yet" body="Missing JD terms become lessons; known skills become revision." />
          ) : (
            <Panel padded={false}>
              <ul className="stagger divide-y divide-line">
                {plans.map((p) => (
                  <li key={p.id} className="px-5 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <Link href={`/learn/${p.id}`} className={cx(TOUCH_LINK, "font-medium text-ink hover:text-brand")}>{p.title}</Link>
                      <span className="shrink-0 font-mono text-[13px] tabular text-ink-2">{p.mastered}/{p.topics}</span>
                    </div>
                    <Meter value={p.mastered} max={Math.max(p.topics, 1)} tone="ok" className="mt-3" label={`${p.title} mastery`} />
                    <p className="mt-2 text-[13px] text-ink-3">{p.mastered} of {p.topics} topics mastered</p>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </section>
      </div>
    </div>
  );
}

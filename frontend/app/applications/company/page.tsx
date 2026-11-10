"use client";

import { useEffect, useState } from "react";
import { Button, EmptyState, Field, Label, LoadingBlock, PageHeader, Panel, PanelHeader, Tag, inputCls, linkCls, selectCls } from "@/components/ds";
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

  if (!loaded) return <LoadingBlock rows={3} />;
  const research = detail?.research ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Company"
        title="Company research"
        description="Extracted from the real company page. Every claim keeps its source."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[320px_1fr]">
        <Panel className="space-y-4 lg:sticky lg:top-6">
          <PanelHeader title="Run research" meta="Fetches the website for the selected application" />
          <Field label="Application">
            <select className={selectCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
              {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
            </select>
          </Field>
          <Field label="Company website">
            <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://company.com" className={inputCls} />
          </Field>
          <Button variant="accent" className="w-full" onClick={run} disabled={busy || !appId}>
            {busy ? "Fetching…" : "Research"}
          </Button>
          {error && <p role="alert" className="rounded-md border border-bad/25 bg-bad/5 p-2.5 text-sm text-bad">{error}</p>}
        </Panel>
        <div className="space-y-4">
          {research.length === 0 ? (
            <EmptyState title="No research for this application yet" body="Enter a website and run research to pull findings from the page." />
          ) : research.map((r) => (
            <Panel key={r.id} className="space-y-4 text-sm">
              <p className="text-base font-medium text-ink">
                {r.name}
                {r.website
                  ? <> · <a href={r.website} target="_blank" rel="noreferrer" className={`break-all ${linkCls}`}>{r.website}</a></>
                  : <span className="font-normal text-ink-3"> · no URL given</span>}
              </p>
              {((r.profile.extracted_statements as string[] | undefined) ?? []).map((s, i) => (
                <blockquote key={i} className="border-l-2 border-line-strong pl-3 leading-relaxed text-ink-2">“{s}”</blockquote>
              ))}
              {((r.profile.technology_signals as string[] | undefined) ?? []).length > 0 && (
                <div>
                  <Label className="mb-2 block">Tech signals</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {(r.profile.technology_signals as string[]).map((t) => <Tag key={t}>{t}</Tag>)}
                  </div>
                </div>
              )}
            </Panel>
          ))}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Button, EmptyState, Field, Notice, PageHeader, Panel, PanelHeader, Tag, inputCls, selectCls } from "@/components/ds";
import { api } from "@/lib/api";

export default function Discovery() {
  const router = useRouter();
  const [sources, setSources] = useState<Awaited<ReturnType<typeof api.discoverySources>>>([]);
  const [jobs, setJobs] = useState<Awaited<ReturnType<typeof api.discoveryListings>>>([]);
  const [name, setName] = useState(""); const [url, setUrl] = useState("");
  const [adapter, setAdapter] = useState("greenhouse");
  const [search, setSearch] = useState(""); const [message, setMessage] = useState("");
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [taskId, setTaskId] = useState("");
  const load = useCallback(async () => { const [s, j] = await Promise.all([api.discoverySources(), api.discoveryListings()]); setSources(s); setJobs(j); }, []);
  useEffect(() => { load().catch(e => setError(e.message)); }, [load]);
  useEffect(() => {
    if (!taskId) return;
    const timer = setInterval(async () => {
      try {
        const t = await api.taskStatus(taskId);
        if (!["queued", "running"].includes(t.status)) {
          setTaskId(""); setMessage(`Scan ${t.status}. ${t.error_detail || ""}`); await load();
        }
      } catch (e) { setError(e instanceof Error ? e.message : "Could not check scan"); }
    }, 2500);
    return () => clearInterval(timer);
  }, [taskId, load]);
  async function act(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); await load(); } catch(e) { setError(e instanceof Error ? e.message : "Request failed"); } finally { setBusy(false); } }

  const visibleJobs = jobs.filter(j => `${j.company_name} ${j.title} ${j.location || ""}`.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Discovery"
        title="Discover company jobs"
        description="Refresh public Greenhouse, Lever, or structured company careers pages, then save vacancies to your tracker."
      />
      {error && <Notice tone="bad" className="mb-5">{error}</Notice>}
      {message && <Notice className="mb-5">{message}</Notice>}
      <div className="grid items-start gap-5 lg:grid-cols-[340px_1fr]">
        <div className="space-y-5">
          <form onSubmit={e => { e.preventDefault(); act(async () => { await api.discoveryCreate(name, adapter, url); setName(""); setUrl(""); setMessage("Source saved. Refresh it to import current jobs."); }); }}>
            <Panel className="space-y-4">
              <PanelHeader title="Add a job board" />
              <Field label="Company">
                <input required className={inputCls} value={name} onChange={e => setName(e.target.value)} />
              </Field>
              <Field label="Board type">
                <select className={selectCls} value={adapter} onChange={e => setAdapter(e.target.value)}>
                  <option value="greenhouse">Greenhouse</option>
                  <option value="lever">Lever</option>
                  <option value="company_careers">Company careers (JSON-LD)</option>
                </select>
              </Field>
              <Field label="Board URL">
                <input required type="url" className={inputCls} placeholder="https://boards.greenhouse.io/company" value={url} onChange={e => setUrl(e.target.value)} />
              </Field>
              <Button type="submit" variant="accent" busy={busy} className="w-full">Add source</Button>
            </Panel>
          </form>
          <Panel padded={false}>
            <div className="px-5 pt-5"><PanelHeader title="Sources" meta={`${sources.length} configured`} /></div>
            {sources.length === 0 ? (
              <p className="px-5 pb-5 text-[14px] text-ink-3">No sources yet.</p>
            ) : (
              <ul className="stagger divide-y divide-line">
                {sources.map(s => (
                  <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                    <div className="min-w-0">
                      <p className="font-medium text-ink">{s.name}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <Tag>{s.adapter}</Tag>
                        {s.consecutive_failures > 0 && <Badge tone="bad">{s.consecutive_failures} failed scans</Badge>}
                      </div>
                    </div>
                    <Button variant="secondary" disabled={busy || !!taskId} onClick={() => act(async () => { const t = await api.discoveryScan(s.id); setTaskId(t.task_id); setMessage("Scan queued. This page will update when it finishes."); })}>
                      Refresh jobs
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
        <section className="space-y-4">
          <Field label="Search imported jobs">
            <input type="search" className={inputCls} value={search} onChange={e => setSearch(e.target.value)} />
          </Field>
          {!jobs.length && (
            <EmptyState title="No jobs imported yet" body="Add a company board and refresh it." />
          )}
          <ul className="stagger space-y-3">
            {visibleJobs.map(j => (
              <li key={j.id}>
                <Panel as="article" className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-ink">{j.title}</h3>
                      {j.needs_review && <Badge tone="warn" dot>Needs review</Badge>}
                    </div>
                    <p className="mt-1 text-[14px] text-ink-2">{j.company_name} · {j.location || "Location unspecified"}</p>
                    {j.needs_review && <p className="mt-2 text-[13px] text-warn">Possible duplicate — review before applying</p>}
                  </div>
                  <Button variant="secondary" disabled={busy} onClick={() => act(async () => { const r = await api.discoverySave(j.id); router.push(`/applications/${r.application_id}`); })}>
                    Save to tracker
                  </Button>
                </Panel>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

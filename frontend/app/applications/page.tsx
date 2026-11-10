"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { EmptyState, ErrorState, LinkButton, LoadingBlock, PageHeader, Panel, PanelHeader, TrackingId, cx } from "@/components/ds";
import { StageBadge, StageDistribution, StageRoute } from "@/components/route";
import { STAGES, STATUS_LABEL, TERMINAL, daysSince, relativeDays, stageFor, type StageKey } from "@/lib/journey";
import { api } from "@/lib/api";
import type { Application } from "@/types";

const QUIET_AFTER_DAYS = 14;

type Attention = { app: Application; kind: "interview" | "next" | "quiet" | "resume"; text: string };

/** Derive what needs attention from real application fields only. */
function attentionItems(apps: Application[]): Attention[] {
  const out: Attention[] = [];
  for (const a of apps) {
    const stage = stageFor(a.status, a.updated_at);
    if (TERMINAL.includes(stage)) continue;
    if (a.interview_date) out.push({ app: a, kind: "interview", text: `Interview ${a.interview_date}` });
    else if (a.next_step) out.push({ app: a, kind: "next", text: a.next_step });
    else if (a.status !== "saved" && !a.resume_version_id) out.push({ app: a, kind: "resume", text: "No resume version attached" });
    else {
      const d = daysSince(a.updated_at);
      if (d != null && d >= QUIET_AFTER_DAYS) out.push({ app: a, kind: "quiet", text: `No movement for ${d} days` });
    }
  }
  const rank = { interview: 0, next: 1, resume: 2, quiet: 3 };
  return out.sort((x, y) => rank[x.kind] - rank[y.kind]);
}

type Event = { app: Application; from?: string; to: string; at: string };
function activity(apps: Application[], n = 8): Event[] {
  return apps
    .flatMap((app) => app.status_history.map((h) => ({ app, ...h })))
    .filter((e) => !Number.isNaN(new Date(e.at).getTime()))
    .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
    .slice(0, n);
}

const KIND_LABEL: Record<Attention["kind"], string> = { interview: "Interview", next: "Next step", resume: "Resume", quiet: "Going quiet" };
const KIND_DOT: Record<Attention["kind"], string> = { interview: "bg-accent", next: "bg-brand", resume: "bg-warn", quiet: "bg-ink-3" };

function AttentionList({ items }: { items: Attention[] }) {
  if (items.length === 0) {
    return <p className="rounded-md bg-sunken/60 px-4 py-6 text-center text-sm text-ink-2">Nothing waiting on you. Every live application has a resume and recent movement.</p>;
  }
  return (
    <ul className="stagger -mx-2">
      {items.slice(0, 7).map(({ app, kind, text }) => (
        <li key={`${app.id}-${kind}`}>
          <Link href={`/applications/${app.id}`} className="group flex items-start gap-3 rounded-md px-2 py-3 transition-colors hover:bg-sunken/70">
            <span className={cx("mt-[7px] size-2 shrink-0 rounded-full", KIND_DOT[kind])} aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
                <span className="font-medium text-ink">{app.company || "Untitled company"}</span>
                <span className="truncate text-ink-3">{app.role}</span>
              </p>
              <p className="mt-0.5 truncate text-[13px] text-ink-2"><span className="text-ink-3">{KIND_LABEL[kind]} · </span>{text}</p>
            </div>
            <span className="mt-0.5 text-ink-3 transition-transform group-hover:translate-x-0.5" aria-hidden="true">→</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ActivityStream({ events }: { events: Event[] }) {
  if (events.length === 0) return <p className="text-sm text-ink-3">Status changes will appear here.</p>;
  return (
    <ol className="relative space-y-4 before:absolute before:top-2 before:bottom-2 before:left-[5px] before:w-px before:bg-line">
      {events.map((e, i) => (
        <li key={`${e.app.id}-${e.at}-${i}`} className="relative pl-6">
          <span className="absolute top-1.5 left-0 size-[11px] rounded-full border-2 border-surface bg-ink-3" aria-hidden="true" />
          <p className="text-[13px] text-ink">
            <Link href={`/applications/${e.app.id}`} className="font-medium hover:underline">{e.app.company || e.app.role}</Link>
            <span className="text-ink-2"> {e.from ? `moved ${STATUS_LABEL[e.from] ?? e.from} → ` : "created as "}{STATUS_LABEL[e.to] ?? e.to}</span>
          </p>
          <p className="mt-0.5 font-mono text-[11px] text-ink-3">{relativeDays(e.at)}</p>
        </li>
      ))}
    </ol>
  );
}

function RecentRow({ app }: { app: Application }) {
  return (
    <li>
      <Link href={`/applications/${app.id}`} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-sunken/50 sm:grid-cols-[minmax(0,1fr)_120px_110px_64px]">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-ink">{app.role}</p>
          <p className="truncate text-[13px] text-ink-3">{app.company || "Untitled company"}{app.location ? ` · ${app.location}` : ""}</p>
        </div>
        <div className="hidden sm:block"><StageRoute compact status={app.status} updatedAt={app.updated_at} history={app.status_history} /></div>
        <div className="justify-self-end sm:justify-self-start"><StageBadge status={app.status} updatedAt={app.updated_at} /></div>
        <p className="hidden text-right font-mono text-[12px] tabular text-ink-3 sm:block">{app.ats_score != null ? app.ats_score.toFixed(0) : "—"}</p>
      </Link>
    </li>
  );
}

export default function Today() {
  const [apps, setApps] = useState<Application[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setState("loading");
    try { setApps(await api.listApps({ sort: "updated" })); setState("ready"); }
    catch (e) { setError(e instanceof Error ? e.message : "Couldn’t load applications."); setState("error"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const counts = useMemo(() => {
    const c = Object.fromEntries(STAGES.map((s) => [s.key, 0])) as Record<StageKey, number>;
    for (const a of apps) c[stageFor(a.status, a.updated_at)] += 1;
    return c;
  }, [apps]);
  const attention = useMemo(() => attentionItems(apps), [apps]);
  const events = useMemo(() => activity(apps), [apps]);
  const live = apps.length - counts.delivered - counts.return - counts.dead;
  const lead = apps[0];

  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });

  return (
    <div>
      <PageHeader
        eyebrow={today}
        title="Today"
        description={state === "ready" && apps.length > 0
          ? <><span className="font-mono tabular text-ink">{live}</span> live application{live === 1 ? "" : "s"}, <span className="font-mono tabular text-ink">{attention.length}</span> waiting on you.</>
          : "What needs attention across your job search."}
        actions={<><LinkButton href="/tracker" variant="secondary">Open tracker</LinkButton><LinkButton href="/applications/new" variant="accent">Add application</LinkButton></>}
      />

      {state === "loading" && <LoadingBlock rows={4} label="Loading applications" />}
      {state === "error" && <ErrorState message={error} onRetry={load} />}

      {state === "ready" && apps.length === 0 && (
        <EmptyState
          title="Your post house is empty"
          body="Add a job by pasting its description or URL. It’s analysed for skills, keywords and experience, then tracked from draft to offer."
          action={<><LinkButton href="/applications/new" variant="accent">Add your first application</LinkButton><LinkButton href="/discovery" variant="secondary">Discover jobs</LinkButton></>}
        />
      )}

      {state === "ready" && apps.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="min-w-0 space-y-6">
            <Panel>
              <PanelHeader title="Needs attention" meta="Interviews, next steps, missing resumes, and applications going quiet" />
              <AttentionList items={attention} />
            </Panel>

            <Panel>
              <PanelHeader title="Pipeline" meta={`${apps.length} applications across the route`} action={<Link href="/tracker" className="text-[13px] text-ink-3 hover:text-ink">Board →</Link>} />
              <StageDistribution counts={counts} />
            </Panel>

            <Panel padded={false} className="overflow-hidden">
              <div className="flex items-center justify-between px-5 pt-5 pb-3">
                <h3 className="text-[15px] font-semibold text-ink">Recently updated</h3>
                <span className="hidden font-mono text-[11px] uppercase tracking-[0.08em] text-ink-3 sm:block">ATS</span>
              </div>
              <ul className="divide-y divide-line border-t border-line">
                {apps.slice(0, 6).map((a) => <RecentRow key={a.id} app={a} />)}
              </ul>
            </Panel>
          </div>

          <aside className="space-y-6">
            {lead && (
              <Panel>
                <div className="flex items-center justify-between">
                  <TrackingId id={lead.id} />
                  <span className="font-mono text-[11px] text-ink-3">{relativeDays(lead.updated_at)}</span>
                </div>
                <p className="mt-3 font-display text-2xl leading-tight text-ink">{lead.role}</p>
                <p className="text-sm text-ink-2">{lead.company || "Untitled company"}</p>
                <div className="tear my-5" aria-hidden="true" />
                <StageRoute status={lead.status} updatedAt={lead.updated_at} history={lead.status_history} />
                <Link href={`/applications/${lead.id}`} className="mt-5 inline-block text-[13px] font-medium text-brand hover:underline">Open latest application →</Link>
              </Panel>
            )}
            <Panel>
              <PanelHeader title="Activity" />
              <ActivityStream events={events} />
            </Panel>
          </aside>
        </div>
      )}
    </div>
  );
}

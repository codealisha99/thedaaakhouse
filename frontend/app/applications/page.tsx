"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBox } from "@/components/ui";
import { Btn, Card, Chip, PageHeader, Skeleton, StatCard } from "@/components/retro";
import { pinFor, stageFor, stageOf } from "@/components/post/journey";
import { api } from "@/lib/api";
import type { Application } from "@/types";

function AppCard({ app }: { app: Application }) {
  const stage = stageOf(stageFor(app.status, app.updated_at));
  const skills = app.jd_analysis?.skills.slice(0, 3) ?? [];
  return (
    <Card lift className="flex flex-col p-4">
      <h4 className="font-pixel text-xl font-bold uppercase leading-tight text-green">{app.role}</h4>
      <p className="mt-1 font-mono text-sm">{app.company || "Untitled company"}</p>
      <ul className="mt-3 space-y-1.5 font-mono text-[13px] text-muted">
        <li>[team] {stage.title}</li>
        <li>[loc] {app.location || "—"}</li>
        <li>[date] {app.date_applied || app.date_saved || "—"}</li>
      </ul>
      {skills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {skills.map((s) => <Chip key={s}>{s}</Chip>)}
        </div>
      )}
      <div className="mt-3 border-t-2 border-green pt-2 font-mono text-xs font-bold uppercase">
        <Link href={`/applications/${app.id}`} className="underline hover:no-underline">
          Open ↗
        </Link>
        <span className="ml-3 text-muted">DH-{pinFor(app.id)}</span>
      </div>
    </Card>
  );
}

export default function Applications() {
  const [apps, setApps] = useState<Application[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    api.listApps({}).then((a) => { setApps(a); setState("ready"); })
      .catch((e) => { setError(e instanceof Error ? e.message : "load failed"); setState("error"); });
  }, []);

  const count = (stages: string[]) =>
    apps.filter((a) => stages.includes(stageFor(a.status, a.updated_at))).length;
  const followups = apps.filter((a) => a.next_step || a.interview_date).slice(0, 5);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        subtitle="Every application, one board."
        action={<Btn href="/applications/new">+ New application</Btn>}
      />

      {state === "loading" && <Skeleton />}
      {state === "error" && <ErrorBox message={error} />}

      {state === "ready" && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard n={count(["posted"])} label="Applied" href="/tracker" />
            <StatCard n={count(["transit"])} label="In Transit" href="/tracker" />
            <StatCard n={count(["out"])} label="Interviews" href="/tracker" />
            <StatCard n={count(["delivered"])} label="Offers" href="/tracker" />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-4 lg:col-span-2">
              <h3 className="font-pixel text-xl font-bold uppercase text-green">Recent applications</h3>
              {apps.length === 0 && <p className="font-mono text-sm text-muted">No applications yet.</p>}
              <div className="grid gap-4 sm:grid-cols-2">
                {apps.slice(0, 6).map((a) => <AppCard key={a.id} app={a} />)}
              </div>
            </div>
            <div>
              <h3 className="font-pixel text-xl font-bold uppercase text-green">Follow-ups due</h3>
              <Card className="mt-4 space-y-2 bg-sage p-4">
                {followups.length === 0 && (
                  <p className="font-mono text-sm text-muted">Nothing due. Board is clear.</p>
                )}
                {followups.map((a) => (
                  <Link key={a.id} href={`/applications/${a.id}`} className="block border-2 border-green bg-surface p-2 font-mono text-[13px] hover:bg-sage">
                    <strong>{a.company}</strong> — {a.next_step || `interview ${a.interview_date ?? ""}`}
                  </Link>
                ))}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

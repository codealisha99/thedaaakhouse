"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState, ErrorBox, ScoreBadge, Spinner, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import type { Application } from "@/types";

export default function Applications() {
  const [apps, setApps] = useState<Application[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    api.listApps({}).then((a) => { setApps(a); setState("ready"); })
      .catch((e) => { setError(e instanceof Error ? e.message : "load failed"); setState("error"); });
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Applications</h2>
          <p className="text-sm text-slate-500">Each application connects its JD, resume version, ATS, and prep.</p>
        </div>
        <Link href="/applications/new" className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white">
          + Analyze JD
        </Link>
      </div>
      {state === "loading" && <Spinner />}
      {state === "error" && <ErrorBox message={error} />}
      {state === "ready" && apps.length === 0 && (
        <EmptyState>No applications yet. Analyze a job description to create your first connected workspace.</EmptyState>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {apps.map((a) => (
          <Link key={a.id} href={`/applications/${a.id}`}
            className="rounded-xl border bg-white p-4 transition-shadow hover:shadow-md">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-semibold">{a.company || "Untitled company"}</p>
                <p className="truncate text-sm text-slate-500">{a.role}</p>
              </div>
              <ScoreBadge score={a.ats_score} />
            </div>
            <div className="mt-3 flex items-center justify-between">
              <StatusBadge status={a.status} />
              <span className="text-xs text-slate-400">
                {(a.jd_analysis?.skills.length ?? 0)} skills · {(a.jd_analysis?.responsibilities.length ?? 0)} duties
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

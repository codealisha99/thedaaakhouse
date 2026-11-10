"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  Button, EmptyState, ErrorState, Field, Label, LoadingBlock, Notice, PageHeader, Panel, PanelHeader,
  Tag, cx, linkCls, selectCls,
} from "@/components/ds";
import { api } from "@/lib/api";
import type { Application, ChangeOp, Resume, ResumeVersion } from "@/types";

const MAX_CHANGES_SHOWN = 10;

function TailorInner() {
  const params = useSearchParams();
  const [apps, setApps] = useState<Application[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [appId, setAppId] = useState(params.get("app") ?? "");
  const [resumeId, setResumeId] = useState("");
  const [result, setResult] = useState<{ id: string } | null>(null);
  const [detail, setDetail] = useState<ResumeVersion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([api.listApps({}), api.listResumes()])
      .then(([a, r]) => {
        setApps(a); setResumes(r);
        if (!params.get("app") && a.length > 0) setAppId(a[0].id);
        if (r.length > 0) setResumeId(r[0].id);
        setLoaded(true);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "load failed"));
  }, [params]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setResult(null); setDetail(null); setBusy(true);
    try {
      const v = await api.tailor(appId, resumeId);
      setResult({ id: v.id });
      setDetail(await api.getVersion(v.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tailoring failed.");
    } finally {
      setBusy(false);
    }
  }

  if (error && apps.length === 0) return <ErrorState message={error} />;
  if (!loaded) return <LoadingBlock rows={3} label="Loading applications" />;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Resume · Tailor"
        title="Tailor resume"
        description="Extractive only. Bullets are reordered by job-description relevance, never rewritten. Missing terms are reported, not filled in."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[340px_1fr]">
        <TailorForm
          apps={apps} resumes={resumes} appId={appId} resumeId={resumeId}
          busy={busy} error={error}
          onAppChange={setAppId} onResumeChange={setResumeId} onSubmit={submit}
        />
        {result && detail ? <TailorResult version={detail} appId={appId} /> : (
          <EmptyState title="No version yet" body="The result lists each change, the reason for it and the resume evidence behind it." />
        )}
      </div>
    </div>
  );
}

function TailorForm(p: {
  apps: Application[]; resumes: Resume[]; appId: string; resumeId: string; busy: boolean; error: string | null;
  onAppChange: (v: string) => void; onResumeChange: (v: string) => void; onSubmit: (e: React.FormEvent) => void;
}) {
  return (
    <form onSubmit={p.onSubmit} aria-label="Tailor settings" className="lg:sticky lg:top-6">
      <Panel className="space-y-4">
        <PanelHeader title="Source and target" meta="Creates a version attached to the application." />
        <Field label="Application">
          <select className={selectCls} value={p.appId} onChange={(e) => p.onAppChange(e.target.value)}>
            {p.apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
          </select>
        </Field>
        <Field label="Master resume">
          <select className={selectCls} value={p.resumeId} onChange={(e) => p.onResumeChange(e.target.value)}>
            {p.resumes.map((r) => <option key={r.id} value={r.id}>{r.filename}</option>)}
          </select>
        </Field>
        {p.error && <Notice tone="bad">{p.error}</Notice>}
        <Button type="submit" variant="accent" className="w-full" busy={p.busy} disabled={!p.appId || !p.resumeId}>
          {p.busy ? "Tailoring…" : "Create tailored version"}
        </Button>
      </Panel>
    </form>
  );
}

function TailorResult({ version, appId }: { version: ResumeVersion; appId: string }) {
  const changes = version.changes ?? [];
  const missing = version.missing_keywords ?? [];
  const shown = changes.slice(0, MAX_CHANGES_SHOWN);
  return (
    <div className="space-y-6">
      <Notice tone="ok">
        Version created and attached to the application.{" "}
        <Link href={`/applications/${appId}`} className={linkCls}>Open workspace →</Link>
      </Notice>

      <Panel>
        <PanelHeader
          title="Change operations"
          meta={`${changes.length} change${changes.length === 1 ? "" : "s"}${changes.length > MAX_CHANGES_SHOWN ? `, showing the first ${MAX_CHANGES_SHOWN}` : ""}`}
        />
        {shown.length === 0 ? (
          <p className="text-sm text-ink-3">No reordering was needed.</p>
        ) : (
          <ol className="stagger space-y-3">
            {shown.map((c, i) => <ChangeRow key={i} index={i + 1} change={c} />)}
          </ol>
        )}
      </Panel>

      {missing.length > 0 && (
        <Panel>
          <PanelHeader title="Missing from your profile" meta="Reported, not added. Your profile has no evidence for these terms." />
          <div className="flex flex-wrap gap-1.5">
            {missing.map((k) => <Tag key={k} tone="bad">{k}</Tag>)}
          </div>
        </Panel>
      )}
    </div>
  );
}

function ChangeRow({ index, change }: { index: number; change: ChangeOp }) {
  return (
    <li className="rounded-md border border-line p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] tabular text-ink-3">{String(index).padStart(2, "0")}</span>
        <Tag>{change.operation}</Tag>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-ink">{change.reason}</p>
      {change.target_requirement && (
        <p className="mt-2.5 text-[13px] text-ink-2">
          <Label className="mr-2">JD requirement</Label>
          {change.target_requirement}
        </p>
      )}
      {change.source_evidence.length > 0 && (
        <div className="mt-3">
          <Label>Source evidence</Label>
          <ul className="mt-1.5 space-y-1.5">
            {change.source_evidence.map((ev, j) => (
              <li key={j} className={cx("break-words border-l-2 border-ok bg-ok/8 py-1 pr-2 pl-3 font-mono text-[12px] leading-relaxed text-ink-2")}>
                {ev}
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}

export default function Tailor() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} label="Loading" />}>
      <TailorInner />
    </Suspense>
  );
}

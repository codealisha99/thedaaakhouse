"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  Badge, Button, EmptyState, ErrorState, Field, LoadingBlock, Meter, Notice, PageHeader, Panel, PanelHeader,
  Score, Tag, cx, scoreTone, selectCls,
} from "@/components/ds";
import { api } from "@/lib/api";
import type {
  Application, ATSBreakdown, AtsV2Breakdown, AtsV2Category, Resume, ResumeVersion,
} from "@/types";

type Requirement = AtsV2Breakdown["matched"][number];

/** Segment colours for the stacked contribution bar; tokens only. */
const SEGMENT_COLORS = ["var(--brand)", "var(--ok)", "var(--warn)", "var(--stage-out)", "var(--stage-posted)", "var(--ink-3)"];

function verdictText(score: number): string {
  return score >= 75 ? "Approved" : score >= 50 ? "Held for review" : "Rejected";
}

function AtsInner() {
  const params = useSearchParams();
  const [apps, setApps] = useState<Application[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [appId, setAppId] = useState(params.get("app") ?? "");
  const [source, setSource] = useState<string>(params.get("version") ? `v:${params.get("version")}` : "");
  const [out, setOut] = useState<{ score: number; breakdown: ATSBreakdown } | null>(null);
  const [out2, setOut2] = useState<{ score: number; breakdown: AtsV2Breakdown } | null>(null);
  const [detailed, setDetailed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([api.listApps({}), api.listResumes(), api.listVersions()])
      .then(([a, r, v]) => {
        setApps(a); setResumes(r); setVersions(v);
        if (!params.get("app") && a.length > 0) setAppId(a[0].id);
        setLoaded(true);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "load failed"));
  }, [params]);

  useEffect(() => {
    if (appId) api.listVersions(appId).then(setVersions).catch(() => {});
  }, [appId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setOut(null); setOut2(null); setBusy(true);
    try {
      const payload = source.startsWith("v:")
        ? { resume_version_id: source.slice(2) }
        : { resume_id: source.slice(2) };
      if (detailed) setOut2(await api.runAtsV2(appId, payload));
      else setOut(await api.runAts(appId, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "ATS run failed.");
    } finally {
      setBusy(false);
    }
  }

  if (error && apps.length === 0) return <ErrorState message={error} />;
  if (!loaded) return <LoadingBlock rows={3} label="Loading applications" />;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Resume · ATS"
        title="ATS check"
        description="Scores a resume against an application's job description. Every number shows how it was reached."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[340px_1fr]">
        <form onSubmit={submit} aria-label="ATS settings" className="lg:sticky lg:top-6">
          <Panel className="space-y-4">
            <PanelHeader title="Check a resume" meta="Pick the application and the resume to score." />
            <Field label="Application">
              <select className={selectCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
                {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
              </select>
            </Field>
            <Field label="Resume">
              <select className={selectCls} value={source} onChange={(e) => setSource(e.target.value)}>
                <option value="" disabled>Select…</option>
                <optgroup label="Master resumes">
                  {resumes.map((r) => <option key={r.id} value={`r:${r.id}`}>{r.filename}</option>)}
                </optgroup>
                <optgroup label="Tailored versions">
                  {versions.map((v) => <option key={v.id} value={`v:${v.id}`}>{v.label}</option>)}
                </optgroup>
              </select>
            </Field>
            <label className="flex cursor-pointer items-start gap-3 rounded-md border border-line p-3 text-sm">
              <input type="checkbox" checked={detailed} onChange={(e) => setDetailed(e.target.checked)}
                className="mt-0.5 size-4 shrink-0 accent-[var(--ink)]" />
              <span>
                <span className="block font-medium text-ink">Detailed scoring</span>
                <span className="block text-[13px] text-ink-3">Staged matching. Unknown categories are excluded and the rest renormalized.</span>
              </span>
            </label>
            {error && <Notice tone="bad">{error}</Notice>}
            <Button type="submit" variant="accent" className="w-full" busy={busy} disabled={!appId || !source}>
              {busy ? "Checking…" : "Run ATS check"}
            </Button>
          </Panel>
        </form>

        {out2 ? (
          <DetailedResult key={`v2-${out2.score}`} score={out2.score} b={out2.breakdown} />
        ) : out ? (
          <SummaryResult key={`v1-${out.score}`} score={out.score} b={out.breakdown} />
        ) : (
          <EmptyState title="No check run yet" body="The score breaks down into weighted categories, with matched and missing requirements and their evidence." />
        )}
      </div>
    </div>
  );
}

function ScoreHeader({ score, methodology }: { score: number; methodology: string }) {
  return (
    <Panel className="flex flex-wrap items-end justify-between gap-6">
      <div className="min-w-[200px]">
        <Score value={score} label="ATS score" />
      </div>
      <div className="min-w-0 max-w-sm text-right">
        <Badge tone={scoreTone(score)} dot>{verdictText(score)}</Badge>
        <p className="mt-3 break-words font-mono text-[11px] leading-relaxed text-ink-3">{methodology}</p>
      </div>
    </Panel>
  );
}

function DetailedResult({ score, b }: { score: number; b: AtsV2Breakdown }) {
  return (
    <div className="stagger space-y-6">
      <ScoreHeader score={score} methodology={b.methodology} />
      {b.blockers.length > 0 && (
        <Notice tone="bad">
          <p className="font-medium">Eligibility blockers (separate from the score)</p>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5">
            {b.blockers.map((x, i) => <li key={i}>{x}</li>)}
          </ul>
        </Notice>
      )}
      <CategoryBreakdown categories={b.categories} />
      <div className="grid gap-6 md:grid-cols-2">
        <RequirementPanel title="Matched" tone="ok" items={b.matched} empty="Nothing matched." />
        <RequirementPanel title="Missing" tone="bad" items={b.missing} empty="No missing requirements." />
      </div>
      <Recommendations items={b.recommendations} />
    </div>
  );
}

/** Weighted methodology: stacked contribution bar (sums to the score) and per-category rows. */
function CategoryBreakdown({ categories }: { categories: Record<string, AtsV2Category> }) {
  const entries = Object.entries(categories);
  const colorOf = (i: number) => SEGMENT_COLORS[i % SEGMENT_COLORS.length];
  const scored = entries.map(([name, c], i) => ({ name, c, color: colorOf(i) })).filter((x) => x.c.score != null);
  const total = scored.reduce((sum, x) => sum + (x.c.contribution ?? 0), 0);
  return (
    <Panel>
      <PanelHeader
        title="How the score is built"
        meta="Each category scores 0 to 100. Weight is its share of the total; contribution = score × weight."
      />
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-sunken" role="img"
        aria-label={`Contributions sum to ${total.toFixed(1)} points: ${scored.map((x) => `${x.name} ${x.c.contribution ?? 0}`).join(", ")}`}>
        {scored.map((x) => (
          <span key={x.name} title={x.name} className="h-full" style={{ width: `${x.c.contribution ?? 0}%`, background: x.color }} />
        ))}
      </div>
      <ul className="mt-4 divide-y divide-line">
        {entries.map(([name, c], i) => {
          const isScored = c.score != null;
          return (
            <li key={name} className="grid gap-x-4 gap-y-1.5 py-3 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_auto]">
              <div className="flex min-w-0 items-center gap-2">
                <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: isScored ? colorOf(i) : "transparent", boxShadow: isScored ? undefined : "inset 0 0 0 1px var(--line-strong)" }} aria-hidden="true" />
                <span className="truncate text-sm font-medium capitalize text-ink">{name}</span>
              </div>
              <p className="font-mono text-[12px] tabular text-ink-2 sm:text-right">
                {isScored
                  ? `${c.score}% × ${Math.round((c.weight ?? 0) * 100)}% = +${c.contribution ?? 0}`
                  : "excluded"}
              </p>
              {isScored && <Meter value={c.score ?? 0} max={100} className="sm:col-span-2" label={`${name} score`} />}
              <p className="break-words text-[13px] text-ink-3 sm:col-span-2">{c.detail}</p>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function RequirementPanel({ title, tone, items, empty }: {
  title: string; tone: "ok" | "bad"; items: Requirement[]; empty: string;
}) {
  return (
    <Panel>
      <PanelHeader title={title} meta={`${items.length} requirement${items.length === 1 ? "" : "s"}`} />
      {items.length === 0 ? <p className="text-sm text-ink-3">{empty}</p> : (
        <ul className="stagger space-y-2.5">
          {items.map((r, i) => (
            <li key={i} className={cx("rounded-md border-l-2 py-2 pr-2 pl-3", tone === "ok" ? "border-ok bg-ok/5" : "border-bad bg-bad/5")}>
              <p className="break-words text-sm font-medium text-ink">{r.requirement}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <Tag tone={tone}>{r.kind}</Tag>
                <span className="font-mono text-[11px] text-ink-3">{r.strength} · {r.priority}</span>
              </div>
              {r.evidence.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {r.evidence.map((ev, j) => <li key={j} className="break-words font-mono text-[12px] leading-relaxed text-ink-2">↳ {ev}</li>)}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Recommendations({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <Panel>
      <PanelHeader title="Recommendations" meta="Preferred misses lower the score slightly; they never fail a check." />
      <ul className="space-y-2.5">
        {items.map((r, i) => (
          <li key={i} className="flex items-start gap-2.5 text-sm leading-relaxed text-ink-2">
            <span className="mt-1 size-3.5 shrink-0 rounded-[3px] border border-line-strong" aria-hidden="true" />
            {r}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function SummaryResult({ score, b }: { score: number; b: ATSBreakdown }) {
  const parts = [
    { label: "Keywords", value: b.keyword_match },
    { label: "Skills", value: b.skills_match },
    { label: "Experience", value: b.experience_match },
    { label: "Formatting", value: b.formatting_score },
  ];
  return (
    <div className="stagger space-y-6">
      <ScoreHeader score={score} methodology={b.methodology} />
      <Panel>
        <PanelHeader title="Components" meta="Each part of the score, as a percentage." />
        <div className="space-y-4">
          {parts.map((p) => (
            <div key={p.label}>
              <div className="mb-1.5 flex items-baseline justify-between text-sm">
                <span className="text-ink-2">{p.label}</span>
                <span className="font-mono text-[12px] tabular text-ink">{p.value}%</span>
              </div>
              <Meter value={p.value} label={p.label} />
            </div>
          ))}
        </div>
      </Panel>
      <div className="grid gap-6 md:grid-cols-2">
        <TagPanel title="Skills matched" tone="ok" items={b.skills_matched} empty="None." />
        <TagPanel title="Skills missing" tone="bad" items={b.skills_missing} empty="None." />
      </div>
      {b.formatting_issues.length > 0 && (
        <Notice tone="warn">
          <p className="font-medium">Formatting issues</p>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5">
            {b.formatting_issues.map((x, i) => <li key={i}>{x}</li>)}
          </ul>
        </Notice>
      )}
      <Recommendations items={b.recommendations} />
    </div>
  );
}

function TagPanel({ title, tone, items, empty }: { title: string; tone: "ok" | "bad"; items: string[]; empty: string }) {
  return (
    <Panel>
      <PanelHeader title={title} meta={`${items.length} skill${items.length === 1 ? "" : "s"}`} />
      {items.length === 0 ? <p className="text-sm text-ink-3">{empty}</p> : (
        <div className="flex flex-wrap gap-1.5">
          {items.map((s) => <Tag key={s} tone={tone}>{s}</Tag>)}
        </div>
      )}
    </Panel>
  );
}

export default function Ats() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} label="Loading" />}>
      <AtsInner />
    </Suspense>
  );
}

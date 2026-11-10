"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import {
  Badge, Button, DefList, EmptyState, ErrorState, Field, Label, LinkButton, LoadingBlock, Meter, Notice,
  PageHeader, Panel, PanelHeader, Score, Tabs, Tag, Tone, TrackingId, cx, inputCls, linkCls, scoreTone, textareaCls,
} from "@/components/ds";
import { StageBadge, StageRoute, StatusSelect } from "@/components/route";
import { api } from "@/lib/api";
import { relativeDays, stageFor, stageOf } from "@/lib/journey";
import type { Application, ApplicationDetail, FitEvaluation, InterviewPlan, ResumeVersion } from "@/types";

const TABS = ["Overview", "Fit", "Job Description", "Company", "Resume", "ATS", "Interview"] as const;
type Tab = (typeof TABS)[number];
type Msg = { text: string; tone: "ok" | "bad" } | null;
type PatchFn = (p: Record<string, unknown>, note?: string) => Promise<void>;
type RunFn = <T>(fn: () => Promise<T>, note: string) => Promise<void>;
type Research = ApplicationDetail["research"][number];

export default function AppDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [tab, setTab] = useState<Tab>("Overview");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      setDetail(await api.getApp(id));
      setState("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
      setState("error");
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const patch: PatchFn = async (body, note) => {
    setBusy(true); setMsg(null);
    try {
      const updated = await api.patchApp(id, body as never);
      setDetail((d) => (d ? { ...d, application: { ...d.application, ...updated } } : d));
      setMsg({ text: note ?? "Saved.", tone: "ok" });
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : "Save failed.", tone: "bad" });
    } finally {
      setBusy(false);
    }
  };

  const run: RunFn = async (fn, note) => {
    setBusy(true); setMsg(null);
    try {
      await fn();
      await load();
      setMsg({ text: note, tone: "ok" });
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : "Operation failed.", tone: "bad" });
    } finally {
      setBusy(false);
    }
  };

  if (state === "loading") return <LoadingBlock rows={5} />;
  if (state === "error" || !detail) return <ErrorState message={error} onRetry={load} />;
  const a = detail.application;

  return (
    <div className="space-y-6">
      <AppHeader a={a} onStatus={(s) => patch({ status: s }, "Status updated.")} />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="Application sections" />
      <Panel key={tab} className="rise-in min-h-64">
        {tab === "Overview" && <OverviewTab detail={detail} patch={patch} />}
        {tab === "Fit" && <FitTab appId={id} run={run} busy={busy} />}
        {tab === "Job Description" && <JdTab detail={detail} />}
        {tab === "Company" && <CompanyTab appId={id} detail={detail} run={run} busy={busy} />}
        {tab === "Resume" && <ResumeTab appId={id} detail={detail} run={run} busy={busy} />}
        {tab === "ATS" && <AtsTab appId={id} detail={detail} run={run} busy={busy} />}
        {tab === "Interview" && <PrepTab appId={id} detail={detail} run={run} busy={busy} />}
      </Panel>
    </div>
  );
}

/* ---------- Header: route, identity, score, status ---------- */

function AtsChip({ score }: { score: number | null }) {
  return (
    <Badge tone={scoreTone(score)}>
      <span className="font-mono tabular">ATS {score == null ? "—" : score.toFixed(0)}</span>
    </Badge>
  );
}

function AppHeader({ a, onStatus }: { a: Application; onStatus: (s: string) => void }) {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Application"
        title={a.company || "Untitled"}
        description={
          <>
            {a.role}
            {a.location ? ` · ${a.location}` : ""}
            {a.job_url && (
              <>
                {" · "}
                <a href={a.job_url} target="_blank" rel="noreferrer" className={linkCls}>View posting ↗</a>
              </>
            )}
            <span className="mt-2 block"><TrackingId id={a.id} /></span>
          </>
        }
        actions={
          <>
            <AtsChip score={a.ats_score} />
            <StatusSelect value={a.status} onChange={onStatus} />
          </>
        }
      />
      <Panel>
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <StageBadge key={a.status} status={a.status} updatedAt={a.updated_at} stamp />
          {a.updated_at && <span className="font-mono text-[12px] text-ink-3">Last moved {relativeDays(a.updated_at)}</span>}
        </div>
        <StageRoute status={a.status} updatedAt={a.updated_at} history={a.status_history} />
      </Panel>
    </div>
  );
}

/* ---------- Overview: fields + vertical timeline ---------- */

function OverviewTab({ detail, patch }: { detail: ApplicationDetail; patch: PatchFn }) {
  const a = detail.application;
  const [notes, setNotes] = useState(a.notes);
  // Sync when the application (re)loads; blur-saves only on actual edits.
  useEffect(() => { setNotes(detail.application.notes); }, [detail.application.id, detail.application.notes]);
  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_300px]">
      <div className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Date saved"><input className={inputCls} type="date" defaultValue={a.date_saved ?? ""} onBlur={(e) => patch({ date_saved: e.target.value || null })} /></Field>
          <Field label="Date applied"><input className={inputCls} type="date" defaultValue={a.date_applied ?? ""} onBlur={(e) => patch({ date_applied: e.target.value || null })} /></Field>
          <Field label="Salary"><input className={inputCls} defaultValue={a.salary ?? ""} onBlur={(e) => patch({ salary: e.target.value || null })} /></Field>
          <Field label="Interview date"><input className={inputCls} defaultValue={a.interview_date ?? ""} placeholder="2026-10-20 10:00" onBlur={(e) => patch({ interview_date: e.target.value || null })} /></Field>
        </div>
        <Field label="Next step"><input className={inputCls} defaultValue={a.next_step ?? ""} onBlur={(e) => patch({ next_step: e.target.value || null })} /></Field>
        <Field label="Notes">
          <textarea className={textareaCls} value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={() => { if (notes !== a.notes) patch({ notes }); }} />
        </Field>
      </div>
      <aside className="space-y-6">
        <div>
          <PanelHeader title="Timeline" meta="Newest first" />
          <Timeline history={a.status_history} />
        </div>
        <DefList items={[
          { label: "Attached resume", value: detail.attached_version?.label ?? "none" },
          { label: "ATS runs", value: <span className="font-mono tabular">{detail.ats_history.length}</span> },
          { label: "Prep plans", value: <span className="font-mono tabular">{detail.interview_preps.length}</span> },
        ]} />
      </aside>
    </div>
  );
}

type HistoryItem = Application["status_history"][number];

function Timeline({ history }: { history: HistoryItem[] }) {
  if (history.length === 0) return <p className="text-sm text-ink-3">No events yet.</p>;
  return (
    <ol className="stagger relative space-y-5 border-l border-line-strong pl-5">
      {[...history].reverse().map((h, i) => {
        const color = stageOf(stageFor(h.to, null)).color;
        return (
          <li key={`${h.at}-${i}`} className="relative">
            <span aria-hidden="true" className="absolute -left-[25px] top-1.5 size-2.5 rounded-full border-2 border-surface"
              style={{ background: color, boxShadow: `0 0 0 1px ${color}` }} />
            <p className="flex flex-wrap items-center gap-1.5 text-sm">
              {h.from ? (
                <>
                  <StageBadge status={h.from} />
                  <span aria-hidden="true" className="text-ink-3">→</span>
                </>
              ) : <span className="text-ink-2">Created as</span>}
              <StageBadge status={h.to} />
            </p>
            <time dateTime={h.at} className="mt-1.5 block font-mono text-[12px] tabular text-ink-3">{new Date(h.at).toLocaleString()}</time>
          </li>
        );
      })}
    </ol>
  );
}

/* ---------- Job description ---------- */

function JdTab({ detail }: { detail: ApplicationDetail }) {
  const a = detail.application;
  const jd = a.jd_analysis;
  return (
    <div className="space-y-6">
      {!a.raw_jd && <EmptyState title="No job description saved" body="Edit this application from the Tracker to paste one." />}
      {jd && (
        <div className="grid gap-8 md:grid-cols-2">
          <div className="space-y-6">
            <section>
              <h3 className="mb-2 text-sm font-semibold">Required skills <span className="font-mono font-normal text-ink-3 tabular">({jd.skills.length})</span></h3>
              <div className="flex flex-wrap gap-1.5">{jd.skills.map((s) => <Tag key={s}>{s}</Tag>)}</div>
            </section>
            <section>
              <h3 className="mb-2 text-sm font-semibold">Top keywords</h3>
              <div className="flex flex-wrap gap-1.5">
                {jd.keywords.slice(0, 20).map((k) => <Tag key={k.term}>{k.term} ×{k.count}</Tag>)}
              </div>
            </section>
            {jd.experience_years != null && (
              <p className="text-sm text-ink-2">Experience required: <strong className="font-mono text-ink tabular">{jd.experience_years}+ years</strong></p>
            )}
          </div>
          <section>
            <h3 className="mb-2 text-sm font-semibold">Responsibilities</h3>
            <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-ink-2">
              {jd.responsibilities.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </section>
        </div>
      )}
      {a.raw_jd && (
        <details className="rounded-md border border-line bg-sunken/50 p-4">
          <summary className={cx("cursor-pointer text-sm", linkCls)}>Raw job description ({a.raw_jd.length} chars)</summary>
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-ink-2">{a.raw_jd}</pre>
        </details>
      )}
    </div>
  );
}

/* ---------- Company research ---------- */

function ResearchSummary({ r }: { r: Research }) {
  const statements = (r.profile.extracted_statements as string[] | undefined) ?? [];
  const tech = (r.profile.technology_signals as string[] | undefined) ?? [];
  return (
    <div className="space-y-4 text-sm">
      <p className="text-base font-medium text-ink">
        {r.name}
        {r.website && <> · <a href={r.website} target="_blank" rel="noreferrer" className={cx("break-all", linkCls)}>{r.website}</a></>}
      </p>
      {statements.map((s, i) => (
        <blockquote key={i} className="border-l-2 border-line-strong pl-3 leading-relaxed text-ink-2">“{s}”</blockquote>
      ))}
      {tech.length > 0 && (
        <div>
          <Label className="mb-2 block">Tech signals</Label>
          <div className="flex flex-wrap gap-1.5">{tech.map((t) => <Tag key={t}>{t}</Tag>)}</div>
        </div>
      )}
      <p className="break-words text-[12px] text-ink-3">Sources: {r.sources.map((s) => s.source_url).join(", ") || "none recorded"}</p>
    </div>
  );
}

function CompanyTab({ appId, detail, run, busy }: {
  appId: string; detail: ApplicationDetail; run: RunFn; busy: boolean;
}) {
  const [website, setWebsite] = useState("");
  const latest = detail.research[0];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Company website" className="min-w-0 flex-1 basis-64">
          <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://company.com (optional)" className={inputCls} />
        </Field>
        <Button variant="accent" disabled={busy} onClick={() => run(() => api.runResearch(appId, website || undefined), "Research saved.")}>
          Run research
        </Button>
      </div>
      {!latest && <EmptyState title="No research yet" body="Paste the company website and run it. Findings are extracted from the real page, with sources." />}
      {latest && <ResearchSummary r={latest} />}
    </div>
  );
}

/* ---------- Resume versions ---------- */

function ResumeTab({ appId, detail, run, busy }: {
  appId: string; detail: ApplicationDetail; run: RunFn; busy: boolean;
}) {
  const attachedId = detail.application.resume_version_id;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-2">Attached version: <strong className="text-ink">{detail.attached_version?.label ?? "none"}</strong></p>
        <LinkButton href={`/resume/tailor?app=${appId}`} variant="accent">Tailor a resume for this JD →</LinkButton>
      </div>
      {detail.versions.length === 0 ? (
        <EmptyState title="No tailored versions yet" body="Tailor a resume for this job description, then attach it here." />
      ) : (
        <ul className="stagger divide-y divide-line rounded-md border border-line">
          {detail.versions.map((v) => (
            <VersionRow key={v.id} v={v} attached={attachedId === v.id} appId={appId} run={run} busy={busy} />
          ))}
        </ul>
      )}
    </div>
  );
}

function VersionRow({ v, attached, appId, run, busy }: {
  v: ResumeVersion; attached: boolean; appId: string; run: RunFn; busy: boolean;
}) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5">
      <div className="min-w-0 space-y-2">
        <p className="flex flex-wrap items-center gap-2 font-medium">
          <Link href={`/resume/versions/${v.id}`} className={linkCls}>{v.label}</Link>
          {attached && <Badge tone="brand">Attached</Badge>}
        </p>
        <p className="font-mono text-[12px] text-ink-3 tabular">ATS before {v.ats_score ?? "—"}</p>
        <div className="flex flex-wrap gap-1.5">
          {v.missing_keywords.length === 0
            ? <span className="text-[12px] text-ink-3">No missing keywords</span>
            : v.missing_keywords.slice(0, 5).map((k) => <Tag key={k} tone="bad">{k}</Tag>)}
        </div>
      </div>
      <div className="flex shrink-0 gap-2">
        {!attached && (
          <Button variant="secondary" disabled={busy} onClick={() => run(() => api.attachVersion(appId, v.id), "Version attached.")}>Attach</Button>
        )}
        <LinkButton href={`/resume/ats?app=${appId}&version=${v.id}`} variant="secondary">Check ATS</LinkButton>
      </div>
    </li>
  );
}

/* ---------- ATS ---------- */

function TagGroup({ title, items, tone }: { title: string; items: string[]; tone: "ok" | "bad" }) {
  return (
    <section>
      <h4 className="mb-2 text-sm font-semibold">{title}</h4>
      {items.length === 0
        ? <p className="text-sm text-ink-3">None</p>
        : <div className="flex flex-wrap gap-1.5">{items.map((s) => <Tag key={s} tone={tone}>{s}</Tag>)}</div>}
    </section>
  );
}

function AtsTab({ appId, detail, run, busy }: {
  appId: string; detail: ApplicationDetail; run: RunFn; busy: boolean;
}) {
  const latest = detail.ats_history[0];
  const hasResume = Boolean(detail.application.resume_version_id);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-3">{hasResume ? "Scores the attached resume against this job description." : "Attach a resume version first (Resume tab)."}</p>
        <Button variant="accent" disabled={busy || !hasResume} onClick={() => run(() => api.runAts(appId, {}), "ATS analysis complete.")}>
          Run ATS on attached resume
        </Button>
      </div>
      {detail.ats_history.length === 0 && <EmptyState title="No ATS runs yet" body="Run ATS on the attached resume to see matched and missing skills." />}
      {latest && (
        <div className="grid gap-8 lg:grid-cols-[260px_1fr]">
          <Score value={latest.score} label="ATS score" caption={latest.breakdown.methodology} />
          <div className="space-y-6">
            <div className="grid gap-6 sm:grid-cols-2">
              <TagGroup title={`Matched (${latest.breakdown.skills_matched.length})`} items={latest.breakdown.skills_matched} tone="ok" />
              <TagGroup title={`Missing (${latest.breakdown.skills_missing.length})`} items={latest.breakdown.skills_missing} tone="bad" />
            </div>
            {latest.breakdown.formatting_issues.length > 0 && (
              <Notice tone="warn">Formatting issues: {latest.breakdown.formatting_issues.join(" · ")}</Notice>
            )}
            <section>
              <h4 className="mb-2 text-sm font-semibold">Recommendations</h4>
              <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-ink-2">
                {latest.breakdown.recommendations.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Interview prep ---------- */

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
            <dt className="mb-2"><Label>Focus (missing from your resume)</Label></dt>
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

function PrepTab({ appId, detail, run, busy }: {
  appId: string; detail: ApplicationDetail; run: RunFn; busy: boolean;
}) {
  const latest = detail.interview_preps[0];
  return (
    <div className="space-y-5">
      <Button variant="accent" disabled={busy} onClick={() => run(() => api.runPrep(appId), "Interview plan generated.")}>
        Generate interview plan
      </Button>
      {!latest && <EmptyState title="No prep plan yet" body="Generated from this JD. Each question says why it exists." />}
      {latest && <PrepPlan plan={latest.plan} />}
    </div>
  );
}

/* ---------- Fit ---------- */

const FIT_TONE: Record<FitEvaluation["classification"], Tone> = {
  target: "ok", adjacent: "brand", poor: "bad", needs_review: "warn",
};
const FIT_CLASSES = ["target", "adjacent", "poor", "needs_review"] as const;

function FitTab({ appId, run, busy }: { appId: string; run: RunFn; busy: boolean }) {
  const [evals, setEvals] = useState<FitEvaluation[]>([]);
  const [state, setState] = useState<"loading" | "ready">("loading");

  const load = useCallback(async () => {
    try {
      setEvals(await api.fitHistory(appId));
    } catch { /* shown as empty with retry below */ }
    setState("ready");
  }, [appId]);

  useEffect(() => { load(); }, [load]);
  const latest = evals[0];

  async function evaluate() {
    await run(async () => {
      const e = await api.evaluateFit(appId);
      setEvals(await api.fitHistory(appId));
      return e;
    }, "Fit evaluation complete.");
  }

  async function override(evaluationId: string, classification: string) {
    await run(async () => {
      await api.overrideFit(evaluationId, classification);
      setEvals(await api.fitHistory(appId));
    }, "Override recorded. Scoring rules unchanged.");
  }

  if (state === "loading") return <LoadingBlock rows={3} />;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="accent" disabled={busy} onClick={evaluate}>Evaluate career fit</Button>
        <LinkButton href="/profile" variant="ghost">Edit career profile →</LinkButton>
      </div>
      {!latest && <EmptyState title="No fit evaluation yet" body="Scored against your career profile, with reasons." />}
      {latest && (
        <FitResult e={latest} count={evals.length} busy={busy} onOverride={(c) => override(latest.id, c)} />
      )}
    </div>
  );
}

function FitResult({ e, count, busy, onOverride }: {
  e: FitEvaluation; count: number; busy: boolean; onOverride: (c: string) => void;
}) {
  return (
    <div className="grid gap-8 lg:grid-cols-[260px_1fr]">
      <div className="space-y-6">
        <Score value={e.score * 100} label="Career fit" caption={e.recommendation} />
        <div className="space-y-3">
          <Label className="block">Classification</Label>
          <Badge tone={FIT_TONE[e.classification]} className="capitalize">
            {e.classification.replace("_", " ")}{e.overridden ? " (override)" : ""}
          </Badge>
        </div>
        <div className="space-y-2">
          <Label className="block">Override</Label>
          <div className="flex flex-wrap gap-2">
            {FIT_CLASSES.map((c) => (
              <Button key={c} variant="secondary" size="sm" disabled={busy} onClick={() => onOverride(c)} className="capitalize">
                {c.replace("_", " ")}
              </Button>
            ))}
          </div>
        </div>
        {count > 1 && <p className="text-[12px] text-ink-3">{count} evaluations in history (latest shown).</p>}
      </div>
      <div className="space-y-6">
        <FactorList factors={e.factors} />
        {e.reasons.length > 0 && <BulletSection title="Why" items={e.reasons} />}
        {e.gaps.length > 0 && <BulletSection title="Gaps" items={e.gaps.slice(0, 8)} />}
        {e.conflicts.length > 0 && (
          <Notice tone="warn">
            <p className="font-semibold text-ink">Conflicts</p>
            <ul className="mt-1.5 list-disc pl-5">{e.conflicts.map((r, i) => <li key={i}>{r}</li>)}</ul>
          </Notice>
        )}
        {e.unknown.length > 0 && (
          <div>
            <Label className="mb-2 block">Unknown</Label>
            <div className="flex flex-wrap gap-1.5">{e.unknown.map((u) => <Tag key={u}>{u}</Tag>)}</div>
          </div>
        )}
      </div>
    </div>
  );
}

function FactorList({ factors }: { factors: Record<string, number> }) {
  const entries = Object.entries(factors);
  if (entries.length === 0) return null;
  return (
    <section>
      <h4 className="mb-3 text-sm font-semibold">Factors</h4>
      <ul className="space-y-3.5">
        {entries.map(([k, v]) => {
          const pct = Number(v) * 100;
          const name = k.replace(/_/g, " ");
          return (
            <li key={k}>
              <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
                <span className="text-ink-2">{name}</span>
                <span className="font-mono tabular text-ink">{pct.toFixed(0)}%</span>
              </div>
              <Meter value={pct} label={name} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function BulletSection({ title, items }: { title: string; items: string[] }) {
  return (
    <section>
      <h4 className="mb-2 text-sm font-semibold">{title}</h4>
      <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-ink-2">
        {items.map((r, i) => <li key={i}>{r}</li>)}
      </ul>
    </section>
  );
}

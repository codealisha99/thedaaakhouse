"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Field, Label, Notice, PageHeader, Panel, cx, inputCls, textareaCls } from "@/components/ds";
import { api } from "@/lib/api";

type Phase = "idle" | "reading" | "filed";

const STEPS = [
  { key: "skills", label: "Required skills" },
  { key: "keywords", label: "Weighted keywords" },
  { key: "duties", label: "Responsibilities" },
  { key: "years", label: "Experience required" },
];

/** What the analyzer extracts, shown as a live checklist while it runs. */
function ExtractionPreview({ phase, hasUrl }: { phase: Phase; hasUrl: boolean }) {
  return (
    <Panel className="lg:sticky lg:top-10">
      <Label>What happens next</Label>
      <ol className="mt-4 space-y-3.5">
        {hasUrl && (
          <li className="flex items-center gap-3 text-sm">
            <StepDot done={phase !== "idle"} active={phase === "reading"} />
            <span className={phase === "idle" ? "text-ink-2" : "text-ink"}>Fetch the posting (private addresses are blocked)</span>
          </li>
        )}
        {STEPS.map((s, i) => (
          <li key={s.key} className="flex items-center gap-3 text-sm">
            <StepDot done={phase === "filed"} active={phase === "reading"} delay={i * 120} />
            <span className={phase === "idle" ? "text-ink-2" : "text-ink"}>{s.label}</span>
          </li>
        ))}
        <li className="flex items-center gap-3 text-sm">
          <StepDot done={phase === "filed"} />
          <span className={phase === "filed" ? "font-medium text-ink" : "text-ink-2"}>Filed as Drafted on your tracker</span>
        </li>
      </ol>
      <div className="tear my-5" aria-hidden="true" />
      <p className="text-[13px] leading-relaxed text-ink-3">
        Extraction reads only the text you provide. Nothing is added that isn’t in the job description.
      </p>
    </Panel>
  );
}

function StepDot({ done, active, delay = 0 }: { done?: boolean; active?: boolean; delay?: number }) {
  return (
    <span aria-hidden="true" style={{ transitionDelay: `${delay}ms` }}
      className={cx("flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors duration-300",
        done ? "border-ok bg-ok text-surface" : active ? "animate-pulse border-accent bg-accent/15" : "border-line-strong")}>
      {done && <svg className="size-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="m2.5 6.5 2.5 2.5 4.5-5" /></svg>}
    </span>
  );
}

export default function AddApplication() {
  const router = useRouter();
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("");
  const [jobUrl, setJobUrl] = useState("");
  const [jd, setJd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [seeding, setSeeding] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const url = jobUrl.trim();
    if (!jd.trim() && !url) { setError("Paste a job description or provide a job URL."); return; }
    setPhase("reading");
    try {
      const app = url && !jd.trim()
        ? await api.createFromUrl({ url, company: company || undefined, role: role || undefined, location: location || undefined })
        : await api.createApp({
            company, role: role || "Untitled role", location: location || undefined,
            job_url: url || undefined, raw_jd: jd, status: "saved",
            date_saved: new Date().toISOString().slice(0, 10),
          });
      setPhase("filed");
      setTimeout(() => router.push(`/applications/${app.id}`), 700);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
      setPhase("idle");
    }
  }

  async function seed() {
    setError(null); setSeeding(true);
    try {
      const out = await api.seedNexora();
      router.push(`/applications/${out.application_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Seed failed.");
    } finally { setSeeding(false); }
  }

  const words = jd.trim() ? jd.trim().split(/\s+/).length : 0;

  return (
    <div>
      <PageHeader eyebrow="Desk" title="Add application"
        description="Paste the job description, or give just the posting URL and it will be fetched. Either way it’s analysed and filed on your tracker." />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <form onSubmit={submit} className="space-y-5" noValidate>
          <Panel className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Company"><input className={inputCls} value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme" autoComplete="organization" /></Field>
              <Field label="Role"><input className={inputCls} value={role} onChange={(e) => setRole(e.target.value)} placeholder="AI Engineer" /></Field>
              <Field label="Location"><input className={inputCls} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Remote" /></Field>
              <Field label="Job URL" hint="With no description pasted, the posting is fetched from this URL.">
                <input className={inputCls} type="url" inputMode="url" value={jobUrl} onChange={(e) => setJobUrl(e.target.value)} placeholder="https://…" />
              </Field>
            </div>
            <Field label="Job description" hint={words > 0 ? <span className="font-mono tabular">{words} words</span> : "Paste the full text for the best extraction."}>
              <textarea className={cx(textareaCls, "min-h-72 font-mono text-[13px]")} value={jd} onChange={(e) => setJd(e.target.value)}
                placeholder="Paste the full job description…" aria-invalid={Boolean(error) && !jd.trim() && !jobUrl.trim()} />
            </Field>
            {error && <Notice tone="bad">{error}</Notice>}
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button type="submit" variant="accent" size="lg" busy={phase === "reading"} disabled={phase === "filed"}>
                {phase === "reading" ? "Analysing…" : phase === "filed" ? "Filed — opening…" : "Analyse and file"}
              </Button>
              <span className="text-[13px] text-ink-3">Takes a few seconds.</span>
            </div>
          </Panel>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-dashed border-line-strong px-5 py-4">
            <div>
              <p className="text-sm font-medium text-ink">Just exploring?</p>
              <p className="text-[13px] text-ink-3">Load Nexora AI Labs, a fictional sample job from the development seed.</p>
            </div>
            <Button variant="secondary" size="sm" onClick={seed} busy={seeding}>Load sample job</Button>
          </div>
        </form>

        <ExtractionPreview phase={phase} hasUrl={Boolean(jobUrl.trim()) && !jd.trim()} />
      </div>
    </div>
  );
}

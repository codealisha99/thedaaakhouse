"use client";

import { useState } from "react";
import { Label, Meter, Tag, cx } from "@/components/ds";

/*
 * Illustrative product compositions for the landing page. They render the same
 * structures the app produces (route, ATS breakdown, change ops, prep questions,
 * approval flow) with a fictional company — Nexora AI Labs is also the app's
 * development seed — and every one is labelled as an example.
 */

export function ExampleTag() {
  return <span className="rounded-full border border-line-strong px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">Example</span>;
}

const HERO_STOPS = [
  { key: "Drafted", detail: "JD analysed: 14 skills, 32 keywords, 4+ years", when: "Mar 02" },
  { key: "Posted", detail: "Sent with “ML Platform v3” · ATS 82", when: "Mar 04" },
  { key: "In transit", detail: "Online assessment received", when: "Mar 11" },
  { key: "Out for delivery", detail: "Interview Thu 10:00 · 12 prep questions ready", when: "Mar 18" },
  { key: "Delivered", detail: "Offer", when: "—" },
];

/** Hero: a tracking slip. Stops are buttons so visitors can step through the route. */
export function TrackingSlip() {
  const [at, setAt] = useState(3);
  const stop = HERO_STOPS[at];
  return (
    <div className="relative">
      <div className="absolute -inset-x-6 -inset-y-8 -z-10 rounded-[28px] bg-sunken/70 sm:-inset-x-10" aria-hidden="true" />
      <article className="rise-in rounded-2xl border border-line bg-surface shadow-pop">
        <div className="flex items-center justify-between px-6 pt-5">
          <span className="font-mono text-[12px] tracking-wide text-ink-3">DH-4F2A91</span>
          <ExampleTag />
        </div>
        <div className="px-6 pt-4 pb-5">
          <p className="font-display text-[30px] leading-tight text-ink">Machine Learning Engineer</p>
          <p className="text-sm text-ink-2">Nexora AI Labs · Remote</p>
        </div>
        <div className="tear mx-6" aria-hidden="true" />
        <div className="px-6 pt-6 pb-2">
          <ol className="relative flex justify-between" aria-label="Example route — select a stop">
            <span className="absolute inset-x-2 top-[9px] h-px bg-line-strong" aria-hidden="true" />
            <span className="absolute left-2 top-[9px] h-px bg-ink transition-[width] duration-500 ease-[var(--ease-in-out)]" style={{ width: `calc((100% - 16px) * ${at / 4})` }} aria-hidden="true" />
            {HERO_STOPS.map((s, i) => (
              <li key={s.key} className="relative z-10">
                <button onClick={() => setAt(i)} aria-pressed={i === at} aria-label={s.key}
                  className="group -m-2 flex flex-col items-center p-2">
                  <span className={cx("block size-[19px] rounded-full border-2 transition-all duration-300",
                    i < at ? "border-ink bg-ink" : i === at ? "scale-110 border-accent bg-surface ring-4 ring-accent/15" : "border-line-strong bg-surface group-hover:border-ink-3")}>
                    {i === at && <span className="m-[3px] block size-[9px] rounded-full bg-accent" />}
                  </span>
                </button>
              </li>
            ))}
          </ol>
          <div className="mt-1 flex justify-between text-[11px] text-ink-3" aria-hidden="true">
            <span>Drafted</span><span>Delivered</span>
          </div>
        </div>
        <div className="mx-6 mt-4 mb-6 flex items-start justify-between gap-4 rounded-lg bg-sunken/70 px-4 py-3.5" aria-live="polite">
          <div className="min-w-0">
            <p className="text-sm font-medium text-ink">{stop.key}</p>
            <p className="mt-0.5 text-[13px] text-ink-2">{stop.detail}</p>
          </div>
          <span className="shrink-0 font-mono text-[12px] text-ink-3">{stop.when}</span>
        </div>
        <div className="grid grid-cols-3 border-t border-line text-center">
          {[["ATS", "82"], ["Fit", "Target"], ["Prep", "12 Qs"]].map(([k, v]) => (
            <div key={k} className="border-line py-3.5 [&+&]:border-l">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-3">{k}</p>
              <p className="mt-0.5 font-mono text-[15px] tabular text-ink">{v}</p>
            </div>
          ))}
        </div>
      </article>
      <div className="stamp absolute -top-5 -right-2 hidden rounded-md border-[2.5px] border-accent bg-bg/80 px-2.5 py-1 font-mono text-[12px] font-semibold uppercase tracking-[0.14em] text-accent sm:block" aria-hidden="true">
        Out for delivery
      </div>
    </div>
  );
}

/** Before/after of an extractive tailor: same bullets, new order, each move carries evidence. */
export function TailorDemo() {
  const [after, setAfter] = useState(true);
  const before = [
    "Led migration of nightly ETL jobs to Airflow",
    "Built internal dashboard for model metrics",
    "Deployed PyTorch inference services on Kubernetes",
    "Mentored two junior engineers",
  ];
  const order = after ? [2, 0, 1, 3] : [0, 1, 2, 3];
  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-2 sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div role="radiogroup" aria-label="Show resume" className="inline-flex rounded-md border border-line-strong bg-sunken p-0.5 text-[13px]">
          {[["Original", false], ["Tailored", true]].map(([l, v]) => (
            <button key={String(l)} role="radio" aria-checked={after === v} onClick={() => setAfter(v as boolean)}
              className={cx("h-8 rounded-[5px] px-3 transition-all", after === v ? "bg-surface font-medium text-ink shadow-1" : "text-ink-3")}>{l as string}</button>
          ))}
        </div>
        <ExampleTag />
      </div>
      <ul className="space-y-2">
        {order.map((idx, pos) => (
          <li key={idx} className={cx("flex items-start gap-3 rounded-md border px-3 py-2.5 text-[13px] transition-all duration-500 ease-[var(--ease-out)]",
            after && idx === 2 ? "border-ok/30 bg-ok/6" : "border-line bg-bg/50")}>
            <span className="mt-px font-mono text-[11px] text-ink-3">{String(pos + 1).padStart(2, "0")}</span>
            <span className="text-ink">{before[idx]}</span>
          </li>
        ))}
      </ul>
      <div className={cx("mt-4 rounded-lg border border-dashed border-line-strong p-3.5 font-mono text-[12px] leading-relaxed transition-opacity duration-300", after ? "opacity-100" : "opacity-40")}>
        <p><span className="text-ink-3">operation</span> <span className="text-ink">move_up</span></p>
        <p><span className="text-ink-3">requirement</span> <span className="text-ink">Kubernetes, model serving</span></p>
        <p><span className="text-ink-3">evidence</span> <span className="text-ok">“Deployed PyTorch inference services on Kubernetes”</span></p>
        <p><span className="text-ink-3">words added</span> <span className="text-ink">0</span></p>
      </div>
    </div>
  );
}

const ATS = [
  { k: "Keywords", w: 50, s: 84 },
  { k: "Skills", w: 25, s: 80 },
  { k: "Experience", w: 15, s: 75 },
  { k: "Formatting", w: 10, s: 90 },
];

export function AtsDemo() {
  const total = ATS.reduce((a, c) => a + (c.w * c.s) / 100, 0);
  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-2 sm:p-6">
      <div className="flex items-start justify-between">
        <div>
          <Label>ATS score</Label>
          <p className="mt-1 font-mono text-5xl tabular tracking-tight text-ink">{total.toFixed(0)}<span className="text-lg text-ink-3">/100</span></p>
        </div>
        <ExampleTag />
      </div>
      <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-sunken" aria-hidden="true">
        {ATS.map((c, i) => (
          <span key={c.k} className="h-full" style={{ width: `${(c.w * c.s) / 100}%`, background: ["var(--ink)", "var(--brand)", "var(--stage-out)", "var(--ink-3)"][i], marginRight: 2 }} />
        ))}
      </div>
      <table className="mt-5 w-full text-[13px]">
        <thead><tr className="text-left font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-3"><th className="pb-2 font-medium">Category</th><th className="pb-2 font-medium">Weight</th><th className="pb-2 font-medium">Score</th><th className="pb-2 text-right font-medium">Adds</th></tr></thead>
        <tbody className="divide-y divide-line">
          {ATS.map((c) => (
            <tr key={c.k}>
              <td className="py-2 text-ink">{c.k}</td>
              <td className="py-2 font-mono tabular text-ink-3">{c.w}%</td>
              <td className="w-[34%] py-2 pr-4"><Meter value={c.s} label={`${c.k} score`} /></td>
              <td className="py-2 text-right font-mono tabular text-ink">+{((c.w * c.s) / 100).toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-5 flex flex-wrap gap-1.5">
        {["PyTorch", "Kubernetes", "Python", "MLOps"].map((t) => <Tag key={t} tone="ok">{t}</Tag>)}
        {["gRPC", "Ray"].map((t) => <Tag key={t} tone="bad">{t}</Tag>)}
      </div>
    </div>
  );
}

export function PrepDemo() {
  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-line bg-surface p-5 shadow-2">
        <div className="flex items-center justify-between"><Label>Question 04 · System design</Label><ExampleTag /></div>
        <p className="mt-3 text-[15px] leading-snug text-ink">How would you serve a model with a 50 ms p99 latency budget to 2,000 requests per second?</p>
        <div className="tear my-4" aria-hidden="true" />
        <p className="text-[13px] text-ink-2"><span className="text-ink-3">Why: </span>the JD lists “low-latency inference” under responsibilities.</p>
        <p className="mt-1 font-mono text-[12px] text-ink-3">source: job description, line 18</p>
      </div>
      <div className="ml-6 rounded-2xl border border-line bg-surface p-5 shadow-2 sm:ml-12">
        <div className="flex items-center justify-between"><Label>Arena · your answer</Label><span className="font-mono text-sm tabular text-ink">7.5/10</span></div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {["batching", "autoscaling", "caching"].map((t) => <Tag key={t} tone="ok">{t}</Tag>)}
          <Tag tone="bad">tail latency</Tag>
        </div>
        <p className="mt-3 text-[13px] text-ink-2"><span className="text-ink-3">Follow-up: </span>what would you trade off to hit p99 rather than p50?</p>
      </div>
    </div>
  );
}

export function OutreachDemo() {
  const steps = ["Drafted", "Checked", "You approve", "Sent"];
  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-2 sm:p-6">
      <div className="flex items-center justify-between"><Label>Outreach draft</Label><ExampleTag /></div>
      <ol className="mt-4 grid grid-cols-4 gap-1.5" aria-label="Approval flow">
        {steps.map((s, i) => (
          <li key={s} className="min-w-0">
            <span className={cx("block h-1 rounded-full", i < 2 ? "bg-ink" : i === 2 ? "bg-accent" : "bg-line")} />
            <span className={cx("mt-1.5 block truncate text-[11.5px]", i === 2 ? "font-medium text-ink" : "text-ink-3")}>{s}</span>
          </li>
        ))}
      </ol>
      <div className="mt-5 space-y-1.5 text-[13px]">
        <p><span className="inline-block w-16 text-ink-3">To</span><span className="font-mono text-ink">careers@nexora.example</span></p>
        <p><span className="inline-block w-16 text-ink-3">Subject</span><span className="text-ink">Machine Learning Engineer application</span></p>
      </div>
      <div className="mt-4 rounded-md border border-warn/30 bg-warn/8 px-3.5 py-2.5 text-[13px] text-ink">
        <span className="font-medium text-warn">Factuality check · </span>“5 years of Kubernetes” isn’t supported by your resume.
      </div>
      <p className="mt-4 truncate font-mono text-[11px] text-ink-3">payload sha256 9c1e…a07f · sends only this exact text</p>
    </div>
  );
}

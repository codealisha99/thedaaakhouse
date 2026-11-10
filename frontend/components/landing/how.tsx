"use client";

import { useEffect, useRef, useState } from "react";
import { cx } from "@/components/ds";

const STEPS = [
  {
    stage: "Drafted",
    title: "Add the job",
    body: "Paste a job description or just the URL. It’s read for required skills, weighted keywords, responsibilities and years of experience, and filed on your tracker.",
    facts: ["Job URL fetch with private-address blocking", "Role categorised automatically"],
  },
  {
    stage: "Posted",
    title: "Send the right resume",
    body: "Tailor a version from your master resume. Bullets are reordered toward the job, never rewritten. Score it, see what’s missing, attach it to the application.",
    facts: ["Masters are never overwritten", "Line diff against the master", "PDF export"],
  },
  {
    stage: "In transit",
    title: "Prepare while you wait",
    body: "Interview questions derived from the JD, company facts pulled from its real pages, a study plan that starts with your gaps, and scored mock sessions.",
    facts: ["Every question says why it exists", "Research keeps its sources"],
  },
  {
    stage: "Out for delivery",
    title: "Follow up on time",
    body: "Each status change is timestamped. Today shows interviews, next steps, applications without a resume, and the ones going quiet before they become dead letters.",
    facts: ["Gmail drafts you approve before sending", "30 days of silence marks a dead letter"],
  },
];

/** Scroll-driven route: the stop for the step in view lights up. */
export function HowItWorks() {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) setActive(Number((e.target as HTMLElement).dataset.i));
    }, { rootMargin: "-45% 0px -45% 0px" });
    refs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <ol className="relative">
      <span className="absolute top-3 bottom-3 left-[11px] w-px bg-line-strong md:left-[calc(30%+11px)]" aria-hidden="true" />
      <span className="absolute top-3 left-[11px] w-px origin-top bg-ink transition-[height] duration-500 ease-[var(--ease-in-out)] md:left-[calc(30%+11px)]"
        style={{ height: `calc((100% - 24px) * ${active / (STEPS.length - 1)})` }} aria-hidden="true" />
      {STEPS.map((s, i) => (
        <li key={s.stage} ref={(el) => { refs.current[i] = el; }} data-i={i}
          className="relative grid gap-2 pb-16 pl-12 last:pb-0 md:grid-cols-[30%_1fr] md:gap-0 md:pl-0">
          <p className={cx("font-mono text-[12px] uppercase tracking-[0.1em] transition-colors md:pt-0.5 md:pr-10 md:text-right", i === active ? "text-accent" : "text-ink-3")}>
            <span className="tabular">0{i + 1}</span> · {s.stage}
          </p>
          <span aria-hidden="true" className={cx("absolute top-0.5 left-0 size-[23px] rounded-full border-2 bg-bg transition-all duration-300 md:left-[30%]",
            i < active ? "border-ink bg-ink" : i === active ? "scale-110 border-accent" : "border-line-strong")}>
            {i === active && <span className="m-[4px] block size-[11px] rounded-full bg-accent" />}
          </span>
          <div className="md:pl-14">
            <h3 className={cx("font-display text-[32px] leading-tight transition-colors duration-300 sm:text-[38px]", i === active ? "text-ink" : "text-ink-3")}>{s.title}</h3>
            <p className="mt-3 max-w-xl text-[16px] leading-relaxed text-ink-2">{s.body}</p>
            <ul className="mt-4 flex flex-wrap gap-2">
              {s.facts.map((f) => <li key={f} className="rounded-full border border-line px-3 py-1 text-[12.5px] text-ink-2">{f}</li>)}
            </ul>
          </div>
        </li>
      ))}
    </ol>
  );
}

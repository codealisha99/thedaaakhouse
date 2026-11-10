"use client";

import { use, useCallback, useEffect, useState } from "react";
import {
  Badge, Button, DefList, ErrorState, Field, LoadingBlock, Meter, Notice, PageHeader, Panel, PanelHeader, cx, textareaCls, type Tone,
} from "@/components/ds";
import { api } from "@/lib/api";
import type { StudyPlan, StudyTopic, TopicAnswer } from "@/types";

const STATUS_TONE: Record<string, Tone> = {
  not_started: "neutral", in_progress: "brand", mastered: "ok", needs_revision: "warn",
};

export default function PlanDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, TopicAnswer>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setPlan(await api.getPlan(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed.");
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function submitAnswer(term: string) {
    setBusy(true);
    try {
      const res = await api.answerTopic(id, term, drafts[term] ?? "");
      setResults((r) => ({ ...r, [term]: res }));
      await load();
    } catch (e) {
      setResults((r) => ({ ...r, [term]: {
        topic: term, score: 0, verdict: "needs_revision", hits: [], missed: [],
        feedback: e instanceof Error ? e.message : "Submit failed.",
        progress: { status: "needs_revision", attempts: 0, correct: 0 },
      }}));
    } finally {
      setBusy(false);
    }
  }

  if (!plan) {
    return (
      <div className="mx-auto max-w-5xl">
        {error ? <ErrorState message={error} onRetry={load} /> : <LoadingBlock rows={3} />}
      </div>
    );
  }

  const mastered = plan.topics.filter((t) => t.progress.status === "mastered").length;
  const newCount = plan.topics.filter((t) => !t.known).length;
  // Server already ranks missing terms first; the path follows that order.
  const ordered = [...plan.topics].sort((a, b) => a.order - b.order);

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Study plan"
        title={plan.title}
        description={`${mastered} of ${plan.topics.length} topics mastered.`}
      />
      {error && <Notice tone="bad" className="mb-5">{error}</Notice>}
      <div className="grid items-start gap-5 lg:grid-cols-[260px_1fr]">
        <Panel className="lg:sticky lg:top-6">
          <PanelHeader title="Mastery" />
          <Meter value={mastered} max={Math.max(plan.topics.length, 1)} tone="ok" label="Topics mastered" />
          <p className="mt-2 font-mono text-[13px] tabular text-ink-2">{mastered} of {plan.topics.length} mastered</p>
          <div className="mt-5">
            <DefList items={[
              { label: "New terms", value: <span className="font-mono tabular">{newCount}</span> },
              { label: "Revision", value: <span className="font-mono tabular">{plan.topics.length - newCount}</span> },
            ]} />
          </div>
        </Panel>
        <ol className="stagger space-y-3">
          {ordered.map((t) => (
            <TopicRow
              key={t.term}
              topic={t}
              open={open === t.term}
              onToggle={() => setOpen(open === t.term ? null : t.term)}
              draft={drafts[t.term] ?? ""}
              onDraft={(v) => setDrafts((d) => ({ ...d, [t.term]: v }))}
              result={results[t.term]}
              busy={busy}
              onSubmit={() => submitAnswer(t.term)}
            />
          ))}
        </ol>
      </div>
    </div>
  );
}

type TopicRowProps = {
  topic: StudyTopic;
  open: boolean;
  onToggle: () => void;
  draft: string;
  onDraft: (v: string) => void;
  result?: TopicAnswer;
  busy: boolean;
  onSubmit: () => void;
};

function TopicRow({ topic, open, onToggle, ...body }: TopicRowProps) {
  const status = topic.progress.status;
  return (
    <li className="relative pl-10">
      <span aria-hidden="true" className="absolute left-0 top-3.5 flex size-7 items-center justify-center rounded-full border border-line-strong bg-surface font-mono text-[12px] tabular text-ink-2">
        {topic.order}
      </span>
      <Panel padded={false} className={cx(open && "border-line-strong")}>
        <button type="button" aria-expanded={open} onClick={onToggle}
          className="flex min-h-12 w-full flex-wrap items-center justify-between gap-2 px-4 py-3 text-left">
          <span className="min-w-0">
            <span className="block font-medium text-ink">{topic.term}</span>
            <span className="mt-0.5 block text-[13px] text-ink-3">
              {topic.known ? "Revision" : "New"} · <span className="font-mono tabular">{topic.progress.attempts}</span> attempt(s)
            </span>
          </span>
          <Badge tone={STATUS_TONE[status] ?? "neutral"} dot>{status.replace(/_/g, " ")}</Badge>
        </button>
        {open && <TopicBody topic={topic} {...body} />}
      </Panel>
    </li>
  );
}

function TopicBody({ topic, draft, onDraft, result, busy, onSubmit }: Omit<TopicRowProps, "open" | "onToggle">) {
  return (
    <div className="space-y-4 border-t border-line px-4 py-4 text-[14px]">
      {topic.resume_evidence && <Notice tone="ok">Your evidence: {topic.resume_evidence}</Notice>}
      {topic.levels.map((l) => (
        <div key={l.name}>
          <p className="font-medium text-ink">{l.name}</p>
          <p className="mt-0.5 text-ink-2">{l.prompt}</p>
        </div>
      ))}
      <div>
        <p className="font-medium text-ink">Exercises</p>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-2">
          {topic.exercises.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      </div>
      <div className="rounded-md border border-line bg-sunken/50 p-4">
        <p className="font-medium text-ink">Knowledge check</p>
        <p className="mt-1 text-ink-2">{topic.check.question}</p>
        <Field label="Your answer" className="mt-3">
          <textarea className={textareaCls} placeholder="Write your answer…" value={draft} onChange={(e) => onDraft(e.target.value)} />
        </Field>
        <Button className="mt-3" busy={busy} disabled={!draft.trim()} onClick={onSubmit}>Check answer</Button>
        {result && (
          <Notice tone={result.verdict === "correct" ? "ok" : "warn"} className="mt-3">
            <p className="font-medium">
              {result.verdict === "correct" ? "Correct" : "Needs revision"}{" "}
              <span className="font-mono tabular">({Math.round(result.score * 100)}%)</span>
            </p>
            <p className="mt-1">{result.feedback}</p>
          </Notice>
        )}
      </div>
    </div>
  );
}

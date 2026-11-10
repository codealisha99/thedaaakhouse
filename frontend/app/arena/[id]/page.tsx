"use client";

import { use, useCallback, useEffect, useState } from "react";
import {
  Badge, Button, DefList, ErrorState, Field, Label, LoadingBlock, Meter, Notice, PageHeader, Panel, PanelHeader, Tag, cx, textareaCls, type Tone,
} from "@/components/ds";
import { api } from "@/lib/api";
import type { ArenaSession, ArenaTurn } from "@/types";

type Evaluation = ArenaTurn["evaluation"];

const VERDICT_TONE: Record<string, Tone> = { strong: "ok", partial: "warn" };

export default function ArenaRun({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [s, setS] = useState<ArenaSession | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setS(await api.getArena(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed.");
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      setS(await api.answerArena(id, draft));
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!s) {
    return (
      <div className="mx-auto max-w-5xl">
        {error ? <ErrorState message={error} onRetry={load} /> : <LoadingBlock rows={3} />}
      </div>
    );
  }

  const pct = s.total ? (100 * s.answered) / s.total : 0;
  const average = s.average_score != null ? `${(s.average_score * 100).toFixed(0)}%` : "—";

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow={`Arena session · ${s.difficulty}`}
        title={s.mode.replace(/_/g, " ")}
        description={`Question ${Math.min(s.answered + 1, s.total)} of ${s.total} · ${s.status}`}
      />
      <div className="grid items-start gap-5 lg:grid-cols-[1fr_280px]">
        <div className="stagger min-w-0 space-y-4">
          {s.turns.map((t, i) => <TurnCard key={i} index={i} turn={t} />)}
          {s.status === "active" && s.current && (
            <QuestionForm
              question={s.current}
              number={s.answered + 1}
              total={s.total}
              draft={draft}
              onDraft={setDraft}
              busy={busy}
              error={error}
              onSubmit={submit}
            />
          )}
        </div>
        <aside className="space-y-5 lg:sticky lg:top-6">
          <Panel>
            <PanelHeader title="Progress" meta={`${s.answered} of ${s.total} answered`} />
            <Meter value={pct} tone="brand" label="Questions answered" />
            <div className="mt-5">
              <DefList items={[
                { label: "Status", value: <Badge tone={s.status === "complete" ? "ok" : "brand"}>{s.status}</Badge> },
                { label: "Average", value: <span className="font-mono tabular">{average}</span> },
              ]} />
            </div>
          </Panel>
          {s.status === "complete" && s.summary && <SummaryPanel summary={s.summary} />}
        </aside>
      </div>
    </div>
  );
}

function TurnCard({ turn, index }: { turn: ArenaTurn; index: number }) {
  const q = turn.question;
  return (
    <Panel as="article">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Label>Q{index + 1} · {q.topic}</Label>
          <h3 className="mt-1.5 font-semibold text-ink">{q.question}</h3>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Tag>{q.difficulty}</Tag>
          <Tag>{q.source}</Tag>
        </div>
      </div>
      <p className="mt-4 whitespace-pre-wrap rounded-md bg-sunken p-3 text-[14px] leading-relaxed text-ink-2">{turn.answer}</p>
      <EvaluationBlock evaluation={turn.evaluation} />
    </Panel>
  );
}

function EvaluationBlock({ evaluation: ev }: { evaluation: Evaluation }) {
  return (
    <div className="mt-4 space-y-3 border-t border-line pt-4">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={VERDICT_TONE[ev.verdict] ?? "bad"} dot>{ev.verdict}</Badge>
        <span className="font-mono text-sm tabular text-ink">{Math.round(ev.score * 100)}%</span>
        <Meter value={ev.score * 100} className="w-24" label="Turn score" />
      </div>
      <p className="text-[14px] text-ink-2">{ev.feedback}</p>
      {ev.hits.length > 0 && <TagGroup label="Hits" items={ev.hits} tone="ok" />}
      {ev.missed.length > 0 && <TagGroup label="Missed" items={ev.missed} tone="bad" />}
      {ev.follow_up && <Notice tone="brand">Follow-up: {ev.follow_up}</Notice>}
    </div>
  );
}

function TagGroup({ label, items, tone }: { label: string; items: string[]; tone: "ok" | "bad" }) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {items.map((item) => <Tag key={item} tone={tone}>{item}</Tag>)}
      </div>
    </div>
  );
}

type QuestionFormProps = {
  question: NonNullable<ArenaSession["current"]>;
  number: number;
  total: number;
  draft: string;
  onDraft: (v: string) => void;
  busy: boolean;
  error: string | null;
  onSubmit: (e: React.FormEvent) => void;
};

function QuestionForm({ question: q, number, total, draft, onDraft, busy, error, onSubmit }: QuestionFormProps) {
  const meta = [q.topic, q.reason, q.hints.length > 0 && `Hint: ${q.hints[0]}`, q.complexity && `Target: ${q.complexity}`]
    .filter(Boolean).join(" · ");
  return (
    <form onSubmit={onSubmit}>
      <Panel className="space-y-4">
        <div>
          <Label>Question {number} of {total}</Label>
          <h3 className="mt-1.5 text-[17px] font-semibold tracking-[-0.01em] text-ink">{q.question}</h3>
          <p className="mt-1.5 text-[13px] text-ink-3">{meta}</p>
        </div>
        {q.tests.length > 0 && (
          <div>
            <Label>Tests</Label>
            <p className="mt-1.5 break-words rounded-md bg-sunken p-3 font-mono text-[12px] text-ink-2">{q.tests.join(" | ")}</p>
          </div>
        )}
        <Field label="Your answer">
          <textarea className={cx(textareaCls, "min-h-28")} placeholder="Type your answer…" value={draft} onChange={(e) => onDraft(e.target.value)} />
        </Field>
        {error && <Notice tone="bad">{error}</Notice>}
        <Button type="submit" variant="accent" busy={busy} disabled={!draft.trim()}>
          {busy ? "Evaluating…" : "Submit answer"}
        </Button>
      </Panel>
    </form>
  );
}

function SummaryPanel({ summary }: { summary: NonNullable<ArenaSession["summary"]> }) {
  return (
    <Panel>
      <PanelHeader title="Session summary" />
      <div className="space-y-3 text-[14px]">
        <TagGroup label="Strengths" items={summary.strengths} tone="ok" />
        <TagGroup label="Weaknesses" items={summary.weaknesses} tone="bad" />
      </div>
      <div className="mt-5 space-y-3">
        <Label>By category</Label>
        {Object.entries(summary.by_category).map(([c, v]) => (
          <div key={c}>
            <div className="flex items-baseline justify-between text-[13px]">
              <span className="text-ink-2">{c.replace(/_/g, " ")}</span>
              <span className="font-mono tabular text-ink">{(Number(v) * 100).toFixed(0)}%</span>
            </div>
            <Meter value={Number(v) * 100} className="mt-1.5" label={c} />
          </div>
        ))}
      </div>
    </Panel>
  );
}

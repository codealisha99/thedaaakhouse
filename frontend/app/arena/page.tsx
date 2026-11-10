"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Button, Field, Notice, PageHeader, Panel, PanelHeader, cx, linkCls, selectCls, type Tone } from "@/components/ds";
import { api } from "@/lib/api";
import type { Application, ArenaSummary } from "@/types";

const MODES: { key: string; blurb: string }[] = [
  { key: "mock", blurb: "Realistic mixed interview, one question at a time" },
  { key: "resume", blurb: "Deep dives into your projects and decisions" },
  { key: "technical", blurb: "JD-driven concepts, tools, and scenarios" },
  { key: "dsa", blurb: "Arrays → DP with hints, tests, and complexity" },
  { key: "system_design", blurb: "Requirements → API → scale → reliability" },
  { key: "cs", blurb: "OS, DBMS, networks, OOP fundamentals" },
  { key: "aiml", blurb: "Python, stats, ML/DL, transformers, RAG, deploy" },
];

const STATUS_TONE: Record<string, Tone> = { active: "brand", complete: "ok" };
const TOUCH_LINK = cx(linkCls, "inline-flex min-h-9 items-center");

export default function Arena() {
  const [apps, setApps] = useState<Application[]>([]);
  const [sessions, setSessions] = useState<ArenaSummary[]>([]);
  const [mode, setMode] = useState("mock");
  const [difficulty, setDifficulty] = useState("medium");
  const [appId, setAppId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [a, s] = await Promise.all([api.listApps({}), api.listArena()]);
      setApps(a); setSessions(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed.");
    }
  }

  useEffect(() => { load(); }, []);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setBusy(true);
    try {
      const s = await api.startArena(mode, difficulty, appId || undefined);
      window.location.href = `/arena/${s.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start session.");
    } finally {
      setBusy(false);
    }
  }

  const blurb = MODES.find((m) => m.key === mode)?.blurb;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Practice"
        title="Interview arena"
        description="Drills and mock interviews with scored turns."
      />
      {error && <Notice tone="bad" className="mb-5">{error}</Notice>}
      <div className="grid items-start gap-5 lg:grid-cols-[1fr_320px]">
        <form onSubmit={start}>
          <Panel className="space-y-5">
            <PanelHeader title="Start a session" />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Mode" hint={blurb}>
                <select className={selectCls} value={mode} onChange={(e) => setMode(e.target.value)}>
                  {MODES.map((m) => <option key={m.key} value={m.key}>{m.key.replace("_", " ")}</option>)}
                </select>
              </Field>
              <Field label="Difficulty">
                <select className={selectCls} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                  {["easy", "medium", "hard"].map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Application (optional)" hint="Resume and technical modes need an application or they will say so.">
              <select className={selectCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
                <option value="">None (drills only)</option>
                {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
              </select>
            </Field>
            <Button type="submit" variant="accent" busy={busy}>
              {busy ? "Entering…" : "Start session"}
            </Button>
          </Panel>
        </form>
        <aside className="space-y-5">
          <Panel>
            <PanelHeader title="Past sessions" meta={`${sessions.length} total`} />
            {sessions.length === 0 ? (
              <p className="text-[14px] text-ink-3">No sessions yet.</p>
            ) : (
              <ul className="stagger divide-y divide-line">
                {sessions.map((s) => (
                  <li key={s.id} className="py-3">
                    <div className="flex items-start justify-between gap-3">
                      <Link href={`/arena/${s.id}`} className={TOUCH_LINK}>
                        {s.mode.replace("_", " ")} · {s.difficulty}
                      </Link>
                      <Badge tone={STATUS_TONE[s.status] ?? "neutral"}>{s.status}</Badge>
                    </div>
                    <p className="text-[13px] text-ink-3">
                      <span className="font-mono tabular">{s.answered}/{s.total}</span> answered
                      {s.average_score != null && (
                        <> · avg <span className="font-mono tabular">{(s.average_score * 100).toFixed(0)}%</span></>
                      )}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel>
            <PanelHeader title="Arena rules" />
            <p className="text-[14px] leading-relaxed text-ink-2">
              One question at a time. Answers are scored against expected points; weak answers earn a follow-up, not a lecture. Difficulty defaults to easy–medium.
            </p>
          </Panel>
        </aside>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Field, inputCls } from "@/components/ui";
import { Letterhead, TypedMemo } from "@/components/post/postal";
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

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Letterhead title="Interview Arena" subtitle="Drills and mock interviews with scored turns" />
      <form onSubmit={start} className="grid gap-3 rounded-xl border bg-white p-5 sm:grid-cols-3">
        <Field label="Mode">
          <select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value)}>
            {MODES.map((m) => <option key={m.key} value={m.key}>{m.key.replace("_", " ")}</option>)}
          </select>
        </Field>
        <Field label="Difficulty">
          <select className={inputCls} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            {["easy", "medium", "hard"].map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </Field>
        <Field label="Application (optional)">
          <select className={inputCls} value={appId} onChange={(e) => setAppId(e.target.value)}>
            <option value="">None (drills only)</option>
            {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
          </select>
        </Field>
        <p className="-mt-1 text-xs text-slate-500 sm:col-span-3">
          {MODES.find((m) => m.key === mode)?.blurb}. Resume/tech modes need an application or they will say so.
        </p>
        {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700 sm:col-span-3">{error}</p>}
        <button type="submit" disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 sm:col-span-3">
          {busy ? "Entering…" : "Start session"}
        </button>
      </form>
      {sessions.length > 0 && (
        <div className="rounded-xl border bg-white p-4 text-sm">
          <h3 className="font-semibold">Past sessions</h3>
          <ul className="mt-2 space-y-1">
            {sessions.map((s) => (
              <li key={s.id} className="flex justify-between gap-2">
                <Link href={`/arena/${s.id}`} className="text-violet-700 hover:underline">
                  {s.mode} · {s.difficulty}
                </Link>
                <span className="text-xs text-slate-500">
                  {s.status} · {s.answered}/{s.total}
                  {s.average_score != null ? ` · ${(s.average_score * 100).toFixed(0)}%` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <TypedMemo title="Arena rules">
        <p>One question at a time. Answers are scored against expected points; weak answers earn a follow-up, not a lecture. Difficulty defaults to easy–medium.</p>
      </TypedMemo>
    </div>
  );
}

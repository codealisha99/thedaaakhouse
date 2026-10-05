"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorBox, ScoreBadge, Spinner, StatusBadge, StatusSelect } from "@/components/ui";
import { Letterhead, RubberStamp, TruckLoader, WaxSealButton } from "@/components/post/postal";
import { STAGES, pinFor, stageFor, stageOf } from "@/components/post/journey";
import { api, ApiError } from "@/lib/api";
import type { Application, ResumeVersion } from "@/types";

const STAGE_TO_STATUS: Record<string, string> = {
  drafted: "saved", posted: "applied", transit: "oa", out: "interview",
  delivered: "offer", return: "rejected", dead: "withdrawn",
};

function Cell({ value, onSave }: { value: string; onSave: (v: string) => Promise<unknown> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft(value), [value]);
  if (!editing) {
    return (
      <button onClick={() => setEditing(true)} className="block max-w-56 truncate px-1 py-0.5 text-left hover:bg-kraft/20" title={value || "click to edit"}>
        {value || <span className="text-postmark/50">—</span>}
      </button>
    );
  }
  return (
    <input
      autoFocus
      value={draft}
      disabled={saving}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={async () => { setSaving(true); try { await onSave(draft); } finally { setSaving(false); setEditing(false); } }}
      onKeyDown={async (e) => {
        if (e.key === "Enter") { (e.target as HTMLInputElement).blur(); }
        if (e.key === "Escape") { setDraft(value); setEditing(false); }
      }}
      className="w-44 rounded border border-kraft bg-envelope px-1 py-0.5 font-mono text-sm"
    />
  );
}

const FIELDS: { key: keyof Application; label: string }[] = [
  { key: "company", label: "Company" }, { key: "role", label: "Role" },
  { key: "location", label: "Location" }, { key: "job_url", label: "Job URL" },
  { key: "date_saved", label: "Date Saved" }, { key: "date_applied", label: "Date Applied" },
  { key: "salary", label: "Salary" }, { key: "interview_date", label: "Interview Date" },
  { key: "next_step", label: "Next Step" }, { key: "notes", label: "Notes" },
];

export default function Tracker() {
  const [rows, setRows] = useState<Application[]>([]);
  const [versions, setVersions] = useState<Record<string, string>>({});
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("updated");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<"wall" | "list">("wall");
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [stamped, setStamped] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const params: Record<string, string> = { sort };
      if (search.trim()) params.search = search.trim();
      if (status) params.status = status;
      const [apps, vers] = await Promise.all([api.listApps(params), api.listVersions()]);
      setRows(apps);
      setVersions(Object.fromEntries(vers.map((v: ResumeVersion) => [v.id, v.label])));
      setState("ready");
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "Failed to load applications.");
      setState("error");
    }
  }, [search, status, sort]);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, search]);

  async function patch(id: string, field: string, value: string, silent = false) {
    const prev = rows;
    setRows(rows.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
    try {
      const updated = await api.patchApp(id, { [field]: value } as Partial<Application>);
      setRows(rows.map((r) => (r.id === id ? updated : r)));
      if (field === "status") setStamped(id);
      return true;
    } catch {
      setRows(prev);
      if (!silent) alert("Save failed — is the API running?");
      return false;
    }
  }

  async function addRow() {
    setBusy(true);
    try {
      const created = await api.createApp({ company: "", role: "New role", status: "saved" });
      setRows([created, ...rows]);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Return this letter to sender for good? (Deletes the application.)")) return;
    await api.deleteApp(id);
    setRows(rows.filter((r) => r.id !== id));
  }

  const byStage = (key: string) => rows.filter((r) => stageFor(r.status, r.updated_at) === key);

  return (
    <div className="space-y-4">
      <Letterhead
        title="Pigeonholes"
        subtitle={`Tracker · ${rows.length} letter${rows.length === 1 ? "" : "s"} in the wall`}
        action={<WaxSealButton onClick={addRow}>Sort new letter</WaxSealButton>}
      />

      <div className="flex flex-wrap items-center gap-2">
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search the mail…"
          className="min-w-44 flex-1 rounded-md border border-kraft bg-envelope px-3 py-1.5 font-mono text-sm" />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-md border border-kraft bg-envelope px-2 py-1.5 font-mono text-sm">
          <option value="">All stages</option>
          {["saved", "applied", "oa", "interview", "final_round", "offer", "rejected", "withdrawn"].map((s) => (
            <option key={s} value={s}>{s.replace("_", " ")}</option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-md border border-kraft bg-envelope px-2 py-1.5 font-mono text-sm">
          <option value="updated">Recent first</option>
          <option value="created">Newest added</option>
          <option value="company">Company A–Z</option>
          <option value="status">By stage</option>
        </select>
        <div className="ml-auto flex rounded-md border border-kraft bg-envelope p-0.5 font-mono text-xs">
          {(["wall", "list"] as const).map((v) => (
            <button key={v} onClick={() => setView(v)}
              className={`min-h-[44px] rounded px-3 font-bold uppercase tracking-wider ${view === v ? "bg-postalnavy text-paper" : "text-postmark"}`}>
              {v === "wall" ? "Wall" : "Ledger"}
            </button>
          ))}
        </div>
      </div>

      {state === "loading" && <TruckLoader label="Sorting the mail…" />}
      {state === "error" && <ErrorBox message={error} onRetry={load} />}
      {state === "ready" && rows.length === 0 && (
        <EmptyState>No letters yet. Post your first application.</EmptyState>
      )}

      {state === "ready" && rows.length > 0 && view === "wall" && (
        <div className="flex gap-3 overflow-x-auto pb-4 md:grid md:grid-cols-4 md:overflow-visible xl:grid-cols-7">
          {STAGES.map((stage) => {
            const cards = byStage(stage.key);
            return (
              <section
                key={stage.key}
                onDragOver={(e) => { e.preventDefault(); setDragOver(stage.key); }}
                onDragLeave={() => setDragOver(null)}
                onDrop={(e) => {
                  e.preventDefault(); setDragOver(null);
                  const id = e.dataTransfer.getData("text/application-id");
                  if (id) patch(id, "status", STAGE_TO_STATUS[stage.key], true);
                }}
                className={`w-64 shrink-0 rounded-md border-2 border-dashed p-2 md:w-auto ${dragOver === stage.key ? "border-postred bg-postred/10" : "border-kraft/70 bg-kraft/15"}`}
                aria-label={stage.title}
              >
                <header className="px-1 pb-2">
                  <p className="font-serif text-base font-bold leading-tight text-postalnavy">{stage.title}</p>
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-postmark">{stage.blurb} · {cards.length}</p>
                </header>
                <div className="min-h-24 space-y-2">
                  {cards.map((r) => (
                    <article
                      key={r.id}
                      draggable
                      onDragStart={(e) => e.dataTransfer.setData("text/application-id", r.id)}
                      className="paper-keep cursor-grab rounded-[2px] border border-kraft/70 bg-envelope p-2.5 shadow-paper active:cursor-grabbing"
                    >
                      <Link href={`/applications/${r.id}`} className="block">
                        <p className="font-mono text-[11px] leading-snug">
                          <span className="text-postmark">To:</span> <strong>{r.company || "—"}</strong><br />
                          <span className="text-postmark">Attn:</span> {r.role}
                        </p>
                        <p className="mt-1 font-mono text-[10px] text-postmark">DH-{pinFor(r.id)}{r.ats_score != null ? ` · ATS ${r.ats_score.toFixed(0)}` : ""}</p>
                      </Link>
                      {stamped === r.id && (
                        <div className="mt-1" onAnimationEnd={() => setStamped((s) => (s === r.id ? null : s))}>
                          <RubberStamp text={stage.stamp} color={stage.color} size="sm" />
                        </div>
                      )}
                    </article>
                  ))}
                  {cards.length === 0 && <p className="px-1 py-4 text-center font-hand text-xl text-postmark/70">empty cubby</p>}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {state === "ready" && rows.length > 0 && view === "list" && (
        <div className="overflow-x-auto rounded-md border border-kraft bg-envelope shadow-paper">
          <table className="w-full min-w-max border-collapse font-mono text-[13px]">
            <thead>
              <tr className="bg-kraft/30 text-left text-[11px] uppercase tracking-wider text-postalnavy">
                <th className="border-b border-kraft px-3 py-2">Letter</th>
                {FIELDS.map((f) => <th key={f.key} className="border-b border-kraft px-3 py-2">{f.label}</th>)}
                <th className="border-b border-kraft px-3 py-2">Stage</th>
                <th className="border-b border-kraft px-3 py-2">ATS</th>
                <th className="border-b border-kraft px-3 py-2">Filed as</th>
                <th className="border-b border-kraft px-3 py-2"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-kraft/40 hover:bg-kraft/10">
                  <td className="px-3 py-1.5">
                    <Link href={`/applications/${r.id}`} className="font-bold text-postred hover:underline">Open →</Link>
                  </td>
                  {FIELDS.map((f) => (
                    <td key={f.key} className="px-2 py-1">
                      {f.key === "job_url" && r.job_url ? (
                        <a href={r.job_url} target="_blank" rel="noreferrer" className="text-airmailblue hover:underline" title={r.job_url}>link ⧉</a>
                      ) : (
                        <Cell value={(r[f.key] as string) ?? ""} onSave={(v) => patch(r.id, f.key, v)} />
                      )}
                      {f.key === "job_url" && !r.job_url && (
                        <Cell value="" onSave={(v) => patch(r.id, f.key, v)} />
                      )}
                    </td>
                  ))}
                  <td className="px-2 py-1"><StatusSelect small value={r.status} onChange={(v) => { void patch(r.id, "status", v); }} /></td>
                  <td className="px-3 py-1.5"><ScoreBadge score={r.ats_score} /></td>
                  <td className="max-w-40 truncate px-3 py-1.5 text-xs text-postmark">{r.resume_version_id ? versions[r.resume_version_id] ?? "filed" : "—"}</td>
                  <td className="px-2 py-1">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={r.status} updatedAt={r.updated_at} />
                      <button onClick={() => remove(r.id)} className="min-h-[44px] text-xs text-postred hover:underline">Return</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorBox, ScoreBadge, Spinner, StatusBadge, StatusSelect } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Application, ResumeVersion } from "@/types";

const FIELDS: { key: keyof Application; label: string; width: string }[] = [
  { key: "company", label: "Company", width: "min-w-36" },
  { key: "role", label: "Role", width: "min-w-44" },
  { key: "location", label: "Location", width: "min-w-32" },
  { key: "job_url", label: "Job URL", width: "min-w-40" },
  { key: "date_saved", label: "Date Saved", width: "min-w-28" },
  { key: "date_applied", label: "Date Applied", width: "min-w-28" },
  { key: "salary", label: "Salary", width: "min-w-28" },
  { key: "interview_date", label: "Interview Date", width: "min-w-32" },
  { key: "next_step", label: "Next Step", width: "min-w-40" },
  { key: "notes", label: "Notes", width: "min-w-48" },
];

function Cell({ value, onSave }: { value: string; onSave: (v: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft(value), [value]);
  if (!editing) {
    return (
      <button onClick={() => setEditing(true)} className="block max-w-56 truncate px-1 py-0.5 text-left hover:bg-slate-100" title={value || "click to edit"}>
        {value || <span className="text-slate-300">—</span>}
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
      className="w-44 rounded border px-1 py-0.5 text-sm"
    />
  );
}

export default function Tracker() {
  const [rows, setRows] = useState<Application[]>([]);
  const [versions, setVersions] = useState<Record<string, string>>({});
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("updated");
  const [busy, setBusy] = useState(false);

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
  }, [load]);

  async function patch(id: string, field: string, value: string) {
    const prev = rows;
    setRows(rows.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
    try {
      const updated = await api.patchApp(id, { [field]: value } as Partial<Application>);
      setRows(rows.map((r) => (r.id === id ? updated : r)));
    } catch {
      setRows(prev);
      alert("Save failed — is the API running?");
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
    if (!confirm("Delete this application and its history?")) return;
    await api.deleteApp(id);
    setRows(rows.filter((r) => r.id !== id));
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Job Tracker</h2>
          <p className="text-sm text-slate-500">{rows.length} application{rows.length === 1 ? "" : "s"} · click any cell to edit</p>
        </div>
        <button onClick={addRow} disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          + Add row
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search company, role, location…"
          className="min-w-52 flex-1 rounded-lg border px-3 py-1.5 text-sm" />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border px-2 py-1.5 text-sm">
          <option value="">All statuses</option>
          {["saved", "applied", "oa", "interview", "final_round", "offer", "rejected", "withdrawn"].map((s) => (
            <option key={s} value={s}>{s.replace("_", " ")}</option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-lg border px-2 py-1.5 text-sm">
          <option value="updated">Sort: recently updated</option>
          <option value="created">Sort: recently added</option>
          <option value="company">Sort: company A–Z</option>
          <option value="status">Sort: status</option>
        </select>
      </div>

      {state === "loading" && <Spinner />}
      {state === "error" && <ErrorBox message={error} onRetry={load} />}
      {state === "ready" && rows.length === 0 && (
        <EmptyState>No applications yet. Click <strong>+ Add row</strong> or analyze a JD from Applications → Job Analyzer.</EmptyState>
      )}

      {state === "ready" && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border bg-white">
          <table className="w-full min-w-max border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="border-b px-3 py-2">Application</th>
                {FIELDS.map((f) => <th key={f.key} className={`border-b px-3 py-2 ${f.width}`}>{f.label}</th>)}
                <th className="border-b px-3 py-2">Status</th>
                <th className="border-b px-3 py-2">ATS</th>
                <th className="border-b px-3 py-2">Resume</th>
                <th className="border-b px-3 py-2"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t hover:bg-slate-50/60">
                  <td className="px-3 py-1.5">
                    <Link href={`/applications/${r.id}`} className="font-medium text-violet-700 hover:underline">
                      Open →
                    </Link>
                  </td>
                  {FIELDS.map((f) => (
                    <td key={f.key} className="px-2 py-1">
                      {f.key === "job_url" && r.job_url ? (
                        <a href={r.job_url} target="_blank" rel="noreferrer" className="text-violet-700 hover:underline" title={r.job_url}>
                          link ⧉
                        </a>
                      ) : (
                        <Cell value={(r[f.key] as string) ?? ""} onSave={(v) => patch(r.id, f.key, v)} />
                      )}
                      {f.key === "job_url" && !r.job_url && (
                        <Cell value="" onSave={(v) => patch(r.id, f.key, v)} />
                      )}
                    </td>
                  ))}
                  <td className="px-2 py-1">
                    <StatusSelect small value={r.status} onChange={(v) => patch(r.id, "status", v)} />
                  </td>
                  <td className="px-3 py-1.5"><ScoreBadge score={r.ats_score} /></td>
                  <td className="max-w-40 truncate px-3 py-1.5 text-xs text-slate-500" title={r.resume_version_id ? versions[r.resume_version_id] : ""}>
                    {r.resume_version_id ? versions[r.resume_version_id] ?? "attached" : "—"}
                  </td>
                  <td className="px-2 py-1">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={r.status} />
                      <button onClick={() => remove(r.id)} className="text-xs text-red-500 hover:underline">Delete</button>
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

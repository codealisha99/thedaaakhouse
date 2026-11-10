"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button, EmptyState, ErrorState, LinkButton, LoadingBlock, PageHeader, Segmented, TrackingId, cx, inputCls, linkCls, scoreTone, selectCls } from "@/components/ds";
import { StageBadge, StatusSelect } from "@/components/route";
import { useToast } from "@/components/toast";
import { STAGES, STAGE_TO_STATUS, STATUS_LABEL, relativeDays, stageFor, type Stage } from "@/lib/journey";
import { api, ApiError } from "@/lib/api";
import { STATUSES, type Application, type ResumeVersion } from "@/types";

const FIELDS: { key: keyof Application; label: string }[] = [
  { key: "company", label: "Company" }, { key: "role", label: "Role" },
  { key: "location", label: "Location" }, { key: "job_url", label: "Job URL" },
  { key: "date_saved", label: "Saved" }, { key: "date_applied", label: "Applied" },
  { key: "salary", label: "Salary" }, { key: "interview_date", label: "Interview" },
  { key: "next_step", label: "Next step" }, { key: "notes", label: "Notes" },
];

function Cell({ value, label, onSave }: { value: string; label: string; onSave: (v: string) => Promise<unknown> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft(value), [value]);
  if (!editing) {
    return (
      <button onClick={() => setEditing(true)} aria-label={`Edit ${label}`} title={value || "Click to edit"}
        className="block h-8 w-full max-w-56 truncate rounded px-1.5 text-left transition-colors hover:bg-sunken">
        {value || <span className="text-ink-3">—</span>}
      </button>
    );
  }
  return (
    <input autoFocus aria-label={label} value={draft} disabled={saving}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={async () => { setSaving(true); try { if (draft !== value) await onSave(draft); } finally { setSaving(false); setEditing(false); } }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") { setDraft(value); setEditing(false); }
      }}
      className={cx(inputCls, "h-8 w-48 px-1.5 text-[13px]")} />
  );
}

function BoardCard({ app, stage, stamped, onMove, onStampEnd }: {
  app: Application; stage: Stage; stamped: boolean; onMove: (status: string) => void; onStampEnd: () => void;
}) {
  return (
    <article draggable onDragStart={(e) => e.dataTransfer.setData("text/application-id", app.id)}
      className="group rounded-lg border border-line bg-surface p-3 shadow-1 transition-[box-shadow,transform,border-color] duration-[var(--dur-2)] hover:-translate-y-px hover:border-line-strong hover:shadow-2 active:cursor-grabbing sm:cursor-grab">
      <Link href={`/applications/${app.id}`} className="block rounded">
        <p className="line-clamp-2 text-sm font-medium leading-snug text-ink">{app.role}</p>
        <p className="mt-0.5 truncate text-[13px] text-ink-2">{app.company || "Untitled company"}</p>
      </Link>
      <div className="tear my-2.5" aria-hidden="true" />
      <div className="flex items-center justify-between gap-2">
        <TrackingId id={app.id} className="text-[11px]" />
        <span className="flex items-center gap-2 font-mono text-[11px] text-ink-3">
          {app.ats_score != null && <span className={cx("tabular", { ok: "text-ok", warn: "text-warn", bad: "text-bad" }[scoreTone(app.ats_score) as "ok"])}>ATS {app.ats_score.toFixed(0)}</span>}
          {relativeDays(app.updated_at)}
        </span>
      </div>
      {stamped && (
        <span onAnimationEnd={() => setTimeout(onStampEnd, 900)}
          className="stamp mt-2 inline-block rounded border-2 px-1.5 py-px font-mono text-[10px] font-semibold uppercase tracking-[0.12em]"
          style={{ color: stage.color, borderColor: stage.color }}>{stage.title}</span>
      )}
      <select aria-label={`Move ${app.role} to stage`} value="" onChange={(e) => e.target.value && onMove(e.target.value)}
        className={cx(selectCls, "mt-2.5 h-8 text-[12px] text-ink-2 sm:sr-only sm:group-focus-within:not-sr-only")}>
        <option value="">Move to…</option>
        {STATUSES.filter((s) => s !== app.status).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
      </select>
    </article>
  );
}

function Board({ rows, stamped, setStamped, move }: {
  rows: Application[]; stamped: string | null; setStamped: (v: string | null) => void; move: (id: string, status: string) => void;
}) {
  const [over, setOver] = useState<string | null>(null);
  return (
    <div className="scroll-quiet -mx-4 flex snap-x scroll-px-4 gap-3 sm:scroll-px-6 lg:snap-none overflow-x-auto px-4 pb-4 sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10">
      {STAGES.map((stage) => {
        const cards = rows.filter((r) => stageFor(r.status, r.updated_at) === stage.key);
        return (
          <section key={stage.key} aria-label={`${stage.title}, ${cards.length}`}
            onDragOver={(e) => { e.preventDefault(); setOver(stage.key); }}
            onDragLeave={() => setOver(null)}
            onDrop={(e) => {
              e.preventDefault(); setOver(null);
              const id = e.dataTransfer.getData("text/application-id");
              if (id) move(id, STAGE_TO_STATUS[stage.key]);
            }}
            className={cx("flex w-[264px] shrink-0 snap-start flex-col rounded-xl border p-2 transition-colors duration-[var(--dur-2)]",
              over === stage.key ? "border-accent/50 bg-accent/5" : "border-transparent bg-sunken/70")}>
            <header className="flex items-center justify-between px-1.5 pt-1 pb-2.5">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[13px] font-semibold text-ink">
                  <span className="size-2 rounded-full" style={{ background: stage.color }} aria-hidden="true" />{stage.title}
                </p>
                <p className="mt-0.5 truncate text-[11px] text-ink-3">{stage.blurb}</p>
              </div>
              <span className="font-mono text-[12px] tabular text-ink-3">{cards.length}</span>
            </header>
            <div className="stagger min-h-24 flex-1 space-y-2">
              {cards.map((r) => (
                <BoardCard key={r.id} app={r} stage={stage} stamped={stamped === r.id}
                  onMove={(s) => move(r.id, s)} onStampEnd={() => setStamped(null)} />
              ))}
              {cards.length === 0 && <p className="rounded-lg border border-dashed border-line-strong/70 px-2 py-6 text-center text-[12px] text-ink-3">Drop here</p>}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function Ledger({ rows, versions, patch, remove }: {
  rows: Application[]; versions: Record<string, string>;
  patch: (id: string, field: string, value: string) => Promise<boolean>; remove: (a: Application) => void;
}) {
  return (
    <div className="scroll-quiet overflow-x-auto rounded-xl border border-line bg-surface shadow-1">
      <table className="w-full min-w-max border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-line bg-sunken/60 text-left">
            <th className="sticky left-0 z-10 bg-sunken px-4 py-2.5 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-3">Tracking</th>
            {FIELDS.map((f) => <th key={f.key} className="px-3 py-2.5 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-3">{f.label}</th>)}
            <th className="px-3 py-2.5 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-3">Status</th>
            <th className="px-3 py-2.5 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-3">ATS</th>
            <th className="px-3 py-2.5 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-3">Resume</th>
            <th className="px-3 py-2.5"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr key={r.id} className="transition-colors hover:bg-sunken/40">
              <td className="sticky left-0 z-10 bg-surface px-4 py-1.5">
                <Link href={`/applications/${r.id}`} className="font-mono text-[12px] text-brand hover:underline">
                  DH-{r.id.replace(/-/g, "").slice(0, 6).toUpperCase()}
                </Link>
              </td>
              {FIELDS.map((f) => (
                <td key={f.key} className="px-2 py-1">
                  {f.key === "job_url" && r.job_url
                    ? <a href={r.job_url} target="_blank" rel="noreferrer" className={linkCls} title={r.job_url}>Posting ↗</a>
                    : <Cell label={f.label} value={(r[f.key] as string) ?? ""} onSave={(v) => patch(r.id, f.key, v)} />}
                </td>
              ))}
              <td className="px-2 py-1"><StatusSelect small value={r.status} onChange={(v) => { void patch(r.id, "status", v); }} /></td>
              <td className="px-3 py-1 font-mono tabular text-ink-2">{r.ats_score != null ? r.ats_score.toFixed(0) : "—"}</td>
              <td className="max-w-40 truncate px-3 py-1 text-ink-3">{r.resume_version_id ? versions[r.resume_version_id] ?? "Attached" : "—"}</td>
              <td className="px-2 py-1">
                <div className="flex items-center gap-2">
                  <StageBadge status={r.status} updatedAt={r.updated_at} />
                  <Button variant="ghost" size="sm" onClick={() => remove(r)} aria-label={`Delete ${r.role}`}>Delete</Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Tracker() {
  const { toast, confirm } = useToast();
  const [rows, setRows] = useState<Application[]>([]);
  const [versions, setVersions] = useState<Record<string, string>>({});
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("updated");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<"board" | "ledger">("board");
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
      setError(e instanceof ApiError ? e.message : "Failed to load applications.");
      setState("error");
    }
  }, [search, status, sort]);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, search]);

  async function patch(id: string, field: string, value: string) {
    let prev: Application[] = [];
    setRows((rs) => { prev = rs; return rs.map((r) => (r.id === id ? { ...r, [field]: value } : r)); });
    try {
      const updated = await api.patchApp(id, { [field]: value } as Partial<Application>);
      setRows((rs) => rs.map((r) => (r.id === id ? updated : r)));
      if (field === "status") setStamped(id);
      return true;
    } catch (e) {
      setRows(prev);
      toast(e instanceof Error ? `Couldn’t save: ${e.message}` : "Couldn’t save the change.", "bad");
      return false;
    }
  }

  async function addRow() {
    setBusy(true);
    try {
      const created = await api.createApp({ company: "", role: "New role", status: "saved" });
      setRows((rs) => [created, ...rs]);
      setView("ledger");
      toast("Blank application added — fill it in below.", "ok");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Couldn’t add an application.", "bad");
    } finally { setBusy(false); }
  }

  async function remove(a: Application) {
    const ok = await confirm({ title: `Delete “${a.role}”?`, body: `${a.company || "This application"} and its history will be removed. This can’t be undone.`, confirmLabel: "Delete", danger: true });
    if (!ok) return;
    try {
      await api.deleteApp(a.id);
      setRows((rs) => rs.filter((r) => r.id !== a.id));
      toast("Application deleted.", "ok");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Delete failed.", "bad");
    }
  }

  const filtered = search || status;

  return (
    <div>
      <PageHeader
        eyebrow="Desk"
        title="Tracker"
        description={<>Every application on its route. Drag a card between stages, or switch to the ledger to edit fields inline. <span className="font-mono tabular text-ink">{rows.length}</span> shown.</>}
        actions={<>
          <Button variant="secondary" onClick={addRow} busy={busy}>Blank row</Button>
          <LinkButton href="/applications/new" variant="accent">Add application</LinkButton>
        </>}
      />

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <div className="relative min-w-52 flex-1">
          <svg className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search company, role, notes…" aria-label="Search applications" className={cx(inputCls, "pl-9")} />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status" className={cx(selectCls, "w-auto")}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort" className={cx(selectCls, "w-auto")}>
          <option value="updated">Recently updated</option>
          <option value="created">Newest added</option>
          <option value="company">Company A–Z</option>
          <option value="status">By status</option>
        </select>
        <div className="ml-auto">
          <Segmented label="View" value={view} onChange={setView} options={[{ value: "board", label: "Board" }, { value: "ledger", label: "Ledger" }]} />
        </div>
      </div>

      {state === "loading" && <LoadingBlock rows={3} label="Loading applications" />}
      {state === "error" && <ErrorState message={error} onRetry={load} />}
      {state === "ready" && rows.length === 0 && (
        filtered
          ? <EmptyState title="No matches" body="No application matches this search or filter." action={<Button variant="secondary" onClick={() => { setSearch(""); setStatus(""); }}>Clear filters</Button>} />
          : <EmptyState title="No applications yet" body="Paste a job description or URL and it will be analysed and placed on the board."
              action={<LinkButton href="/applications/new" variant="accent">Add application</LinkButton>} />
      )}
      {state === "ready" && rows.length > 0 && view === "board" && (
        <Board rows={rows} stamped={stamped} setStamped={setStamped} move={(id, s) => { void patch(id, "status", s); }} />
      )}
      {state === "ready" && rows.length > 0 && view === "ledger" && (
        <Ledger rows={rows} versions={versions} patch={patch} remove={remove} />
      )}
    </div>
  );
}

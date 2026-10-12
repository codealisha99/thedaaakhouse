"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Field, inputCls } from "@/components/ui";
import { Letterhead, TypedMemo, WaxSealButton } from "@/components/post/postal";
import { api, token } from "@/lib/api";
import type { ResumeVersion } from "@/types";

const TABS = ["Preview", "Edit", "Compare", "Match report"] as const;

export default function VersionStudio({ params }: { params: { id: string } }) {
  const [v, setV] = useState<ResumeVersion | null>(null);
  const [history, setHistory] = useState<ResumeVersion[]>([]);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Preview");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [label, setLabel] = useState("");
  const [content, setContent] = useState("");
  const [compare, setCompare] = useState<{ same_line_set: boolean; added: string[]; removed: string[]; similarity: number; unified_diff: string[] } | null>(null);
  const [report, setReport] = useState<{ rows: { requirement: string; status: string; evidence: string[] }[]; coverage: number } | null>(null);

  const load = useCallback(async () => {
    try {
      const doc = await api.getVersion(params.id);
      setV(doc);
      setLabel(doc.label);
      setContent(doc.content ?? "");
      if (doc.application_id) setHistory(await api.listVersions(doc.application_id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed.");
    }
  }, [params.id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (tab === "Compare" && !compare) api.compareVersion(params.id).then(setCompare).catch(() => {});
    if (tab === "Match report" && !report && v?.application_id) {
      api.matchReport(v.application_id, params.id).then(setReport).catch(() => {});
    }
  }, [tab, compare, report, params.id, v?.application_id]);

  async function save() {
    setBusy(true); setMsg(null);
    try {
      const updated = await api.patchVersion(params.id, { label, content });
      setV(updated);
      setMsg(updated.edited_manually
        ? "Saved. Flagged as manually edited — compare view shows exactly what changed."
        : "Saved.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  function downloadPdf() {
    const t = token.get();
    fetch(api.versionPdfUrl(params.id), { headers: t ? { Authorization: `Bearer ${t}` } : {} })
      .then((r) => { if (!r.ok) throw new Error(`Export failed (${r.status})`); return r.blob(); })
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${(v?.label || "resume").replace(/[^\w\- ]+/g, "").slice(0, 60) || "resume"}.pdf`;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch((e) => setMsg(e instanceof Error ? e.message : "Export failed."));
  }

  if (error) return <p className="font-mono text-sm text-postred">{error}</p>;
  if (!v) return <p className="font-mono text-sm text-postmark">Loading…</p>;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Letterhead title="Resume Studio" subtitle={`Version · ${v.label}`} />
      <div className="flex flex-wrap items-center gap-2">
        <nav className="flex gap-1.5">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`rounded-lg px-3.5 py-2 text-sm font-medium ${tab === t ? "bg-slate-900 text-white" : "border bg-white hover:bg-slate-100"}`}>
              {t}
            </button>
          ))}
        </nav>
        <button onClick={downloadPdf} className="ml-auto rounded-lg border px-3.5 py-2 text-sm font-medium hover:bg-slate-100">
          Export PDF
        </button>
      </div>
      {msg && <p className="text-sm text-slate-600">{msg}</p>}
      {v.edited_manually && (
        <p className="rounded-lg bg-amber-50 p-2.5 text-sm text-amber-800">
          Manually edited — content no longer matches the evidence-preserving tailor output. Compare tab shows the difference.
        </p>
      )}

      {tab === "Preview" && (
        <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-xl border bg-white p-5 font-mono text-xs">{v.content}</pre>
      )}

      {tab === "Edit" && (
        <div className="space-y-3 rounded-xl border bg-white p-5">
          <Field label="Label"><input className={inputCls} value={label} onChange={(e) => setLabel(e.target.value)} /></Field>
          <Field label="Content (your edits are flagged, never silently merged)">
            <textarea className={`${inputCls} min-h-64 font-mono text-xs`} value={content} onChange={(e) => setContent(e.target.value)} />
          </Field>
          <button onClick={save} disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            {busy ? "Saving…" : "Save version"}
          </button>
        </div>
      )}

      {tab === "Compare" && (
        <div className="space-y-3 rounded-xl border bg-white p-5 text-sm">
          {!compare ? <p className="text-slate-500">Loading diff…</p> : (
            <>
              <p>Line set identical to master: <strong>{compare.same_line_set ? "yes (pure reorder)" : "no (content changed)"}</strong> · similarity {compare.similarity}</p>
              {compare.added.length > 0 && (
                <div className="rounded-lg bg-red-50 p-3">
                  <p className="font-semibold">Added lines (not in your master resume):</p>
                  <ul className="list-disc pl-5">{compare.added.map((l, i) => <li key={i} className="font-mono text-xs">{l}</li>)}</ul>
                </div>
              )}
              {compare.removed.length > 0 && (
                <div className="rounded-lg bg-amber-50 p-3">
                  <p className="font-semibold">Removed lines:</p>
                  <ul className="list-disc pl-5">{compare.removed.map((l, i) => <li key={i} className="font-mono text-xs">{l}</li>)}</ul>
                </div>
              )}
              <details>
                <summary className="cursor-pointer text-violet-700">Unified diff</summary>
                <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono text-xs">{compare.unified_diff.join("\n")}</pre>
              </details>
            </>
          )}
        </div>
      )}

      {tab === "Match report" && (
        <div className="rounded-xl border bg-white p-5 text-sm">
          {!report ? <p className="text-slate-500">Loading report…</p> : (
            <>
              <p className="mb-2">Coverage: <strong>{(report.coverage * 100).toFixed(0)}%</strong> of JD requirements evidenced.</p>
              <ul className="space-y-2">
                {report.rows.map((r, i) => (
                  <li key={i} className={`rounded-lg p-2.5 ${r.status === "matched" ? "bg-emerald-50" : "bg-red-50"}`}>
                    <p><strong>{r.requirement}</strong> — {r.status}</p>
                    {r.evidence.map((e, j) => <p key={j} className="text-xs text-slate-600">↳ {e}</p>)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {history.length > 1 && (
        <div className="rounded-xl border bg-white p-5 text-sm">
          <h3 className="font-semibold">Version history</h3>
          <ul className="mt-2 space-y-1">
            {history.map((h) => (
              <li key={h.id}>
                {h.id === v.id ? <strong>{h.label} (this)</strong> : (
                  <Link href={`/resume/versions/${h.id}`} className="text-violet-700 hover:underline">{h.label}</Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {v.application_id && (
        <Link href={`/applications/${v.application_id}`} className="text-sm text-violet-700 hover:underline">
          ← Back to application workspace
        </Link>
      )}
      <TypedMemo title="Studio note">
        <p>Tailored versions are evidence-preserving reorderings. Anything you type yourself is flagged and diffable — the system never invents on your behalf.</p>
      </TypedMemo>
    </div>
  );
}

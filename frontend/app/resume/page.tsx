"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorBox, ScoreBadge, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { Resume, ResumeVersion } from "@/types";

export default function MyResumes() {
  const [masters, setMasters] = useState<Resume[]>([]);
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [openText, setOpenText] = useState("");

  async function load() {
    setState("loading");
    try {
      const [m, v] = await Promise.all([api.listResumes(), api.listVersions()]);
      setMasters(m); setVersions(v); setState("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
      setState("error");
    }
  }

  useEffect(() => { load(); }, []);

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true);
    try {
      await api.uploadResume(f);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function view(id: string, kind: "master" | "version") {
    if (kind === "master") {
      const doc = await api.getResume(id);
      setOpenId(id);
      setOpenText(doc.raw_text ?? "");
    } else {
      const doc = await api.getVersion(id);
      setOpenId(id);
      setOpenText(doc.content ?? "");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-serif text-3xl font-bold tracking-tight text-postalnavy">My Resumes</h2>
          <p className="postal-copy font-hand text-xl italic text-postmark">The Filing Cabinet</p>
          <p className="text-sm text-postmark">Master resumes are never overwritten — tailoring creates versions.</p>
        </div>
        <label className="cursor-pointer rounded-md bg-postred px-4 py-2 text-sm font-serif font-bold text-envelope">
          {busy ? "Uploading…" : "+ Upload resume"}
          <input type="file" className="hidden" onChange={upload} accept=".txt,.pdf,.docx,.tex" />
        </label>
      </div>

      {state === "loading" && <Spinner />}
      {state === "error" && <ErrorBox message={error} onRetry={load} />}

      {state === "ready" && (
        <>
          <section>
            <h3 className="mb-2 text-sm font-semibold">Master resumes ({masters.length})</h3>
            {masters.length === 0 ? <EmptyState>No master resume yet — upload your current resume to start.</EmptyState> : (
              <ul className="grid gap-2 sm:grid-cols-2">
                {masters.map((m) => (
                  <li key={m.id} className="flex items-center justify-between paper-keep rounded-sm border border-kraft/60 bg-envelope shadow-paper p-3 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{m.filename}</p>
                      <p className="text-xs text-postmark">{m.parse_status} · {(m.raw_text ?? "").split("\n").length} lines</p>
                    </div>
                    <button onClick={() => view(m.id, "master")} className="rounded-lg border px-2.5 py-1 text-xs font-medium hover:bg-slate-50">View</button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">Tailored versions ({versions.length})</h3>
            {versions.length === 0 ? <EmptyState>No tailored versions yet. Use Tailor Resume against a job description.</EmptyState> : (
              <ul className="space-y-2">
                {versions.map((v) => (
                  <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 paper-keep rounded-sm border border-kraft/60 bg-envelope shadow-paper p-3 text-sm">
                    <div>
                      <p className="font-medium">{v.label}</p>
                      <p className="text-xs text-postmark">missing: {v.missing_keywords.slice(0, 5).join(", ") || "none"}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <ScoreBadge score={v.ats_score} />
                      <button onClick={() => view(v.id, "version")} className="rounded-lg border px-2.5 py-1 text-xs font-medium hover:bg-slate-50">View</button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      {openId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setOpenId(null)}>
          <div className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-xl bg-white p-5" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex justify-between">
              <h3 className="font-semibold">Resume text</h3>
              <button onClick={() => setOpenId(null)} className="text-sm text-postmark hover:underline">Close</button>
            </div>
            <pre className="whitespace-pre-wrap text-xs">{openText}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

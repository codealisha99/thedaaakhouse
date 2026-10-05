"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";

export default function Analyzer() {
  const router = useRouter();
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("");
  const [jobUrl, setJobUrl] = useState("");
  const [jd, setJd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const app = await api.createApp({
        company, role: role || "Untitled role", location: location || undefined,
        job_url: jobUrl || undefined, raw_jd: jd, status: "saved",
        date_saved: new Date().toISOString().slice(0, 10),
      });
      router.push(`/applications/${app.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight">Job Analyzer</h2>
        <p className="text-sm text-slate-500">
          Paste a JD — thedaaakhouse stores the application and extracts skills, responsibilities, and requirements.
        </p>
      </div>
      <form onSubmit={submit} className="space-y-3 rounded-xl border bg-white p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Company"><input className={inputCls} value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme" /></Field>
          <Field label="Role"><input className={inputCls} value={role} onChange={(e) => setRole(e.target.value)} placeholder="AI Engineer" /></Field>
          <Field label="Location"><input className={inputCls} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Remote" /></Field>
          <Field label="Job URL"><input className={inputCls} value={jobUrl} onChange={(e) => setJobUrl(e.target.value)} placeholder="https://…" /></Field>
        </div>
        <Field label="Job description">
          <textarea className={`${inputCls} min-h-48 font-mono text-xs`} value={jd}
            onChange={(e) => setJd(e.target.value)} placeholder="Paste the full job description…" />
        </Field>
        {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
        <button type="submit" disabled={busy || !jd.trim()}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "Analyzing…" : "Save & analyze"}
        </button>
      </form>
    </div>
  );
}

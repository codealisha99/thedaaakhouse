"use client";

import { useEffect, useState } from "react";
import { Letterhead, TypedMemo } from "@/components/post/postal";
import { api } from "@/lib/api";

interface Provider {
  name: string;
  active: boolean;
  model: string;
  status: string;
  note?: string;
}

export default function Integrations() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [gmail, setGmail] = useState<{ enabled: boolean; connected: boolean; email: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api.integrations().then((r) => setProviders(r.providers)).catch((e) => {
      setError(e instanceof Error ? e.message : "Load failed.");
    });
    api.gmailStatus().then(setGmail).catch(() => setGmail(null));
  }, []);

  async function connectGmail() {
    try { window.location.assign((await api.gmailConnect()).authorization_url); }
    catch (e) { setError(e instanceof Error ? e.message : "Gmail connection failed."); }
  }
  async function syncGmail() {
    try { const result = await api.gmailSync(); setNotice(`Reply sync added ${result.events_added} event(s).`); }
    catch (e) { setError(e instanceof Error ? e.message : "Reply sync failed."); }
  }
  async function disconnectGmail() {
    try { await api.gmailDisconnect(); setGmail((current) => current ? { ...current, connected: false, email: null } : current); }
    catch (e) { setError(e instanceof Error ? e.message : "Disconnect failed."); }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Letterhead title="Integrations" subtitle="Active providers and future boundaries" />
      {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
      {notice && <p className="rounded-lg bg-emerald-50 p-2.5 text-sm text-emerald-800">{notice}</p>}
      <section className="rounded-xl border bg-white p-4">
        <div className="flex items-start justify-between gap-4">
          <div><h2 className="font-semibold">Gmail outreach</h2>
            <p className="mt-1 text-sm text-slate-600">{gmail?.connected ? `Connected as ${gmail.email}.` : "No Gmail account connected."}</p>
            <p className="mt-1 text-xs text-slate-500">Provider acceptance is not delivery confirmation. Replies are checked when you sync.</p>
          </div>
          {gmail?.connected ? <div className="flex gap-2">
            <button className="rounded-lg border px-3 py-2 text-sm" onClick={syncGmail}>Sync replies</button>
            <button className="rounded-lg border px-3 py-2 text-sm" onClick={disconnectGmail}>Disconnect</button>
          </div> : <button disabled={!gmail?.enabled} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-40" onClick={connectGmail}>Connect Gmail</button>}
        </div>
        {!gmail?.enabled && <p className="mt-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">Gmail is disabled until the backend OAuth client and token encryption key are configured.</p>}
      </section>
      <ul className="space-y-2">
        {providers.map((p) => (
          <li key={p.name} className="rounded-xl border bg-white p-4 text-sm">
            <div className="flex items-center justify-between">
              <strong>{p.name}</strong>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${p.active ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
                {p.active ? "active" : p.status.replace(/_/g, " ")}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">Model: {p.model || "—"}</p>
            {p.name === "grok" && (
              <p className="mt-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
                Coming Soon — the Grok boundary is defined but disabled. Core features never route here.
              </p>
            )}
            {p.note && p.name !== "grok" && <p className="mt-1 text-xs text-slate-500">{p.note}</p>}
          </li>
        ))}
      </ul>
      <TypedMemo title="Boundary note">
        <p>Providers implement one interface; the app never imports Ollama, OpenAI, or Grok directly. Enabling Grok later means configuration only — no core rewiring.</p>
      </TypedMemo>
    </div>
  );
}

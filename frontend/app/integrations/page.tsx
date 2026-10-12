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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.integrations().then((r) => setProviders(r.providers)).catch((e) => {
      setError(e instanceof Error ? e.message : "Load failed.");
    });
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Letterhead title="Integrations" subtitle="Active providers and future boundaries" />
      {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
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

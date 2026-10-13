"use client";

import { useEffect, useState } from "react";
import { Letterhead } from "@/components/post/postal";
import { api } from "@/lib/api";
import type { Application, CompareRow } from "@/types";

type Key = "fit" | "ats" | "role";

export default function Compare() {
  const [apps, setApps] = useState<Application[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [rows, setRows] = useState<CompareRow[]>([]);
  const [sort, setSort] = useState<Key>("fit");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listApps({}).then(setApps).catch((e) => setError(e instanceof Error ? e.message : "Load failed."));
  }, []);

  function toggle(id: string) {
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(0, 8)));
  }

  async function run() {
    setBusy(true); setError(null);
    try {
      setRows(await api.compareApps(picked));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Compare failed.");
    } finally {
      setBusy(false);
    }
  }

  const sorted = [...rows].sort((a, b) => {
    if (sort === "ats") return (b.ats_score ?? -1) - (a.ats_score ?? -1);
    if (sort === "role") return a.role.localeCompare(b.role);
    return (b.fit?.score ?? -1) - (a.fit?.score ?? -1);
  });

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Letterhead title="Job Comparison" subtitle="Career fit and resume compatibility, side by side" />
      <div className="rounded-xl border bg-white p-4 text-sm">
        <p className="mb-2 font-semibold">Pick up to 8 applications</p>
        <div className="flex max-h-48 flex-wrap gap-2 overflow-auto">
          {apps.map((a) => (
            <label key={a.id} className={`flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5 ${picked.includes(a.id) ? "border-violet-600 bg-violet-50" : ""}`}>
              <input type="checkbox" checked={picked.includes(a.id)} onChange={() => toggle(a.id)} />
              {a.company} · {a.role}
            </label>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2">
          <button onClick={run} disabled={busy || picked.length === 0}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            {busy ? "Comparing…" : "Compare"}
          </button>
          <select value={sort} onChange={(e) => setSort(e.target.value as Key)} className="rounded-lg border px-2 py-1.5 text-sm">
            <option value="fit">Sort: career fit</option>
            <option value="ats">Sort: ATS score</option>
            <option value="role">Sort: role</option>
          </select>
        </div>
      </div>
      {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
      {sorted.length > 0 && (
        <div className="overflow-x-auto rounded-xl border bg-white">
          <table className="w-full min-w-max text-sm">
            <thead>
              <tr className="bg-slate-100 text-left text-xs uppercase text-slate-500">
                <th className="px-3 py-2">Job</th>
                <th className="px-3 py-2">Fit</th>
                <th className="px-3 py-2">ATS</th>
                <th className="px-3 py-2">Missing</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.application_id} className="border-t">
                  <td className="px-3 py-2 font-medium">{r.company} · {r.role}</td>
                  <td className="px-3 py-2">
                    {r.fit ? `${r.fit.classification.replace("_", " ")} ${(r.fit.score * 100).toFixed(0)}%` : <span className="text-slate-400">unevaluated</span>}
                  </td>
                  <td className="px-3 py-2">{r.ats_score != null ? r.ats_score.toFixed(0) : <span className="text-slate-400">—</span>}</td>
                  <td className="max-w-64 truncate px-3 py-2 text-xs text-slate-500">{r.missing_skills.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-slate-500">Fit = career alignment from your profile. ATS = resume-vs-JD compatibility. Different questions, different scores.</p>
    </div>
  );
}

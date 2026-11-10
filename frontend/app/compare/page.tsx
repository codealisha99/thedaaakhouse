"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Field, Label, Meter, Notice, PageHeader, Panel, PanelHeader, Tag, Tone, selectCls } from "@/components/ds";
import { StageBadge } from "@/components/route";
import { api } from "@/lib/api";
import type { Application, CompareRow } from "@/types";

type Key = "fit" | "ats" | "role";

const FIT_TONE: Record<string, Tone> = { target: "ok", adjacent: "brand", poor: "bad", needs_review: "warn" };

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
    <div className="space-y-8">
      <PageHeader
        eyebrow="Compare"
        title="Compare applications"
        description="Career fit and resume compatibility, side by side. Fit and ATS answer different questions, so they are scored separately."
      />
      <Panel className="space-y-5">
        <PanelHeader title="Pick up to 8 applications" meta={`${picked.length} selected`} />
        <div className="scroll-quiet flex max-h-64 flex-wrap gap-2 overflow-auto">
          {apps.map((a) => {
            const on = picked.includes(a.id);
            return (
              <label key={a.id} className={`flex min-h-9 cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors duration-[var(--dur-1)] ${on ? "border-brand/40 bg-brand/5 text-ink" : "border-line-strong bg-surface text-ink-2 hover:border-ink-3"}`}>
                <input type="checkbox" checked={on} onChange={() => toggle(a.id)} className="size-4 accent-brand" />
                {a.company} · {a.role}
              </label>
            );
          })}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <Button variant="accent" onClick={run} disabled={busy || picked.length === 0}>
            {busy ? "Comparing…" : "Compare"}
          </Button>
          <Field label="Sort by" className="w-56">
            <select value={sort} onChange={(e) => setSort(e.target.value as Key)} className={selectCls}>
              <option value="fit">Career fit</option>
              <option value="ats">ATS score</option>
              <option value="role">Role</option>
            </select>
          </Field>
        </div>
      </Panel>
      {error && <Notice tone="bad">{error}</Notice>}
      {sorted.length > 0 && (
        <Panel padded={false} className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-sunken text-left">
                <tr>
                  <th className="px-4 py-2.5 font-normal"><Label>Job</Label></th>
                  <th className="px-4 py-2.5 font-normal"><Label>Career fit</Label></th>
                  <th className="px-4 py-2.5 font-normal"><Label>ATS</Label></th>
                  <th className="px-4 py-2.5 font-normal"><Label>Missing skills</Label></th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr key={r.application_id} className="border-t border-line align-top">
                    <td className="px-4 py-3.5">
                      <p className="font-medium text-ink">{r.company}</p>
                      <p className="text-[13px] text-ink-3">{r.role}</p>
                      <div className="mt-2"><StageBadge status={r.status} /></div>
                    </td>
                    <td className="px-4 py-3.5">
                      {r.fit ? (
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={FIT_TONE[r.fit.classification] ?? "neutral"} className="capitalize">{r.fit.classification.replace("_", " ")}</Badge>
                          <span className="font-mono tabular text-ink-2">{(r.fit.score * 100).toFixed(0)}%</span>
                        </div>
                      ) : <span className="text-ink-3">Unevaluated</span>}
                    </td>
                    <td className="px-4 py-3.5">
                      {r.ats_score != null ? (
                        <div className="w-24 space-y-1.5">
                          <p className="font-mono tabular text-ink">{r.ats_score.toFixed(0)}</p>
                          <Meter value={r.ats_score} />
                        </div>
                      ) : <span className="text-ink-3">—</span>}
                    </td>
                    <td className="min-w-48 px-4 py-3.5">
                      {r.missing_skills.length === 0
                        ? <span className="text-ink-3">None</span>
                        : <div className="flex flex-wrap gap-1.5">{r.missing_skills.map((s) => <Tag key={s} tone="bad">{s}</Tag>)}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      <p className="text-[13px] text-ink-3">Fit = career alignment from your profile. ATS = resume-vs-JD compatibility.</p>
    </div>
  );
}

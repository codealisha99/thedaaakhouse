"use client";

import { useEffect, useState } from "react";
import { Field, inputCls } from "@/components/ui";
import { Letterhead, TypedMemo } from "@/components/post/postal";
import { api } from "@/lib/api";
import type { CareerProfile, Resume } from "@/types";

const LIST_FIELDS: { key: keyof CareerProfile; label: string; hint: string }[] = [
  { key: "target_roles", label: "Target roles", hint: "one per line — e.g. AI Engineer" },
  { key: "skills_demonstrated", label: "Demonstrated skills", hint: "backed by resume evidence" },
  { key: "skills_claimed", label: "Claimed skills", hint: "no evidence on file yet" },
  { key: "skills_to_learn", label: "Skills to learn", hint: "never scored as possessed" },
  { key: "industries", label: "Industries", hint: "one per line" },
  { key: "domains", label: "Technical domains", hint: "e.g. NLP, payments" },
  { key: "excluded_roles", label: "Excluded roles", hint: "hard exclusions — always win" },
  { key: "goals", label: "Long-term objectives", hint: "one per line" },
];

const lines = (v: string) => v.split("\n").map((s) => s.trim()).filter(Boolean);

export default function Profile() {
  const [profile, setProfile] = useState<CareerProfile | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [prefs, setPrefs] = useState({ location: "", experience_level: "", salary: "", arrangement: "" });
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [seedId, setSeedId] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.getProfile(), api.listResumes()]).then(([p, r]) => {
      setProfile(p);
      setResumes(r);
      const d: Record<string, string> = {};
      for (const f of LIST_FIELDS) d[f.key] = ((p[f.key] as string[]) ?? []).join("\n");
      setDrafts(d);
      setPrefs({ location: "", experience_level: "", salary: "", arrangement: "", ...(p.preferences ?? {}) });
    }).catch((e) => setMsg(e instanceof Error ? e.message : "Load failed."));
  }, []);

  async function save() {
    setBusy(true); setMsg(null);
    try {
      const payload: Record<string, unknown> = {};
      for (const f of LIST_FIELDS) payload[f.key] = lines(drafts[f.key] ?? "");
      payload.preferences = prefs;
      setProfile(await api.putProfile(payload));
      setMsg("Profile saved.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function seed() {
    if (!seedId) return;
    setBusy(true); setMsg(null);
    try {
      const out = await api.seedProfile(seedId);
      setProfile(out.profile);
      const d: Record<string, string> = { ...drafts };
      d.skills_demonstrated = (out.profile.skills_demonstrated ?? []).join("\n");
      setDrafts(d);
      setMsg(`Seeded ${out.seeded_skills.length} evidenced skills from your resume (provenance marked).`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Seed failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!profile) return <p className="text-sm text-slate-500">{msg ?? "Loading…"}</p>;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Letterhead title="Career Profile" subtitle="Demonstrated, claimed, and to-learn stay separate" />
      <div className="flex gap-2 rounded-xl border bg-white p-4">
        <div className="flex-1">
          <Field label="Seed evidenced skills from a resume">
            <select className={inputCls} value={seedId} onChange={(e) => setSeedId(e.target.value)}>
              <option value="">Select resume…</option>
              {resumes.map((r) => <option key={r.id} value={r.id}>{r.filename}</option>)}
            </select>
          </Field>
        </div>
        <button onClick={seed} disabled={busy || !seedId}
          className="self-end rounded-lg border px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-40">
          Seed
        </button>
      </div>
      {msg && <p className="text-sm text-slate-600">{msg}</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        {LIST_FIELDS.map((f) => (
          <Field key={f.key} label={`${f.label} (${lines(drafts[f.key] ?? "").length})`}>
            <textarea className={`${inputCls} min-h-24 font-mono text-xs`} value={drafts[f.key] ?? ""}
              onChange={(e) => setDrafts((d) => ({ ...d, [f.key]: e.target.value }))} placeholder={f.hint} />
          </Field>
        ))}
      </div>
      <div className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-2">
        {(["location", "experience_level", "salary", "arrangement"] as const).map((k) => (
          <Field key={k} label={k.replace("_", " ")}>
            <input className={inputCls} value={prefs[k]} onChange={(e) => setPrefs((p) => ({ ...p, [k]: e.target.value }))} />
          </Field>
        ))}
      </div>
      <button onClick={save} disabled={busy}
        className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
        {busy ? "Saving…" : "Save profile"}
      </button>
      <TypedMemo title="Provenance rule">
        <p>Demonstrated = found in your resume with evidence. Claimed = you say so. To-learn = never scored as possessed. Seeded fields record which resume they came from.</p>
      </TypedMemo>
    </div>
  );
}

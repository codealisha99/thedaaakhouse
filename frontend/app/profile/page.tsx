"use client";

import { useEffect, useState } from "react";
import { Button, DefList, ErrorState, Field, LoadingBlock, Notice, PageHeader, Panel, PanelHeader, inputCls, selectCls, textareaCls } from "@/components/ds";
import { api } from "@/lib/api";
import type { CareerProfile, Resume } from "@/types";

const LIST_FIELDS: { key: keyof CareerProfile; label: string; hint: string }[] = [
  { key: "target_roles", label: "Target roles", hint: "One per line, e.g. AI Engineer" },
  { key: "skills_demonstrated", label: "Demonstrated skills", hint: "Backed by resume evidence" },
  { key: "skills_claimed", label: "Claimed skills", hint: "No evidence on file yet" },
  { key: "skills_to_learn", label: "Skills to learn", hint: "Never scored as possessed" },
  { key: "industries", label: "Industries", hint: "One per line" },
  { key: "domains", label: "Technical domains", hint: "e.g. NLP, payments" },
  { key: "excluded_roles", label: "Excluded roles", hint: "Hard exclusions. Always win." },
  { key: "goals", label: "Long-term objectives", hint: "One per line" },
];

const PREF_FIELDS = [
  { key: "location", label: "Location" },
  { key: "experience_level", label: "Experience level" },
  { key: "salary", label: "Salary" },
  { key: "arrangement", label: "Arrangement" },
] as const;

const lines = (v: string) => v.split("\n").map((s) => s.trim()).filter(Boolean);
type Msg = { text: string; tone: "ok" | "bad" } | null;

export default function Profile() {
  const [profile, setProfile] = useState<CareerProfile | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [prefs, setPrefs] = useState({ location: "", experience_level: "", salary: "", arrangement: "" });
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [seedId, setSeedId] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.getProfile(), api.listResumes()]).then(([p, r]) => {
      setProfile(p);
      setResumes(r);
      const d: Record<string, string> = {};
      for (const f of LIST_FIELDS) d[f.key] = ((p[f.key] as string[]) ?? []).join("\n");
      setDrafts(d);
      setPrefs({ location: "", experience_level: "", salary: "", arrangement: "", ...(p.preferences ?? {}) });
    }).catch((e) => setMsg({ text: e instanceof Error ? e.message : "Load failed.", tone: "bad" }));
  }, []);

  async function save() {
    setBusy(true); setMsg(null);
    try {
      const payload: Record<string, unknown> = {};
      for (const f of LIST_FIELDS) payload[f.key] = lines(drafts[f.key] ?? "");
      payload.preferences = prefs;
      setProfile(await api.putProfile(payload));
      setMsg({ text: "Profile saved.", tone: "ok" });
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : "Save failed.", tone: "bad" });
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
      setDrafts((d) => ({ ...d, skills_demonstrated: (out.profile.skills_demonstrated ?? []).join("\n") }));
      setMsg({ text: `Seeded ${out.seeded_skills.length} evidenced skills from your resume (provenance marked).`, tone: "ok" });
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : "Seed failed.", tone: "bad" });
    } finally {
      setBusy(false);
    }
  }

  if (!profile) return msg?.tone === "bad" ? <ErrorState message={msg.text} /> : <LoadingBlock rows={3} label="Loading profile" />;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Profile"
        title="Career profile"
        description="Demonstrated, claimed, and to-learn skills stay separate. Fit scoring reads from here."
        actions={<Button variant="accent" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save profile"}</Button>}
      />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <div className="grid items-start gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-6">
          <Panel>
            <PanelHeader title="Skills and goals" meta="One entry per line" />
            <div className="grid gap-5 sm:grid-cols-2">
              {LIST_FIELDS.map((f) => (
                <Field key={f.key} label={`${f.label} (${lines(drafts[f.key] ?? "").length})`} hint={f.hint}>
                  <textarea className={textareaCls} value={drafts[f.key] ?? ""}
                    onChange={(e) => setDrafts((d) => ({ ...d, [f.key]: e.target.value }))} />
                </Field>
              ))}
            </div>
          </Panel>
          <Panel>
            <PanelHeader title="Preferences" />
            <div className="grid gap-4 sm:grid-cols-2">
              {PREF_FIELDS.map((f) => (
                <Field key={f.key} label={f.label}>
                  <input className={inputCls} value={prefs[f.key]}
                    onChange={(e) => setPrefs((p) => ({ ...p, [f.key]: e.target.value }))} />
                </Field>
              ))}
            </div>
          </Panel>
        </div>
        <aside className="space-y-6 lg:sticky lg:top-6">
          <Panel className="space-y-4">
            <PanelHeader title="Seed from a resume" meta="Adds evidenced skills and records their source" />
            <Field label="Resume">
              <select className={selectCls} value={seedId} onChange={(e) => setSeedId(e.target.value)}>
                <option value="">Select resume…</option>
                {resumes.map((r) => <option key={r.id} value={r.id}>{r.filename}</option>)}
              </select>
            </Field>
            <Button variant="secondary" className="w-full" onClick={seed} disabled={busy || !seedId}>Seed</Button>
          </Panel>
          <Panel>
            <PanelHeader title="Provenance rule" />
            <DefList items={[
              { label: "Demonstrated", value: "Found in your resume, with evidence" },
              { label: "Claimed", value: "You say so" },
              { label: "To learn", value: "Never scored as possessed" },
            ]} />
            <p className="mt-3 text-[13px] leading-relaxed text-ink-3">Seeded fields record which resume they came from.</p>
          </Panel>
        </aside>
      </div>
    </div>
  );
}

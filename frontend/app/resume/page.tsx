"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Badge, Button, EmptyState, ErrorState, Label, LoadingBlock, PageHeader, Panel, PanelHeader,
  Spinner, Tag, buttonCls, cx, linkCls, scoreTone,
} from "@/components/ds";
import { useToast } from "@/components/toast";
import { api } from "@/lib/api";
import type { Resume, ResumeVersion } from "@/types";

const MAX_MISSING_SHOWN = 5;

export default function MyResumes() {
  const { toast } = useToast();
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
      toast(err instanceof Error ? err.message : "Upload failed.", "bad");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function view(id: string, kind: "master" | "version") {
    try {
      if (kind === "master") {
        const doc = await api.getResume(id);
        setOpenText(doc.raw_text ?? "");
      } else {
        const doc = await api.getVersion(id);
        setOpenText(doc.content ?? "");
      }
      setOpenId(id);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not open that resume.", "bad");
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Resumes"
        title="My resumes"
        description="Master resumes are never overwritten. Tailoring creates a new version each time."
        actions={
          <label className={cx(
            buttonCls("accent", "md"), "cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent",
            busy && "pointer-events-none opacity-60",
          )}>
            {busy && <Spinner />}
            {busy ? "Uploading…" : "Upload resume"}
            <input type="file" className="sr-only" onChange={upload} disabled={busy} accept=".txt,.pdf,.docx,.tex" />
          </label>
        }
      />

      {state === "loading" && <LoadingBlock rows={3} label="Loading resumes" />}
      {state === "error" && <ErrorState message={error} onRetry={load} />}

      {state === "ready" && (
        <div className="grid items-start gap-6 lg:grid-cols-[320px_1fr]">
          <MasterList masters={masters} onView={(id) => view(id, "master")} />
          <VersionList versions={versions} onView={(id) => view(id, "version")} />
        </div>
      )}

      {openId && <ResumeTextDialog text={openText} onClose={() => setOpenId(null)} />}
    </div>
  );
}

function MasterList({ masters, onView }: { masters: Resume[]; onView: (id: string) => void }) {
  return (
    <Panel>
      <PanelHeader title="Master resumes" meta={`${masters.length} on file`} />
      {masters.length === 0 ? (
        <EmptyState title="No master resume" body="Upload your current resume to start." />
      ) : (
        <ul className="stagger space-y-2">
          {masters.map((m) => {
            const lines = (m.raw_text ?? "").split("\n").length;
            return (
              <li key={m.id} className="flex items-center justify-between gap-3 rounded-md border border-line bg-bg p-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{m.filename}</p>
                  <p className="mt-0.5 font-mono text-[12px] tabular text-ink-3">{m.parse_status} · {lines} lines</p>
                </div>
                <Button variant="secondary" size="sm" onClick={() => onView(m.id)}>View</Button>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

function VersionList({ versions, onView }: { versions: ResumeVersion[]; onView: (id: string) => void }) {
  return (
    <Panel>
      <PanelHeader title="Tailored versions" meta={`${versions.length} total`} />
      {versions.length === 0 ? (
        <EmptyState title="No tailored versions" body="Use Tailor resume against a job description to create one." />
      ) : (
        <ul className="stagger divide-y divide-line">
          {versions.map((v) => {
            const extra = v.missing_keywords.length - MAX_MISSING_SHOWN;
            return (
              <li key={v.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    <Link href={`/resume/versions/${v.id}`} className={linkCls}>{v.label}</Link>
                  </p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <Label className="mr-1">Missing</Label>
                    {v.missing_keywords.length === 0 && <span className="text-[13px] text-ink-3">none</span>}
                    {v.missing_keywords.slice(0, MAX_MISSING_SHOWN).map((k) => <Tag key={k} tone="bad">{k}</Tag>)}
                    {extra > 0 && <span className="font-mono text-[12px] text-ink-3">+{extra}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={scoreTone(v.ats_score)} className="tabular">
                    {v.ats_score == null ? "Not scored" : `ATS ${Math.round(v.ats_score)}`}
                  </Badge>
                  <Button variant="secondary" size="sm" onClick={() => onView(v.id)}>View</Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

function ResumeTextDialog({ text, onClose }: { text: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4 backdrop-blur-[2px]" onClick={onClose}>
      <div
        role="dialog" aria-modal="true" aria-labelledby="resume-text-title"
        className="dialog-in flex max-h-[80vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-pop"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
          <h3 id="resume-text-title" className="font-semibold text-ink">Resume text</h3>
          <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
        </div>
        <pre className="scroll-quiet overflow-auto whitespace-pre-wrap break-words p-5 font-mono text-[12px] leading-relaxed text-ink-2">{text}</pre>
      </div>
    </div>
  );
}

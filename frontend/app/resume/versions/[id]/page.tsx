"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import {
  Badge, Button, DefList, EmptyState, ErrorState, Field, Label, LoadingBlock, Meter, Notice,
  PageHeader, Panel, PanelHeader, Tabs, Tag, cx, inputCls, linkCls, textareaCls,
} from "@/components/ds";
import { api, getAuthToken } from "@/lib/api";
import type { ResumeVersion } from "@/types";

const TABS = ["Preview", "Edit", "Compare", "Match report"] as const;
type Tab = (typeof TABS)[number];

type CompareOut = {
  same_line_set: boolean; added: string[]; removed: string[]; similarity: number; unified_diff: string[];
};
type ReportOut = {
  rows: { requirement: string; status: string; evidence: string[] }[]; coverage: number;
};

export default function VersionStudio({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [v, setV] = useState<ResumeVersion | null>(null);
  const [history, setHistory] = useState<ResumeVersion[]>([]);
  const [tab, setTab] = useState<Tab>("Preview");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; tone: "ok" | "bad" } | null>(null);

  const [label, setLabel] = useState("");
  const [content, setContent] = useState("");
  const [compare, setCompare] = useState<CompareOut | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportOut | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const doc = await api.getVersion(id);
      setV(doc);
      setLabel(doc.label);
      setContent(doc.content ?? "");
      if (doc.application_id) setHistory(await api.listVersions(doc.application_id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed.");
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (tab === "Compare" && !compare && !compareError) {
      api.compareVersion(id).then(setCompare).catch((e) => setCompareError(e instanceof Error ? e.message : "Compare failed."));
    }
    if (tab === "Match report" && !report && !reportError && v?.application_id) {
      api.matchReport(v.application_id, id).then(setReport).catch((e) => setReportError(e instanceof Error ? e.message : "Match report failed."));
    }
  }, [tab, compare, compareError, report, reportError, id, v?.application_id]);

  async function save() {
    setBusy(true); setMsg(null);
    try {
      const updated = await api.patchVersion(id, { label, content });
      setV(updated);
      setMsg({
        text: updated.edited_manually
          ? "Saved. Flagged as manually edited. The compare view shows exactly what changed."
          : "Saved.",
        tone: "ok",
      });
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : "Save failed.", tone: "bad" });
    } finally {
      setBusy(false);
    }
  }

  function downloadPdf() {
    getAuthToken().then((t) => fetch(api.versionPdfUrl(id), { headers: t ? { Authorization: `Bearer ${t}` } : {} }))
      .then((r) => { if (!r.ok) throw new Error(`Export failed (${r.status})`); return r.blob(); })
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${(v?.label || "resume").replace(/[^\w\- ]+/g, "").slice(0, 60) || "resume"}.pdf`;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch((e) => setMsg({ text: e instanceof Error ? e.message : "Export failed.", tone: "bad" }));
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!v) return <LoadingBlock rows={3} label="Loading version" />;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Resume · Version"
        title={v.label}
        description="An evidence-preserving reordering of your master resume. Anything you type yourself is flagged and diffable."
        actions={<Button variant="secondary" onClick={downloadPdf}>Export PDF</Button>}
      />

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_260px]">
        <div className="min-w-0 space-y-5">
          <Tabs tabs={TABS} value={tab} onChange={setTab} label="Version views" />
          {msg && <Notice tone={msg.tone === "bad" ? "bad" : "ok"}>{msg.text}</Notice>}
          {v.edited_manually && (
            <Notice tone="warn">
              Manually edited. Content no longer matches the evidence-preserving tailor output. The Compare tab shows the difference.
            </Notice>
          )}
          {tab === "Preview" && <PreviewPanel content={v.content ?? ""} />}
          {tab === "Edit" && (
            <EditPanel label={label} content={content} busy={busy} onLabel={setLabel} onContent={setContent} onSave={save} />
          )}
          {tab === "Compare" && <ComparePanel compare={compare} error={compareError} />}
          {tab === "Match report" && <ReportPanel report={report} error={reportError} />}
        </div>

        <aside className="space-y-5 lg:sticky lg:top-6">
          {history.length > 1 && <HistoryPanel history={history} currentId={v.id} />}
          {v.application_id && (
            <Link href={`/applications/${v.application_id}`} className={cx(linkCls, "block text-sm")}>
              ← Back to application workspace
            </Link>
          )}
          <Panel>
            <Label>Studio note</Label>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
              Tailored versions are reorderings of your real bullets. The system never invents content on your behalf.
            </p>
          </Panel>
        </aside>
      </div>
    </div>
  );
}

function PreviewPanel({ content }: { content: string }) {
  return (
    <Panel>
      <pre className="scroll-quiet max-h-[65vh] overflow-auto whitespace-pre-wrap break-words rounded-md bg-sunken p-4 font-mono text-[12.5px] leading-relaxed text-ink">
        {content}
      </pre>
    </Panel>
  );
}

function EditPanel(p: {
  label: string; content: string; busy: boolean;
  onLabel: (v: string) => void; onContent: (v: string) => void; onSave: () => void;
}) {
  return (
    <Panel className="space-y-4">
      <PanelHeader title="Edit version" meta="Edits are flagged as manual and never silently merged." />
      <Field label="Label">
        <input className={inputCls} value={p.label} onChange={(e) => p.onLabel(e.target.value)} />
      </Field>
      <Field label="Content">
        <textarea className={cx(textareaCls, "min-h-72 font-mono text-[13px]")} value={p.content}
          onChange={(e) => p.onContent(e.target.value)} />
      </Field>
      <Button variant="accent" busy={p.busy} onClick={p.onSave}>{p.busy ? "Saving…" : "Save version"}</Button>
    </Panel>
  );
}

function ComparePanel({ compare, error }: { compare: CompareOut | null; error: string | null }) {
  if (error) return <ErrorState message={error} />;
  if (!compare) return <LoadingBlock rows={2} label="Loading diff" />;
  return (
    <div className="space-y-5">
      <Panel>
        <DefList items={[
          { label: "Line set vs master", value: compare.same_line_set ? "Identical (pure reorder)" : "Changed" },
          { label: "Similarity", value: <span className="font-mono tabular">{compare.similarity}</span> },
          { label: "Added / removed", value: <span className="font-mono tabular">{compare.added.length} / {compare.removed.length}</span> },
        ]} />
      </Panel>
      {compare.added.length > 0 && <DiffLines title="Added (not in your master resume)" lines={compare.added} sign="+" tone="ok" />}
      {compare.removed.length > 0 && <DiffLines title="Removed" lines={compare.removed} sign="−" tone="bad" />}
      <Panel>
        <PanelHeader title="Unified diff" />
        <div className="scroll-quiet max-h-80 overflow-auto rounded-md border border-line bg-sunken py-2 font-mono text-[12px] leading-relaxed">
          {compare.unified_diff.map((line, i) => <DiffLine key={i} line={line} />)}
        </div>
      </Panel>
    </div>
  );
}

function DiffLines({ title, lines, sign, tone }: { title: string; lines: string[]; sign: string; tone: "ok" | "bad" }) {
  return (
    <Panel>
      <PanelHeader title={title} meta={`${lines.length} line${lines.length === 1 ? "" : "s"}`} />
      <ul className="space-y-1.5">
        {lines.map((l, i) => (
          <li key={i} className={cx("break-words border-l-2 py-1 pr-2 pl-3 font-mono text-[12px] leading-relaxed",
            tone === "ok" ? "border-ok bg-ok/10 text-ok" : "border-bad bg-bad/8 text-bad")}>
            <span aria-hidden="true" className="mr-2 select-none">{sign}</span>{l}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function DiffLine({ line }: { line: string }) {
  const tone = line.startsWith("+++") || line.startsWith("---") ? "text-ink-3"
    : line.startsWith("+") ? "bg-ok/10 text-ok"
    : line.startsWith("-") ? "bg-bad/8 text-bad"
    : line.startsWith("@@") ? "text-brand"
    : "text-ink-2";
  return <span className={cx("block px-3 whitespace-pre", tone)}>{line || " "}</span>;
}

function ReportPanel({ report, error }: { report: ReportOut | null; error: string | null }) {
  if (error) return <ErrorState message={error} />;
  if (!report) return <LoadingBlock rows={3} label="Loading report" />;
  const matched = report.rows.filter((r) => r.status === "matched").length;
  const pct = report.coverage * 100;
  return (
    <div className="space-y-5">
      <Panel className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <Label>Coverage</Label>
          <span className="font-mono text-sm tabular text-ink">{matched} of {report.rows.length} requirements</span>
        </div>
        <p className="font-mono text-3xl font-medium tabular text-ink">{pct.toFixed(0)}<span className="ml-1 text-base text-ink-3">%</span></p>
        <Meter value={pct} max={100} tone="brand" label="Requirement coverage" />
        <p className="text-[13px] text-ink-3">of JD requirements evidenced in this version.</p>
      </Panel>
      {report.rows.length === 0 ? (
        <EmptyState title="No requirements" body="The job description produced no requirements to match." />
      ) : (
        <ul className="stagger space-y-2.5">
          {report.rows.map((r, i) => {
            const ok = r.status === "matched";
            return (
              <li key={i} className={cx("rounded-md border-l-2 py-2.5 pr-3 pl-3.5", ok ? "border-ok bg-ok/5" : "border-bad bg-bad/5")}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="min-w-0 break-words text-sm font-medium text-ink">{r.requirement}</p>
                  <Badge tone={ok ? "ok" : "bad"}>{ok ? "Matched" : "Missing"}</Badge>
                </div>
                {r.evidence.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {r.evidence.map((e, j) => <li key={j} className="break-words font-mono text-[12px] leading-relaxed text-ink-2">↳ {e}</li>)}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function HistoryPanel({ history, currentId }: { history: ResumeVersion[]; currentId: string }) {
  return (
    <Panel>
      <PanelHeader title="Version history" meta={`${history.length} versions for this application`} />
      <ul className="space-y-1.5">
        {history.map((h) => (
          <li key={h.id}>
            {h.id === currentId ? (
              <span className="flex items-center gap-2 text-sm font-medium text-ink">
                <Tag>current</Tag>{h.label}
              </span>
            ) : (
              <Link href={`/resume/versions/${h.id}`} className={cx(linkCls, "text-sm")}>{h.label}</Link>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

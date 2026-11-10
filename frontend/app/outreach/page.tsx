"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Badge, Button, EmptyState, Field, Label, Notice, PageHeader, Panel, PanelHeader, Tone, cx, inputCls, linkCls, selectCls, textareaCls,
} from "@/components/ds";
import { useToast } from "@/components/toast";
import { api, type OutreachDraft, type CampaignTask } from "@/lib/api";

const SAMPLE = "company,website,email,name,role,description\nExample,https://example.com,hiring@example.com,,Backend Engineer,Python and FastAPI engineering role\n";
const TOUCH_LINK = cx(linkCls, "inline-flex min-h-9 items-center");

const TONE_BY_STATUS: Record<string, Tone> = {
  succeeded: "ok", accepted: "ok", delivered: "ok",
  failed: "bad", bounced: "bad", cancelled: "bad",
  unknown: "warn",
  queued: "brand", running: "brand", sending: "brand", delivering: "brand",
};
const statusTone = (s?: string): Tone => (s && TONE_BY_STATUS[s]) || "neutral";

export default function OutreachPage() {
  const { confirm } = useToast();
  const [drafts, setDrafts] = useState<OutreachDraft[]>([]);
  const [tasks, setTasks] = useState<CampaignTask[]>([]);
  const [resumes, setResumes] = useState<{ id: string; filename: string }[]>([]);
  const [resume, setResume] = useState("");
  const [csv, setCsv] = useState("");
  const [signature, setSignature] = useState("");
  const [gmail, setGmail] = useState<{ enabled: boolean; connected: boolean } | null>(null);
  const [sends, setSends] = useState<{ draft_id: string; status: string }[]>([]);
  const [selected, setSelected] = useState<OutreachDraft | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filter, setFilter] = useState("");
  const [sendTask, setSendTask] = useState<CampaignTask | null>(null);

  const refresh = useCallback(async () => {
    const [d, t, g, s] = await Promise.all([api.outreachDrafts(), api.campaignTasks(), api.gmailStatus(), api.outreachSends()]);
    setDrafts(d); setTasks(t); setGmail(g); setSends(s);
  }, []);
  useEffect(() => {
    refresh().catch(e => setError(e.message));
    api.listResumes().then(setResumes).catch(e => setError(e.message));
    const timer = setInterval(() => refresh().catch(e => setError(e.message)), 5000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (!sendTask || !["queued", "running"].includes(sendTask.status)) return;
    const timer = setInterval(() => api.taskStatus(sendTask.id).then(setSendTask).catch(e => setError(e.message)), 2000);
    return () => clearInterval(timer);
  }, [sendTask]);

  async function action(fn: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await fn(); await refresh(); } catch (e) { setError(e instanceof Error ? e.message : "Request failed"); }
    finally { setBusy(false); }
  }
  function select(d: OutreachDraft) {
    setSelected(d); setSubject(d.subject); setBody(d.body); setReviewed(false); setSendTask(null);
  }
  async function sendSelected(d: OutreachDraft) {
    const ok = await confirm({
      title: "Queue this email through Gmail?",
      body: `To ${d.recipient_email}. Subject: "${d.subject}". The reviewed version is sent exactly as shown. Gmail acceptance is not delivery.`,
      confirmLabel: "Queue send",
    });
    if (!ok) return;
    await action(async () => {
      const r = await api.outreachSend(d.id, d.payload_sha256);
      setSendTask({ id: r.task_id, status: "queued" }); setReviewed(false);
      setNotice("Send queued. Watch the result below; queuing does not mean delivered.");
    });
  }

  const dirty = !!selected && (subject !== selected.subject || body !== selected.body);
  const sendStatusFor = (draftId: string) => sends.find(s => s.draft_id === draftId)?.status;
  const visibleDrafts = drafts.filter(d => `${d.recipient_email} ${d.subject}`.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Outreach"
        title="Email applications"
        description="Prepare up to 100 company emails, review your resume and message, then send through Gmail."
      />
      {error && <Notice tone="bad" className="mb-5">{error}</Notice>}
      {notice && <Notice tone="ok" className="mb-5">{notice}</Notice>}
      {!gmail?.connected && (
        <Notice tone="warn" className="mb-5">
          Draft preparation is available. <Link className={TOUCH_LINK} href="/integrations">Configure and connect Gmail</Link> to send. No email is sent during import.
        </Notice>
      )}

      <details className="mb-5 rounded-[10px] border border-line bg-surface shadow-1" open={!drafts.length}>
        <summary className="cursor-pointer px-5 py-4 text-[15px] font-semibold text-ink">Import a recipient CSV</summary>
        <div className="space-y-4 border-t border-line p-5">
          <p className="text-[14px] leading-relaxed text-ink-2">
            Required columns: company, website, email. Optional: name, role, description. Only supply addresses you have reviewed. Include the actual job description to tailor the resume; otherwise the original resume text is preserved.
          </p>
          <a className={TOUCH_LINK} href={`data:text/csv;charset=utf-8,${encodeURIComponent(SAMPLE)}`} download="application-recipients.csv">Download CSV template</a>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Master resume">
              <select aria-label="Master resume" className={selectCls} value={resume} onChange={e => setResume(e.target.value)}>
                <option value="">Select a resume</option>
                {resumes.map(r => <option key={r.id} value={r.id}>{r.filename}</option>)}
              </select>
            </Field>
            <Field label="Your name for the email signature">
              <input className={inputCls} value={signature} maxLength={256} onChange={e => setSignature(e.target.value)} />
            </Field>
          </div>
          <Link className={TOUCH_LINK} href="/resume">Upload resume</Link>
          <Field label="Recipient CSV file">
            <input type="file" accept=".csv,text/csv" className="block w-full text-[14px] text-ink-2 file:mr-3 file:h-9 file:rounded-md file:border file:border-line-strong file:bg-surface file:px-3 file:text-ink" onChange={async e => {
              const f = e.target.files?.[0]; if (!f) return;
              if (f.size > 1000000) { setError("CSV must be smaller than 1 MB."); return; }
              setCsv(await f.text());
            }} />
          </Field>
          <Field label="Recipient CSV contents">
            <textarea className={cx(textareaCls, "font-mono text-xs")} rows={6} value={csv} onChange={e => setCsv(e.target.value)} placeholder={SAMPLE} />
          </Field>
          <Button disabled={busy || !resume || !csv.trim() || !signature.trim()} onClick={() => action(async () => {
            const r = await api.campaignPrepare(csv, resume, signature);
            setNotice(`${r.tasks.length} rows accepted; ${r.tasks.filter(t => t.replayed).length} already imported. Drafts appear below as preparation completes.`);
          })}>Prepare drafts</Button>
        </div>
      </details>

      {!!tasks.length && <TaskProgress tasks={tasks} />}

      <div className="grid items-start gap-5 lg:grid-cols-[320px_1fr]">
        <Panel padded={false}>
          <div className="px-5 pt-5"><PanelHeader title={`Drafts (${drafts.length})`} /></div>
          <div className="px-5 pb-3">
            <input aria-label="Search drafts" type="search" placeholder="Search recipient or subject" className={inputCls} value={filter} onChange={e => setFilter(e.target.value)} />
          </div>
          <ul className="max-h-[640px] divide-y divide-line overflow-auto scroll-quiet border-t border-line">
            {visibleDrafts.map(d => (
              <li key={d.id}>
                <button type="button" onClick={() => select(d)} aria-pressed={selected?.id === d.id}
                  className={cx("flex min-h-14 w-full flex-col items-start gap-1 px-5 py-3 text-left transition-colors", selected?.id === d.id ? "bg-sunken" : "hover:bg-sunken/60")}>
                  <span className="max-w-full truncate font-mono text-[13px] text-ink">{d.recipient_email}</span>
                  <span className="max-w-full truncate text-[13px] text-ink-2">{d.subject}</span>
                  <Badge tone={statusTone(sendStatusFor(d.id))}>{sendStatusFor(d.id) ?? "Draft — unsent"}</Badge>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
        {selected ? (
          <DraftReview
            draft={selected}
            subject={subject}
            body={body}
            onSubject={v => { setSubject(v); setReviewed(false); }}
            onBody={v => { setBody(v); setReviewed(false); }}
            dirty={dirty}
            reviewed={reviewed}
            onReviewed={setReviewed}
            busy={busy}
            gmailReady={!!gmail?.connected && !!gmail?.enabled}
            sendStatus={sendStatusFor(selected.id)}
            sendTask={sendTask}
            onSave={() => action(async () => { const d = await api.outreachEdit(selected.id, subject, body); select(d); setNotice("Draft saved. Review the updated message before sending."); })}
            onSend={() => sendSelected(selected)}
          />
        ) : (
          <EmptyState title="No draft selected" body="Select a draft to review." />
        )}
      </div>
    </div>
  );
}

function TaskProgress({ tasks }: { tasks: CampaignTask[] }) {
  const count = (s: string[]) => tasks.filter(t => s.includes(t.status)).length;
  return (
    <details className="mb-5 rounded-[10px] border border-line bg-surface px-5 py-4 shadow-1">
      <summary className="cursor-pointer text-[14px] text-ink">
        Preparation progress: <span className="font-mono tabular">{count(["succeeded"])}</span> completed · <span className="font-mono tabular">{count(["failed"])}</span> failed · <span className="font-mono tabular">{count(["queued", "running"])}</span> pending
      </summary>
      <ul className="stagger mt-3 max-h-60 divide-y divide-line overflow-auto text-[14px]">
        {tasks.map(t => (
          <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <span className="min-w-0 break-words text-ink-2">
              {t.company} · <span className="font-mono text-[13px]">{t.recipient_email}</span>
              {t.error_detail && ` — ${t.error_detail}`}
            </span>
            <Badge tone={statusTone(t.status)}>{t.status}</Badge>
          </li>
        ))}
      </ul>
    </details>
  );
}

type DraftReviewProps = {
  draft: OutreachDraft;
  subject: string;
  body: string;
  onSubject: (v: string) => void;
  onBody: (v: string) => void;
  dirty: boolean;
  reviewed: boolean;
  onReviewed: (v: boolean) => void;
  busy: boolean;
  gmailReady: boolean;
  sendStatus?: string;
  sendTask: CampaignTask | null;
  onSave: () => void;
  onSend: () => void;
};

function DraftReview(p: DraftReviewProps) {
  const { draft } = p;
  return (
    <Panel className="space-y-5">
      <PanelHeader title={`Review email to ${draft.recipient_email}`} />
      <ApprovalPath dirty={p.dirty} reviewed={p.reviewed} sendStatus={p.sendStatus} sendTask={p.sendTask} />
      <Field label="Subject">
        <input className={inputCls} value={p.subject} onChange={e => p.onSubject(e.target.value)} />
      </Field>
      <Field label="Message">
        <textarea className={textareaCls} rows={12} value={p.body} onChange={e => p.onBody(e.target.value)} />
      </Field>
      <Button variant="secondary" disabled={!p.dirty || p.busy} onClick={p.onSave}>Save edits</Button>
      <div className="rounded-md bg-sunken p-3">
        <Label>Payload SHA-256</Label>
        <p className="mt-1.5 break-all font-mono text-[12px] text-ink-2">{draft.payload_sha256}</p>
      </div>
      <details className="rounded-md border border-line p-4">
        <summary className="cursor-pointer text-[14px] font-medium text-ink">Resume attachment (PDF)</summary>
        <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-sunken p-3 font-mono text-[12px] text-ink-2">{draft.attachment_preview || "No attachment"}</pre>
        {draft.resume_version_id && <Link className={cx(TOUCH_LINK, "mt-2")} href={`/resume/versions/${draft.resume_version_id}`}>Open resume and download PDF</Link>}
      </details>
      <div className="space-y-2">
        <Label>Facts and contact review</Label>
        {draft.factuality_findings.length === 0
          ? <p className="text-[14px] text-ink-3">No findings reported.</p>
          : draft.factuality_findings.map((f, i) => <Notice key={i} tone="warn">{f.detail}</Notice>)}
      </div>
      <label className="flex items-start gap-3 text-[14px] text-ink-2">
        <input type="checkbox" className="mt-1 size-4 shrink-0 accent-brand" checked={p.reviewed} onChange={e => p.onReviewed(e.target.checked)} />
        I reviewed this recipient, message, and resume, and approve sending this exact version.
      </label>
      <Button variant="accent" disabled={p.busy || p.dirty || !p.reviewed || !p.gmailReady} onClick={p.onSend}>
        Approve and queue Gmail send
      </Button>
      {p.sendTask && (
        <p role="status" className="text-[14px] text-ink-2">
          Send task: <Badge tone={statusTone(p.sendTask.status)}>{p.sendTask.status}</Badge>
          {p.sendTask.error_detail ? ` — ${p.sendTask.error_detail}` : ""}
        </p>
      )}
      <p className="text-[13px] text-ink-3">Gmail acceptance is not delivery confirmation. Daily limits and quiet hours apply. Sync replies in Integrations.</p>
    </Panel>
  );
}

function ApprovalPath({ dirty, reviewed, sendStatus, sendTask }: { dirty: boolean; reviewed: boolean; sendStatus?: string; sendTask: CampaignTask | null }) {
  const reviewState = dirty
    ? { text: "Save edits first", tone: "warn" as Tone }
    : reviewed ? { text: "Approved for this version", tone: "ok" as Tone }
    : { text: "Not yet", tone: "neutral" as Tone };
  const sent = sendTask
    ? { text: sendTask.status, tone: statusTone(sendTask.status) }
    : sendStatus
      ? { text: sendStatus, tone: statusTone(sendStatus) }
      : { text: "Not sent", tone: "neutral" as Tone };
  const steps = [
    { name: "Draft", text: "Prepared", tone: "ok" as Tone },
    { name: "Reviewed", ...reviewState },
    { name: "Sent", ...sent },
  ];
  return (
    <ol aria-label="Approval steps" className="grid gap-2 sm:grid-cols-3">
      {steps.map(s => (
        <li key={s.name} className="rounded-md border border-line bg-sunken/50 p-3">
          <Label>{s.name}</Label>
          <div className="mt-2"><Badge tone={s.tone}>{s.text}</Badge></div>
        </li>
      ))}
    </ol>
  );
}

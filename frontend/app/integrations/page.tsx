"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Notice, PageHeader, Panel, PanelHeader } from "@/components/ds";
import { useToast } from "@/components/toast";
import { api } from "@/lib/api";

interface Provider {
  name: string;
  active: boolean;
  model: string;
  status: string;
  note?: string;
}

type Gmail = { enabled: boolean; connected: boolean; email: string | null };

function providerLabel(p: Provider): string {
  if (p.active) return "active";
  return p.name === "grok" ? "coming soon" : p.status.replace(/_/g, " ");
}

export default function Integrations() {
  const { toast, confirm } = useToast();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [gmail, setGmail] = useState<Gmail | null>(null);
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
    const ok = await confirm({
      title: "Disconnect Gmail?",
      body: `${gmail?.email ?? "This account"} will be disconnected. Outreach emails cannot be sent until Gmail is connected again.`,
      confirmLabel: "Disconnect",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.gmailDisconnect();
      setGmail((current) => current ? { ...current, connected: false, email: null } : current);
      toast("Gmail disconnected.", "ok");
    } catch (e) { setError(e instanceof Error ? e.message : "Disconnect failed."); }
  }

  const gmailBadge = gmail?.connected
    ? <Badge tone="ok" dot>Connected</Badge>
    : gmail?.enabled
      ? <Badge>Not connected</Badge>
      : <Badge>Not configured</Badge>;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="Connections" title="Integrations" description="Active providers and future boundaries." />
      {error && <Notice tone="bad" className="mb-5">{error}</Notice>}
      {notice && <Notice tone="ok" className="mb-5">{notice}</Notice>}
      <div className="grid items-start gap-5 lg:grid-cols-[1fr_300px]">
        <div className="space-y-5">
          <Panel>
            <PanelHeader
              title="Gmail outreach"
              meta={gmail?.connected ? `Connected as ${gmail.email}.` : "No Gmail account connected."}
              action={gmailBadge}
            />
            <p className="text-[13px] text-ink-3">Provider acceptance is not delivery confirmation. Replies are checked when you sync.</p>
            {!gmail?.enabled && (
              <Notice tone="warn" className="mt-4">Gmail is disabled until the backend OAuth client and token encryption key are configured.</Notice>
            )}
            <div className="mt-5 flex flex-wrap gap-2">
              {gmail?.connected ? (
                <>
                  <Button variant="secondary" onClick={syncGmail}>Sync replies</Button>
                  <Button variant="danger" onClick={disconnectGmail}>Disconnect</Button>
                </>
              ) : (
                <Button variant="accent" disabled={!gmail?.enabled} onClick={connectGmail}>Connect Gmail</Button>
              )}
            </div>
          </Panel>
          <Panel padded={false}>
            <div className="px-5 pt-5"><PanelHeader title="AI providers" /></div>
            <ul className="stagger divide-y divide-line">
              {providers.map((p) => (
                <li key={p.name} className="px-5 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium capitalize text-ink">{p.name}</p>
                      <p className="mt-0.5 text-[13px] text-ink-3">Model <span className="break-all font-mono text-ink-2">{p.model || "—"}</span></p>
                    </div>
                    <Badge tone={p.active ? "ok" : "neutral"} dot={p.active}>{providerLabel(p)}</Badge>
                  </div>
                  {p.name === "grok" && (
                    <Notice tone="warn" className="mt-3">
                      Coming Soon — the Grok boundary is defined but disabled. Core features never route here.
                    </Notice>
                  )}
                  {p.note && p.name !== "grok" && <p className="mt-2 text-[13px] text-ink-3">{p.note}</p>}
                </li>
              ))}
            </ul>
          </Panel>
        </div>
        <Panel>
          <PanelHeader title="Boundary note" />
          <p className="text-[14px] leading-relaxed text-ink-2">
            Providers implement one interface; the app never imports Ollama, OpenAI, or Grok directly. Enabling Grok later means configuration only — no core rewiring.
          </p>
        </Panel>
      </div>
    </div>
  );
}

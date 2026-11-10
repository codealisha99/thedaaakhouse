"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Button, EmptyState, Field, Notice, PageHeader, Panel, PanelHeader, cx, inputCls, linkCls, selectCls } from "@/components/ds";
import { api } from "@/lib/api";

type Opportunity = { id: string; kind: string; title: string | null; company: string | null; domain: string | null };
type Contact = { id: string; opportunity_id: string | null; name: string | null; role: string | null; email: string | null; source_url: string | null; address_source: string; verification_state: string; review_required: boolean };

const TOUCH_LINK = cx(linkCls, "inline-flex min-h-9 items-center");

export default function OpportunitiesPage() {
  const [items, setItems] = useState<Opportunity[]>([]); const [selected, setSelected] = useState("");
  const [contacts, setContacts] = useState<Contact[]>([]); const [contactPageUrl, setContactPageUrl] = useState<string | null>(null);
  const [url, setUrl] = useState(""); const [name, setName] = useState("");
  const [notice, setNotice] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const result = await api.listOpportunities();
      setItems(result.items);
      if (!selected && result.items[0]) setSelected(result.items[0].id);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load opportunities."); }
  }, [selected]);

  const refreshContacts = useCallback(async (id = selected) => {
    if (!id) return;
    try {
      const result = await api.opportunityContacts(id);
      setContacts(result.contacts);
      const latest = result.research_runs[0]?.result as { contact_page_url?: string | null } | undefined;
      setContactPageUrl(latest?.contact_page_url || null);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load contacts."); }
  }, [selected]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { if (selected) void refreshContacts(selected); }, [selected, refreshContacts]);

  async function addStartup(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const row = await api.createStartupProspect({ url, name: name || undefined });
      setNotice("Startup prospect saved. No job listing was created.");
      setName(""); setUrl("");
      await refresh();
      setSelected(row.id);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save startup."); }
    finally { setBusy(false); }
  }

  async function makeDraft(contact: Contact) {
    if (!contact.email || !contact.opportunity_id) return;
    setBusy(true); setError("");
    try {
      const draft = await api.createOutreachDraft({
        opportunity_id: contact.opportunity_id,
        recipient_email: contact.email,
        recipient_name: contact.name || undefined,
        recipient_role: contact.role || undefined,
        recipient_identity: "unknown",
        contact_source_url: contact.source_url || undefined,
        contact_source_kind: contact.address_source === "published" ? "published" : "user_supplied",
      });
      setNotice(`Unsent outreach draft created (${draft.id}). Review it before approval or sending.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create the draft."); }
    finally { setBusy(false); }
  }

  async function discover() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      const result = await api.discoverContacts(selected, crypto.randomUUID());
      setNotice(`Contact research queued (${result.task_id}). Refresh contacts after the task completes.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Contact research could not be queued."); }
    finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow="Research" title="Opportunities & contacts" description="Sourced public contact research." />
      {error && <Notice tone="bad" className="mb-5">{error}</Notice>}
      {notice && <Notice tone="ok" className="mb-5">{notice}</Notice>}
      <div className="grid items-start gap-5 lg:grid-cols-[320px_1fr]">
        <form onSubmit={addStartup}>
          <Panel className="space-y-4">
            <PanelHeader title="Add a startup prospect" meta="Use a company website you want to research. This creates no synthetic vacancy." />
            <Field label="Company website">
              <input required type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://company.example" className={inputCls} />
            </Field>
            <Field label="Company name (optional)">
              <input value={name} onChange={e => setName(e.target.value)} className={inputCls} />
            </Field>
            <Button type="submit" busy={busy} className="w-full">Add</Button>
          </Panel>
        </form>
        <Panel className="space-y-4">
          <PanelHeader
            title="Research a company"
            action={
              <div className="flex flex-wrap gap-2">
                <Button variant="ghost" onClick={() => void refresh()}>Refresh opportunities</Button>
                <Button variant="ghost" onClick={() => void refreshContacts()}>Refresh contacts</Button>
              </div>
            }
          />
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Opportunity" className="min-w-64 flex-1">
              <select value={selected} onChange={e => setSelected(e.target.value)} className={selectCls}>
                <option value="">Choose an opportunity</option>
                {items.map(o => (
                  <option key={o.id} value={o.id}>
                    {o.company || o.domain || "Unknown company"}{o.kind === "vacancy" ? ` — ${o.title || "Vacancy"}` : " — startup prospect"}
                  </option>
                ))}
              </select>
            </Field>
            <Button variant="accent" disabled={!selected || busy} onClick={() => void discover()}>Find public contacts</Button>
          </div>
          {contacts.length === 0 ? (
            <EmptyState title="No contacts yet" body="Research uses the official company site and does not guess email addresses." />
          ) : (
            <ul className="stagger space-y-3">
              {contacts.map(c => (
                <li key={c.id}>
                  <article className="rounded-md border border-line p-4">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                      <strong className="font-medium text-ink">{c.name || "Identity not established"}</strong>
                      {c.role && <span className="text-[14px] text-ink-2">{c.role}</span>}
                    </div>
                    <p className="mt-1.5 break-all font-mono text-[13px] text-ink-2">{c.email || "No published email"}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Badge>{c.address_source}</Badge>
                      <Badge>{c.verification_state}</Badge>
                      <Badge tone={c.review_required ? "warn" : "ok"} dot>{c.review_required ? "Review required" : "Reviewed"}</Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-4">
                      {c.source_url && <a className={TOUCH_LINK} href={c.source_url} target="_blank" rel="noreferrer">Source page</a>}
                      {c.email && (
                        <Button variant="secondary" disabled={busy} onClick={() => void makeDraft(c)}>Create unsent draft</Button>
                      )}
                    </div>
                  </article>
                </li>
              ))}
            </ul>
          )}
          {contactPageUrl && (
            <Notice tone="neutral">
              No suitable person found? Use the <a className={TOUCH_LINK} href={contactPageUrl} target="_blank" rel="noreferrer">company contact page</a> as a manual handoff.
            </Notice>
          )}
          <p className="text-[13px] text-ink-3">Published addresses remain unverified. Review identity and source before using a contact in outreach.</p>
        </Panel>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBox } from "@/components/ui";
import { Letterhead, PaperCard, Postmark, StampBadge, StickyNote, TruckLoader, WaxSealButton } from "@/components/post/postal";
import { pinFor, stageFor, stageOf } from "@/components/post/journey";
import { api } from "@/lib/api";
import type { Application } from "@/types";

function Envelope({ app }: { app: Application }) {
  const stage = stageOf(stageFor(app.status, app.updated_at));
  return (
    <Link href={`/applications/${app.id}`}>
      <PaperCard id={app.id} className="group relative overflow-hidden p-4">
        <Postmark city={app.company || "NOWHERE"} className="absolute -right-2 -top-2" />
        <div className="absolute right-3 top-3"><StampBadge text={stage.title} color={stage.color} denom={pinFor(app.id)} /></div>
        <div className="max-w-[70%] font-mono text-sm leading-relaxed">
          <p><span className="text-postmark">To:</span> <strong>{app.company || "Untitled company"}</strong></p>
          <p><span className="text-postmark">Attn:</span> {app.role}</p>
          <p className="text-xs text-postmark">Ref: DH-{pinFor(app.id)} · {app.status.replace("_", " ")}</p>
        </div>
        <div className="route-line mt-3" aria-hidden="true" />
        <p className="mt-1 font-hand text-lg text-postmark group-hover:text-postred">open this letter →</p>
      </PaperCard>
    </Link>
  );
}

export default function Applications() {
  const [apps, setApps] = useState<Application[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    api.listApps({}).then((a) => { setApps(a); setState("ready"); })
      .catch((e) => { setError(e instanceof Error ? e.message : "load failed"); setState("error"); });
  }, []);

  const count = (stages: string[]) =>
    apps.filter((a) => stages.includes(stageFor(a.status, a.updated_at))).length;
  const posted = count(["posted"]);
  const transit = count(["transit"]);
  const interviews = count(["out"]);
  const offers = count(["delivered"]);
  const followups = apps
    .filter((a) => a.next_step || a.interview_date)
    .slice(0, 4);

  return (
    <div className="space-y-6">
      <Letterhead
        title="The Front Counter"
        subtitle="Applications · every letter accounted for"
        action={<WaxSealButton href="/applications/new">Post a new letter</WaxSealButton>}
      />

      {state === "loading" && <TruckLoader label="Sorting the morning post…" />}
      {state === "error" && <ErrorBox message={error} />}

      {state === "ready" && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              { n: posted, label: "Posted", color: "#C8102E" },
              { n: transit, label: "In Transit", color: "#2E6FBF" },
              { n: interviews, label: "Interviews", color: "#5B3A8C" },
              { n: offers, label: "Offers", color: "#1E7B4D" },
            ].map((s) => (
              <Link key={s.label} href="/tracker">
                <PaperCard id={s.label} className="perforated p-4 text-center" tilt={false}>
                  <p className="font-serif text-4xl font-bold" style={{ color: s.color }}>{s.n}</p>
                  <p className="mt-1 font-mono text-xs font-bold uppercase tracking-[0.2em]">{s.label}</p>
                </PaperCard>
              </Link>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-3 lg:col-span-2">
              <h3 className="font-serif text-xl font-bold text-postalnavy">Recent letters</h3>
              {apps.length === 0 && (
                <p className="font-hand text-2xl text-postmark">No letters yet. Post your first application.</p>
              )}
              {apps.slice(0, 6).map((a) => <Envelope key={a.id} app={a} />)}
            </div>
            <div className="space-y-3">
              <h3 className="font-serif text-xl font-bold text-postalnavy">Today&apos;s Post</h3>
              <p className="font-mono text-xs uppercase tracking-[0.18em] text-postmark">follow-ups due</p>
              {followups.length === 0 && (
                <StickyNote>Nothing due. The pigeons are resting.</StickyNote>
              )}
              {followups.map((a) => (
                <Link key={a.id} href={`/applications/${a.id}`}>
                  <StickyNote>
                    {a.company} — {a.next_step || `interview ${a.interview_date ?? ""}`}
                  </StickyNote>
                </Link>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

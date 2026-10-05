"use client";

import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Field, inputCls } from "@/components/ui";
import { Letterhead, TypedMemo, WaxSealButton } from "@/components/post/postal";
import { api } from "@/lib/api";

export default function Analyzer() {
  const router = useRouter();
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("");
  const [jobUrl, setJobUrl] = useState("");
  const [jd, setJd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"writing" | "opening" | "reading">("writing");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPhase("opening");
    try {
      const app = await api.createApp({
        company, role: role || "Untitled role", location: location || undefined,
        job_url: jobUrl || undefined, raw_jd: jd, status: "saved",
        date_saved: new Date().toISOString().slice(0, 10),
      });
      setPhase("reading");
      setTimeout(() => router.push(`/applications/${app.id}`), 900);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
      setPhase("writing");
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Letterhead title="Letter Opening Desk" subtitle="Job Analyzer · slit it open, read every line" />

      <div className="grid gap-5 md:grid-cols-2">
        <form onSubmit={submit} className="paper-keep space-y-3 rounded-sm border border-kraft/60 bg-envelope p-5 shadow-paper">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="To (company)"><input className={inputCls} value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme" /></Field>
            <Field label="Attn (role)"><input className={inputCls} value={role} onChange={(e) => setRole(e.target.value)} placeholder="AI Engineer" /></Field>
            <Field label="Station (location)"><input className={inputCls} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Remote" /></Field>
            <Field label="Postmark (job URL)"><input className={inputCls} value={jobUrl} onChange={(e) => setJobUrl(e.target.value)} placeholder="https://…" /></Field>
          </div>
          <Field label="The letter (job description)">
            <textarea
              className="lined-paper min-h-48 w-full rounded-sm border border-kraft px-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-postred/60"
              value={jd} onChange={(e) => setJd(e.target.value)}
              placeholder="Paste the full job description…" />
          </Field>
          {error && <p className="rounded-sm border border-dashed border-postred/60 bg-postred/5 p-2.5 font-mono text-sm text-postred">{error}</p>}
          <WaxSealButton>Slit open &amp; file</WaxSealButton>
        </form>

        <div className="flex flex-col items-center justify-start gap-4">
          {/* envelope that opens on submit */}
          <div className="relative h-36 w-64" aria-hidden="true" style={{ perspective: 600 }}>
            <div className="absolute inset-x-0 top-0 h-1/2 origin-top rounded-t-md border border-kraft bg-kraft/70"
              style={phase === "writing" ? undefined : { animation: "none" }}>
              <motion.div
                animate={phase === "writing" ? { rotateX: 0 } : { rotateX: [0, -160, -160] }}
                transition={{ duration: phase === "reading" ? 0.9 : 0.6, ease: "easeInOut" }}
                className="h-full w-full origin-top rounded-t-md border-b-2 border-dashed border-postalnavy/30 bg-kraft"
                style={{ transformStyle: "preserve-3d" }}
              />
            </div>
            <div className="absolute inset-0 rounded-md border border-kraft bg-envelope shadow-paper" style={{ clipPath: "polygon(0 38%, 50% 62%, 100% 38%, 100% 100%, 0 100%)" }} />
            <motion.div
              className="absolute inset-x-8 top-2 rounded-sm border border-kraft bg-paper p-2 text-center font-mono text-[11px] uppercase tracking-[0.2em] text-postmark shadow-paper"
              animate={phase === "writing" ? { y: 34, opacity: 0.85 } : { y: -14, opacity: 1 }}
              transition={{ duration: 0.7, ease: "easeOut" }}
            >
              {phase === "writing" ? "sealed letter" : phase === "opening" ? "opening…" : "filed ✓"}
            </motion.div>
          </div>

          <TypedMemo title="Clerk's memo">
            {phase === "writing" && <p>Paste the letter on the left. I&apos;ll extract required skills, duties, keywords, and experience — filed straight into your tracker.</p>}
            {phase === "opening" && <p>Slitting the envelope… reading every line…</p>}
            {phase === "reading" && <p>Read and filed. Taking you to the letter&apos;s workspace…</p>}
          </TypedMemo>
        </div>
      </div>
    </div>
  );
}

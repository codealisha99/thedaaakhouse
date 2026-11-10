import Link from "next/link";
import { Mark } from "@/components/brand";
import { LandingHeader, PrimaryCta, Reveal } from "@/components/landing/chrome";
import { AtsDemo, OutreachDemo, PrepDemo, TailorDemo, TrackingSlip } from "@/components/landing/demos";
import { HowItWorks } from "@/components/landing/how";

const SCATTER = [
  { what: "A spreadsheet row", lost: "with a status you last updated two weeks ago" },
  { what: "resume_final_v7.pdf", lost: "and no record of which job it went to" },
  { what: "The job description", lost: "in a tab that closed when the posting expired" },
  { what: "An ATS score", lost: "from a tool that won’t say how it was computed" },
  { what: "Interview notes", lost: "in a doc you can’t find the morning of" },
];

const ALSO = [
  { name: "Discover jobs", body: "Configure job-board sources, scan them, and save listings straight onto your tracker." },
  { name: "Career fit", body: "Score a job against your career profile: target, adjacent or poor, with reasons, gaps and conflicts." },
  { name: "Compare jobs", body: "Put applications side by side: fit, ATS score and missing skills." },
  { name: "Learning hub", body: "Study plans built from the JD, missing skills first, with exercises and knowledge checks." },
  { name: "Company research", body: "Facts extracted from the company’s real pages, each with its source and retrieval date." },
  { name: "Startup contacts", body: "Research published contact details for a startup, flagged when they need your review." },
];

const PRINCIPLES = [
  { n: "01", title: "Extractive, not generative", body: "Tailoring reorders the bullets you wrote. Anything a job asks for that your profile doesn’t show is reported as missing — never written in." },
  { n: "02", title: "Methodology on the page", body: "The ATS score shows its weights — 50% keywords, 25% skills, 15% experience, 10% formatting — and which requirements matched, with evidence." },
  { n: "03", title: "Nothing sends without you", body: "Outreach email is drafted, checked for unsupported claims, and sent only after you approve that exact text." },
  { n: "04", title: "Your data, your backend", body: "Runs on your own FastAPI server with SQLite or Postgres. Every record is scoped to your account." },
];

const FAQ = [
  { q: "Will it rewrite my resume?", a: "No. Tailored versions reorder and select from your existing bullets. Each change records the requirement it targets and the source line it came from. Your master resume is never overwritten." },
  { q: "How is the ATS score calculated?", a: "It’s a weighted score: keyword match 50%, skills 25%, experience 15%, formatting 10%. The breakdown, matched and missing terms, and formatting checks are shown with every run." },
  { q: "Can it email companies on my behalf?", a: "Only when you ask, and only after review. With Gmail connected, drafts are checked for claims your resume doesn’t support, and a draft is sent only when you approve it." },
  { q: "Where is my data stored?", a: "On the backend you run — SQLite for local development or Postgres in production. Accounts are local or via Clerk, depending on how your server is configured." },
  { q: "Do I need an AI provider?", a: "Core tracking, analysis, ATS scoring and tailoring are deterministic. The Integrations page shows which AI providers your server has configured." },
];

function SectionIntro({ eyebrow, title, body }: { eyebrow: string; title: React.ReactNode; body?: string }) {
  return (
    <div data-reveal className="max-w-2xl">
      <p className="font-mono text-[12px] uppercase tracking-[0.12em] text-accent">{eyebrow}</p>
      <h2 className="mt-4 font-display text-[42px] leading-[1.02] tracking-[-0.01em] text-ink sm:text-[56px]">{title}</h2>
      {body && <p className="mt-5 text-[17px] leading-relaxed text-ink-2">{body}</p>}
    </div>
  );
}

function Feature({ eyebrow, title, body, points, demo, flip }: {
  eyebrow: string; title: string; body: string; points: string[]; demo: React.ReactNode; flip?: boolean;
}) {
  return (
    <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-20">
      <div data-reveal className={flip ? "lg:order-2" : ""}>
        <p className="font-mono text-[12px] uppercase tracking-[0.12em] text-ink-3">{eyebrow}</p>
        <h3 className="mt-3 font-display text-[36px] leading-[1.05] text-ink sm:text-[44px]">{title}</h3>
        <p className="mt-4 max-w-lg text-[16px] leading-relaxed text-ink-2">{body}</p>
        <ul className="mt-6 space-y-2.5">
          {points.map((p) => (
            <li key={p} className="flex gap-3 text-[15px] text-ink-2">
              <span className="mt-[9px] size-1.5 shrink-0 rounded-full bg-accent" aria-hidden="true" />{p}
            </li>
          ))}
        </ul>
      </div>
      <div data-reveal className={flip ? "lg:order-1" : ""}>{demo}</div>
    </div>
  );
}

export default function Landing() {
  return (
    <div className="overflow-x-clip">
      <Reveal />
      <LandingHeader />

      <main id="main">
        {/* Hero */}
        <section className="mx-auto grid max-w-[1200px] items-center gap-16 px-5 pt-14 pb-24 sm:px-8 lg:grid-cols-[1.08fr_1fr] lg:pt-24 lg:pb-32">
          <div className="rise-in">
            <p className="font-mono text-[12px] uppercase tracking-[0.12em] text-ink-3">Job-search workspace · <span className="text-ink-2">daak</span>, Hindi for post</p>
            <h1 className="mt-6 font-display text-[54px] leading-[0.98] tracking-[-0.015em] text-ink sm:text-[76px] lg:text-[88px]">
              Every application, tracked like <em className="text-accent">registered post.</em>
            </h1>
            <p className="mt-7 max-w-xl text-[18px] leading-relaxed text-ink-2">
              Each job you apply to is filed with its description, the exact resume you sent, an ATS score that shows its maths, interview prep and every status change — so you always know where it is and what to do next.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <PrimaryCta />
              <a href="#how" className="inline-flex h-12 items-center gap-2 rounded-md px-4 text-[15px] font-medium text-ink-2 transition-colors hover:text-ink">
                Follow an application <span aria-hidden="true">↓</span>
              </a>
            </div>
          </div>
          <div className="mx-auto w-full max-w-[460px] lg:max-w-none">
            <TrackingSlip />
            <p className="mt-10 text-center text-[13px] text-ink-3">Select a stop to step through the route.</p>
          </div>
        </section>

        {/* Problem */}
        <section className="border-y border-line bg-surface">
          <div className="mx-auto grid max-w-[1200px] gap-14 px-5 py-24 sm:px-8 lg:grid-cols-[1fr_1.1fr] lg:gap-24 lg:py-32">
            <SectionIntro eyebrow="The problem" title={<>A job search leaks in <em>five places.</em></>}
              body="Applications get sent from one place, tracked in another and prepared for in a third. By the interview, the link between the job, the resume you sent and what you need to study is gone." />
            <ol data-reveal className="divide-y divide-line border-y border-line">
              {SCATTER.map((s, i) => (
                <li key={s.what} className="grid grid-cols-[2.5rem_1fr] gap-x-2 py-5">
                  <span className="font-mono text-[12px] tabular text-ink-3">0{i + 1}</span>
                  <p className="text-[16px]"><span className="font-medium text-ink">{s.what}</span> <span className="text-ink-3">{s.lost}</span></p>
                </li>
              ))}
              <li className="grid grid-cols-[2.5rem_1fr] gap-x-2 py-5">
                <span className="mt-1.5 size-2.5 rounded-full bg-accent" aria-hidden="true" />
                <p className="text-[16px] font-medium text-ink">thedaaakhouse files all five on one record, connected to each other.</p>
              </li>
            </ol>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="mx-auto max-w-[1200px] scroll-mt-20 px-5 py-24 sm:px-8 lg:py-32">
          <SectionIntro eyebrow="How it works" title="One route, from draft to offer."
            body="Applications move along five stops. Rejections and withdrawals branch off where they happened, and anything silent for 30 days is marked a dead letter." />
          <div className="mt-20"><HowItWorks /></div>
        </section>

        {/* Features */}
        <section id="features" className="scroll-mt-20 border-t border-line bg-surface">
          <div className="mx-auto max-w-[1200px] space-y-28 px-5 py-24 sm:px-8 lg:space-y-40 lg:py-32">
            <Feature eyebrow="Tailor" title="Tailoring that can’t make things up."
              body="A tailored version starts from your master resume and only reorders and selects. Every move records which requirement it serves and the line of yours it used."
              points={["Masters are never overwritten; versions attach to the application", "Line diff and requirement-by-requirement match report", "Missing skills are listed, not invented"]}
              demo={<TailorDemo />} />
            <Feature flip eyebrow="ATS check" title="A score that shows its maths."
              body="See the weight of each category, what it scored and how much it added. Matched and missing requirements come with the evidence from your resume."
              points={["Run against any resume version", "An optimiser retries toward a target score and keeps the history", "Formatting checks listed pass or fail"]}
              demo={<AtsDemo />} />
            <Feature eyebrow="Prepare" title="Prep that cites its source."
              body="Interview questions come from the job description, each with a category and a reason. Practise in the arena, where every answer is scored for what it covered and what it missed."
              points={["Resume, technical, DSA, system design, CS, AI/ML and mock sessions", "Adaptive follow-up questions", "Summaries of strengths and weaknesses by category"]}
              demo={<PrepDemo />} />
            <Feature flip eyebrow="Outreach" title="Email that waits for your approval."
              body="Prepare a campaign from a CSV, review each draft, and send through your own Gmail. Drafts are checked for claims your resume doesn’t support."
              points={["Approval is tied to a hash of the exact text", "Every send attempt is logged", "Disconnect Gmail at any time"]}
              demo={<OutreachDemo />} />
          </div>
        </section>

        {/* Also on the desk */}
        <section className="mx-auto max-w-[1200px] px-5 py-24 sm:px-8 lg:py-32">
          <SectionIntro eyebrow="Also on the desk" title="The rest of the search, in the same place." />
          <dl data-reveal className="mt-14 grid gap-x-12 border-t border-line sm:grid-cols-2 lg:grid-cols-3">
            {ALSO.map((a) => (
              <div key={a.name} className="border-b border-line py-7">
                <dt className="text-[16px] font-semibold text-ink">{a.name}</dt>
                <dd className="mt-2 text-[15px] leading-relaxed text-ink-2">{a.body}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Principles */}
        <section id="principles" className="scroll-mt-20 bg-ink text-on-ink">
          <div className="mx-auto max-w-[1200px] px-5 py-24 sm:px-8 lg:py-32">
            <div data-reveal className="max-w-2xl">
              <p className="font-mono text-[12px] uppercase tracking-[0.12em] text-accent">Principles</p>
              <h2 className="mt-4 font-display text-[42px] leading-[1.02] sm:text-[56px]">Evidence over invention.</h2>
            </div>
            <div className="mt-16 grid gap-px overflow-hidden rounded-2xl bg-on-ink/12 sm:grid-cols-2">
              {PRINCIPLES.map((p) => (
                <div key={p.n} data-reveal className="bg-ink p-8 lg:p-10">
                  <p className="font-mono text-[12px] tabular opacity-50">{p.n}</p>
                  <h3 className="mt-6 font-display text-[30px] leading-tight">{p.title}</h3>
                  <p className="mt-3 text-[15px] leading-relaxed opacity-70">{p.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="mx-auto grid max-w-[1200px] scroll-mt-20 gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[1fr_1.4fr] lg:gap-24 lg:py-32">
          <SectionIntro eyebrow="FAQ" title="Questions, answered plainly." />
          <div data-reveal className="divide-y divide-line border-y border-line">
            {FAQ.map((f) => (
              <details key={f.q} className="group py-1">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-6 rounded-md py-4 text-[17px] font-medium text-ink [&::-webkit-details-marker]:hidden">
                  {f.q}
                  <span className="relative size-4 shrink-0 text-ink-3" aria-hidden="true">
                    <span className="absolute top-1/2 left-0 h-px w-4 bg-current" />
                    <span className="absolute top-0 left-1/2 h-4 w-px bg-current transition-transform duration-[var(--dur-2)] group-open:scale-y-0" />
                  </span>
                </summary>
                <p className="max-w-2xl pb-5 text-[15px] leading-relaxed text-ink-2">{f.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Closing */}
        <section className="border-t border-line bg-surface">
          <div data-reveal className="mx-auto flex max-w-[1200px] flex-col items-start gap-8 px-5 py-24 sm:px-8 lg:flex-row lg:items-end lg:justify-between lg:py-28">
            <h2 className="max-w-3xl font-display text-[44px] leading-[1.02] text-ink sm:text-[64px]">
              File your next application <em className="text-accent">properly.</em>
            </h2>
            <PrimaryCta label="Create your account" />
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-5 py-10 text-[13px] text-ink-3 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <div className="flex items-center gap-2.5"><Mark className="size-6" /><span>thedaaakhouse — a job-search workspace.</span></div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2">
            <a href="#how" className="hover:text-ink">How it works</a>
            <a href="#features" className="hover:text-ink">Features</a>
            <a href="#faq" className="hover:text-ink">FAQ</a>
            <Link href="/login" className="hover:text-ink">Log in</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}

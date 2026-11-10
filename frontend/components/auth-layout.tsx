import Link from "next/link";
import { Mark } from "./brand";

/** Split auth screen: form on the left, a quiet product statement on the right. */
export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Link href="/" className="inline-flex items-center gap-2.5 self-start rounded-md" aria-label="thedaaakhouse home">
          <Mark />
          <span className="text-[15px] font-semibold tracking-[-0.02em]">thedaaak<span className="text-ink-3">house</span></span>
        </Link>
        <div className="rise-in mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <h1 className="font-display text-[44px] leading-none text-ink">{title}</h1>
          <p className="mt-3 text-[15px] text-ink-2">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </div>
      </div>
      <aside className="relative hidden overflow-hidden border-l border-line bg-ink text-on-ink lg:flex lg:flex-col lg:justify-end lg:p-14">
        <svg className="absolute inset-x-14 top-[28%] h-24 w-[calc(100%-7rem)]" viewBox="0 0 400 60" preserveAspectRatio="none" aria-hidden="true">
          <line x1="8" y1="30" x2="392" y2="30" stroke="currentColor" strokeOpacity=".2" strokeWidth="1.5" />
          <line className="draw" x1="8" y1="30" x2="296" y2="30" stroke="currentColor" strokeWidth="1.5" />
          {[8, 104, 200, 296, 392].map((x, i) => (
            <circle key={x} cx={x} cy="30" r={i === 3 ? 7 : 5} fill={i === 3 ? "var(--accent)" : i < 3 ? "currentColor" : "transparent"} stroke="currentColor" strokeOpacity={i > 3 ? 0.35 : 1} strokeWidth="1.5" />
          ))}
        </svg>
        <p className="font-display text-[40px] leading-[1.05]">Know where every application is,<br /><em className="text-accent">and what to do next.</em></p>
        <p className="mt-5 max-w-md text-[15px] leading-relaxed opacity-70">
          The job description, the resume you sent, the ATS score and its maths, prep and research — filed together on one route.
        </p>
      </aside>
    </div>
  );
}

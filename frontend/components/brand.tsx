import Link from "next/link";

/** Mark: a route with three stops, the last one "here" in vermilion. */
export function Mark({ className = "size-7" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 28 28" aria-hidden="true">
      <rect width="28" height="28" rx="7" fill="var(--ink)" />
      <path d="M6 18.5h16" stroke="var(--on-ink)" strokeOpacity=".35" strokeWidth="1.5" />
      <path d="M6 18.5h10" stroke="var(--on-ink)" strokeWidth="1.5" />
      <circle cx="7" cy="18.5" r="2" fill="var(--on-ink)" />
      <circle cx="14" cy="18.5" r="2" fill="var(--on-ink)" />
      <circle cx="21" cy="18.5" r="2.6" fill="var(--accent)" />
      <path d="M8 8.5h12v5.5H8z" fill="none" stroke="var(--on-ink)" strokeWidth="1.4" />
      <path d="m8.3 8.8 5.7 3.4 5.7-3.4" fill="none" stroke="var(--on-ink)" strokeWidth="1.4" />
    </svg>
  );
}

export function Wordmark({ href = "/applications", onClick }: { href?: string; onClick?: () => void }) {
  return (
    <Link href={href} onClick={onClick} className="inline-flex items-center gap-2.5 rounded-md" aria-label="thedaaakhouse home">
      <Mark />
      <span className="text-[15px] font-semibold tracking-[-0.02em] text-ink">
        thedaaak<span className="text-ink-3">house</span>
      </span>
    </Link>
  );
}

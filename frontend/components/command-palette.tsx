"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { ALL_NAV } from "./nav";
import { Kbd, cx } from "./ds";

/** ⌘K / Ctrl+K jump-to-anywhere. Navigation only — no hidden actions. */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const ref = useRef<HTMLDialogElement>(null);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);

  const items = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return ALL_NAV;
    const inLabel = ALL_NAV.filter((n) => n.label.toLowerCase().includes(s));
    return [...inLabel, ...ALL_NAV.filter((n) => !inLabel.includes(n) && n.hint.toLowerCase().includes(s))];
  }, [q]);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) { setQ(""); setI(0); d.showModal(); }
    if (!open && d.open) d.close();
  }, [open]);
  useEffect(() => setI(0), [q]);

  function go(href: string) { onClose(); router.push(href); }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setI((v) => Math.min(v + 1, items.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setI((v) => Math.max(v - 1, 0)); }
    if (e.key === "Enter" && items[i]) { e.preventDefault(); go(items[i].href); }
  }

  return (
    <dialog ref={ref} onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}
      aria-label="Jump to page"
      className="dialog-in mx-auto mt-[12vh] w-[min(92vw,560px)] overflow-hidden rounded-xl border border-line bg-surface p-0 text-ink shadow-pop backdrop:bg-ink/25 backdrop:backdrop-blur-[2px]">
      <div className="flex items-center gap-3 border-b border-line px-4">
        <svg className="size-4 text-ink-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey}
          role="combobox" aria-expanded="true" aria-controls="cmdk-list" aria-activedescendant={items[i] ? `cmdk-${i}` : undefined}
          placeholder="Jump to…" className="h-12 flex-1 bg-transparent text-[15px] outline-none focus-visible:outline-none" />
        <Kbd>esc</Kbd>
      </div>
      <ul id="cmdk-list" role="listbox" className="scroll-quiet max-h-[50vh] overflow-y-auto p-2">
        {items.length === 0 && <li className="px-3 py-6 text-center text-sm text-ink-3">No page matches “{q}”.</li>}
        {items.map((n, idx) => (
          <li key={n.href} id={`cmdk-${idx}`} role="option" aria-selected={idx === i}
            onMouseMove={() => setI(idx)} onClick={() => go(n.href)}
            className={cx("flex cursor-pointer items-center justify-between gap-4 rounded-md px-3 py-2.5 text-sm", idx === i && "bg-sunken")}>
            <span className="font-medium">{n.label}</span>
            <span className="truncate text-[13px] text-ink-3">{n.hint}</span>
          </li>
        ))}
      </ul>
    </dialog>
  );
}

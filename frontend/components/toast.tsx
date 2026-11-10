"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Button, cx } from "./ds";

type ToastTone = "neutral" | "ok" | "bad";
type Toast = { id: number; message: string; tone: ToastTone };
type ConfirmOpts = { title: string; body?: string; confirmLabel?: string; danger?: boolean };

const Ctx = createContext<{
  toast: (message: string, tone?: ToastTone) => void;
  confirm: (opts: ConfirmOpts) => Promise<boolean>;
}>({ toast: () => {}, confirm: async () => false });

export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [pending, setPending] = useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null);
  const seq = useRef(0);

  const toast = useCallback((message: string, tone: ToastTone = "neutral") => {
    const id = ++seq.current;
    setToasts((t) => [...t.slice(-2), { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "bad" ? 6000 : 3500);
  }, []);

  const confirm = useCallback((opts: ConfirmOpts) => new Promise<boolean>((resolve) => setPending({ ...opts, resolve })), []);
  const close = (v: boolean) => { pending?.resolve(v); setPending(null); };

  return (
    <Ctx.Provider value={{ toast, confirm }}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4 sm:bottom-6 sm:right-6 sm:left-auto sm:items-end">
        {toasts.map((t) => (
          <div key={t.id} role={t.tone === "bad" ? "alert" : "status"}
            className="dialog-in pointer-events-auto flex max-w-sm items-start gap-2.5 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink shadow-pop">
            <span className={cx("mt-1.5 size-2 shrink-0 rounded-full", t.tone === "ok" ? "bg-ok" : t.tone === "bad" ? "bg-bad" : "bg-ink-3")} aria-hidden="true" />
            {t.message}
          </div>
        ))}
      </div>
      {pending && <ConfirmDialog {...pending} onClose={close} />}
    </Ctx.Provider>
  );
}

function ConfirmDialog({ title, body, confirmLabel = "Confirm", danger, onClose }: ConfirmOpts & { onClose: (v: boolean) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return (
    <dialog ref={ref} onCancel={(e) => { e.preventDefault(); onClose(false); }} aria-labelledby="confirm-title"
      className="dialog-in m-auto w-[min(92vw,420px)] rounded-xl border border-line bg-surface p-0 text-ink shadow-pop backdrop:bg-ink/30 backdrop:backdrop-blur-[2px]">
      <div className="p-6">
        <h2 id="confirm-title" className="text-base font-semibold">{title}</h2>
        {body && <p className="mt-2 text-sm leading-relaxed text-ink-2">{body}</p>}
      </div>
      <div className="flex justify-end gap-2 border-t border-line bg-sunken/50 px-6 py-3">
        <Button variant="ghost" onClick={() => onClose(false)} autoFocus>Cancel</Button>
        <Button variant={danger ? "danger" : "primary"} onClick={() => onClose(true)}>{confirmLabel}</Button>
      </div>
    </dialog>
  );
}

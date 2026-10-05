"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

interface Theme {
  plain: boolean;
  night: boolean;
  sound: boolean;
  togglePlain: () => void;
  toggleNight: () => void;
  toggleSound: () => void;
  /** Soft paper "thunk" via WebAudio. Off unless user enables sound. */
  thunk: () => void;
}

const Ctx = createContext<Theme | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [plain, setPlain] = useState(false);
  const [night, setNight] = useState(false);
  const [sound, setSound] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem("tdh-plain") === "1") setPlain(true);
      if (localStorage.getItem("tdh-night") === "1") setNight(true);
    } catch { /* private mode */ }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.plain = plain ? "true" : "false";
    try { localStorage.setItem("tdh-plain", plain ? "1" : "0"); } catch { /* noop */ }
  }, [plain ]);

  useEffect(() => {
    document.body.classList.toggle("night-shift", night);
    try { localStorage.setItem("tdh-night", night ? "1" : "0"); } catch { /* noop */ }
  }, [night]);

  const thunk = useCallback(() => {
    if (!sound) return;
    try {
      const AC = window.AudioContext;
      const ctx = new AC();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(140, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(55, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.16);
    } catch { /* audio unavailable */ }
  }, [sound]);

  return (
    <Ctx.Provider value={{
      plain, night, sound,
      togglePlain: () => setPlain((v) => !v),
      toggleNight: () => setNight((v) => !v),
      toggleSound: () => setSound((v) => !v),
      thunk,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export function useTheme() {
  const t = useContext(Ctx);
  if (!t) throw new Error("useTheme outside ThemeProvider");
  return t;
}

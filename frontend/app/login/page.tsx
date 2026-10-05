"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, token } from "@/lib/api";
import { inputCls } from "@/components/ui";

export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const out = mode === "login"
        ? await api.login(username.trim(), password)
        : await api.register(username.trim(), password);
      token.set(out.access_token);
      router.replace("/tracker");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed. Is the API running?");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm paper-keep rounded-sm border border-kraft/60 bg-envelope shadow-paper p-8">
      <h1 className="font-serif text-3xl font-bold tracking-tight text-postalnavy">thedaaakhouse</h1>
      <p className="postal-copy mt-1 font-hand text-xl italic text-postmark">Sign the Register</p>
      <p className="mt-1 text-sm text-postmark">
        {mode === "login" ? "Log in to your workspace." : "Create your local account."}
      </p>
      <form onSubmit={submit} className="mt-6 space-y-3">
        <input className={inputCls} placeholder="Username (min 3 chars)" value={username}
          onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        <input className={inputCls} type="password" placeholder="Password (min 8 chars)" value={password}
          onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} />
        {error && <p className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
        <button type="submit" disabled={busy || !username || !password}
          className="w-full rounded-md bg-postred px-4 py-2 text-sm font-serif font-bold text-envelope disabled:opacity-40">
          {busy ? "Working…" : mode === "login" ? "Log in" : "Create account"}
        </button>
      </form>
      <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
        className="mt-4 w-full text-center text-sm text-violet-700 hover:underline">
        {mode === "login" ? "New here? Create an account" : "Have an account? Log in"}
      </button>
    </div>
  );
}

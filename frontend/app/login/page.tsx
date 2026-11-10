"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { SignIn } from "@clerk/nextjs";
import { api, token } from "@/lib/api";
import { useAppAuth } from "@/components/auth-provider";
import { AuthLayout } from "@/components/auth-layout";
import { Button, Field, inputCls } from "@/components/ds";

export default function Login() {
  const router = useRouter();
  const auth = useAppAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (auth.clerkEnabled) {
    return (
      <AuthLayout title="Welcome back" subtitle="Sign in to your workspace.">
        <SignIn signUpUrl="/sign-up" forceRedirectUrl="/applications" />
      </AuthLayout>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const out = mode === "login"
        ? await api.login(username.trim(), password)
        : await api.register(username.trim(), password);
      token.set(out.access_token);
      router.replace("/applications");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed. Is the API running?");
    } finally {
      setBusy(false);
    }
  }

  const login = mode === "login";
  return (
    <AuthLayout title={login ? "Welcome back" : "Create your account"}
      subtitle={login ? "Log in to your workspace." : "A local account on this server. Your data stays on your backend."}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label="Username" hint={login ? undefined : "At least 3 characters."}>
          <input className={inputCls} placeholder="Username (min 3 chars)" value={username} autoFocus
            onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </Field>
        <Field label="Password" hint={login ? undefined : "At least 8 characters."}>
          <input className={inputCls} type="password" placeholder="Password (min 8 chars)" value={password}
            onChange={(e) => setPassword(e.target.value)} autoComplete={login ? "current-password" : "new-password"} />
        </Field>
        {error && <p role="alert" className="shake rounded-md border border-bad/25 bg-bad/5 px-3.5 py-2.5 text-sm text-bad">{error}</p>}
        <Button type="submit" variant="primary" size="lg" className="w-full" busy={busy} disabled={!username || !password}>
          {busy ? "Working…" : login ? "Log in" : "Create account"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-3">
        {login ? "New here?" : "Have an account?"}{" "}
        <button onClick={() => { setMode(login ? "register" : "login"); setError(null); }} className="font-medium text-brand hover:underline">
          {login ? "Create an account" : "Log in"}
        </button>
      </p>
    </AuthLayout>
  );
}

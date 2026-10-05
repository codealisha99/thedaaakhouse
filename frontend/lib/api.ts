import type { Application, ApplicationDetail, Resume, ResumeVersion } from "@/types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";
const TOKEN_KEY = "thedaaakhouse_token";

export const token = {
  get: () => (typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY)),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  status: number;
  /** status 0 = network/timeout (no HTTP response was received). */
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** No request may hang forever (login "Working..." trap). */
export const REQUEST_TIMEOUT_MS = 15000;

async function req<T>(path: string, init?: RequestInit, auth = true): Promise<T> {
  const headers: Record<string, string> = {};
  if (init?.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (auth) {
    const t = token.get();
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  let r: Response;
  try {
    r = await fetch(`${API}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { ...headers, ...(init?.headers as object) },
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError(
        0,
        `Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s. ` +
          `Unable to reach the thedaaakhouse backend at ${API} — check that the API is running.`
      );
    }
    throw new ApiError(
      0,
      `Unable to reach the thedaaakhouse backend at ${API}. ` +
        "Please check that the API is running, then try again."
    );
  } finally {
    clearTimeout(timer);
  }
  if (r.status === 401 && auth && typeof window !== "undefined") {
    token.clear();
    if (!window.location.pathname.startsWith("/login")) window.location.href = "/login";
  }
  if (!r.ok) {
    const detail = await r.json().catch(() => ({})).then((j) => (j as { detail?: string }).detail ?? r.statusText);
    throw new ApiError(r.status, typeof detail === "string" ? detail : r.statusText);
  }
  if (r.status === 204) return undefined as T;
  try {
    return (await r.json()) as T;
  } catch {
    throw new ApiError(r.status, "Received an invalid response from the backend. Is something else serving this port?");
  }
}

const q = (params: Record<string, string | undefined>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) s.set(k, v);
  const str = s.toString();
  return str ? `?${str}` : "";
};

export const api = {
  register: (username: string, password: string) =>
    req<{ access_token: string; username: string }>("/api/auth/register", {
      method: "POST", body: JSON.stringify({ username, password }), headers: {},
    }, false),
  login: (username: string, password: string) =>
    req<{ access_token: string; username: string }>("/api/auth/login", {
      method: "POST", body: JSON.stringify({ username, password }), headers: {},
    }, false),
  me: () => req<{ id: string; username: string }>("/api/auth/me"),

  listApps: (opts: { status?: string; search?: string; sort?: string } = {}) =>
    req<Application[]>(`/api/applications${q(opts)}`),
  createApp: (payload: Partial<Application> & { company: string; role: string; raw_jd?: string }) =>
    req<Application>("/api/applications", { method: "POST", body: JSON.stringify(payload) }),
  getApp: (id: string) => req<ApplicationDetail>(`/api/applications/${id}`),
  patchApp: (id: string, payload: Partial<Application>) =>
    req<Application>(`/api/applications/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteApp: (id: string) => req<void>(`/api/applications/${id}`, { method: "DELETE" }),
  analyzeJd: (id: string) =>
    req<unknown>(`/api/applications/${id}/analyze-jd`, { method: "POST" }),
  tailor: (id: string, resume_id: string, label?: string) =>
    req<ResumeVersion>(`/api/applications/${id}/tailor`, {
      method: "POST", body: JSON.stringify({ resume_id, label }),
    }),
  attachVersion: (id: string, resume_version_id: string) =>
    req<Application>(`/api/applications/${id}/attach-version`, {
      method: "POST", body: JSON.stringify({ resume_version_id }),
    }),
  runAts: (id: string, payload: { resume_id?: string; resume_version_id?: string }) =>
    req<{ id: string; score: number; breakdown: import("@/types").ATSBreakdown }>(
      `/api/applications/${id}/ats`, { method: "POST", body: JSON.stringify(payload) }),
  runPrep: (id: string, resume_id?: string) =>
    req<{ id: string; plan: import("@/types").InterviewPlan }>(
      `/api/applications/${id}/interview-prep`, {
        method: "POST", body: JSON.stringify({ resume_id }),
      }),
  runResearch: (id: string, website?: string) =>
    req<{ id: string; name: string; website: string | null; profile: Record<string, unknown>; sources: unknown[] }>(
      `/api/applications/${id}/company-research`, {
        method: "POST", body: JSON.stringify({ website: website ?? "" }),
      }),

  listResumes: () => req<Resume[]>("/api/resumes"),
  getResume: (id: string) => req<Resume>(`/api/resumes/${id}`),
  uploadResume: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<Resume>("/api/resumes", { method: "POST", body: form });
  },
  listVersions: (application_id?: string) =>
    req<ResumeVersion[]>(`/api/applications/versions/all${q({ application_id })}`),
  getVersion: (id: string) => req<ResumeVersion>(`/api/applications/versions/${id}`),
};

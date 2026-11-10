import type { Application, ApplicationDetail, ArenaSession, ArenaSummary, Resume, ResumeVersion, StudyPlan, StudyPlanSummary, TopicAnswer } from "@/types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";
const TOKEN_KEY = "thedaaakhouse_token";
export interface OutreachDraft {
  id: string; recipient_email: string; subject: string; body: string; payload_sha256: string;
  resume_version_id: string | null; attachment_preview: string | null; status: string;
  factuality_findings: { code: string; detail: string }[];
}
export interface CampaignTask {
  id: string; status: string; company?: string; recipient_email?: string;
  result?: { draft_id?: string }; error_detail?: string; error_code?: string;
}
let authTokenProvider: (() => Promise<string | null>) | null = null;

export function setAuthTokenProvider(provider: (() => Promise<string | null>) | null) {
  authTokenProvider = provider;
}

export async function getAuthToken() {
  return authTokenProvider ? authTokenProvider() : token.get();
}

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
    const t = await getAuthToken();
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
    const detail = await r.json().catch(() => ({})).then((j) => j.detail ?? r.statusText);
    const message = typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg ?? "Invalid input").join("; ")
      : detail.detail ?? (detail.rows ? `${detail.message} ${detail.rows.map((row: { row: number; error: string }) => `Row ${row.row}: ${row.error}`).join("; ")}` : detail.message) ?? r.statusText;
    throw new ApiError(r.status, message);
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
  discoverySources: () => req<{ id: string; name: string; adapter: string; consecutive_failures: number }[]>("/api/discovery/sources"),
  discoveryListings: () => req<{ id: string; title: string; company_name: string; location: string | null; status: string; needs_review: boolean }[]>("/api/discovery/listings?status=active"),
  discoveryCreate: (name: string, adapter: string, url: string) => req<{ id: string }>("/api/discovery/sources", { method: "POST", body: JSON.stringify({ name, adapter, config: { url, company_name: name } }) }),
  discoveryScan: (source_id: string) => req<{ task_id: string }>("/api/tasks", { method: "POST", body: JSON.stringify({ kind: "discovery.scan", payload: { source_id } }) }),
  discoverySave: (id: string) => req<{ application_id: string }>(`/api/discovery/listings/${id}/save`, { method: "POST" }),
  campaignPrepare: (csv_text: string, resume_id: string, signature: string) => req<{ tasks: { task_id: string; replayed: boolean }[] }>("/api/campaigns/prepare", { method: "POST", body: JSON.stringify({ csv_text, resume_id, signature }) }),
  campaignTasks: () => req<CampaignTask[]>("/api/campaigns/tasks"),
  outreachDrafts: () => req<OutreachDraft[]>("/api/outreach/drafts"),
  outreachEdit: (id: string, subject: string, body: string) => req<OutreachDraft>(`/api/outreach/drafts/${id}`, { method: "PATCH", body: JSON.stringify({ subject, body }) }),
  outreachSend: (id: string, payload_sha256: string) => req<{ task_id: string }>(`/api/outreach/drafts/${id}/review-send`, { method: "POST", body: JSON.stringify({ payload_sha256 }) }),
  outreachSends: () => req<{ id: string; draft_id: string; status: string }[]>("/api/outreach/sends"),
  taskStatus: (id: string) => req<CampaignTask>(`/api/tasks/${id}`),
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
  createFromUrl: (payload: { url: string; company?: string; role?: string; location?: string }) =>
    req<Application>("/api/applications/from-url", { method: "POST", body: JSON.stringify(payload) }),
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
  runAtsV2: (id: string, payload: { resume_id?: string; resume_version_id?: string; weights?: Record<string, number> }) =>
    req<{ id: string; score: number; breakdown: import("@/types").AtsV2Breakdown }>(
      `/api/applications/${id}/ats-v2`, { method: "POST", body: JSON.stringify(payload) }),
  runOptimize: (id: string, resume_id: string, policy?: { trigger_below?: number; accept_at_least?: number; max_attempts?: number }) =>
    req<import("@/types").OptimizeRun>(
      `/api/applications/${id}/optimize`, { method: "POST", body: JSON.stringify({ resume_id, policy }) }),
  optimizeRuns: (application_id?: string) =>
    req<import("@/types").OptimizeRun[]>(`/api/optimize/runs${application_id ? `?application_id=${application_id}` : ""}`),
  optimizeLatexUrl: (runId: string) => `${API}/api/optimize/runs/${runId}/latex`,
  optimizePdfUrl: (runId: string) => `${API}/api/optimize/runs/${runId}/pdf`,
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
  patchVersion: (id: string, payload: { label?: string; content?: string }) =>
    req<ResumeVersion>(`/api/applications/versions/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getProfile: () => req<import("@/types").CareerProfile>("/api/profile"),
  putProfile: (payload: Partial<import("@/types").CareerProfile>) =>
    req<import("@/types").CareerProfile>("/api/profile", { method: "PUT", body: JSON.stringify(payload) }),
  seedProfile: (resume_id: string) =>
    req<{ profile: import("@/types").CareerProfile; seeded_skills: string[]; evidence: Record<string, string[]> }>(
      "/api/profile/seed", { method: "POST", body: JSON.stringify({ resume_id }) }),
  seedNexora: () =>
    req<{ seeded: boolean; application_id: string; detail: string }>(
      "/api/dev/seed-nexora", { method: "POST", body: JSON.stringify({}) }),
  evaluateFit: (application_id: string, weights?: Record<string, number>) =>
    req<import("@/types").FitEvaluation>("/api/fit/evaluate", { method: "POST", body: JSON.stringify({ application_id, weights }) }),
  fitHistory: (application_id: string) =>
    req<import("@/types").FitEvaluation[]>(`/api/fit/history/${application_id}`),
  overrideFit: (evaluation_id: string, classification: string) =>
    req<import("@/types").FitEvaluation>(`/api/fit/evaluations/${evaluation_id}`, { method: "PATCH", body: JSON.stringify({ classification }) }),
  compareApps: (application_ids: string[]) =>
    req<import("@/types").CompareRow[]>("/api/fit/compare", { method: "POST", body: JSON.stringify({ application_ids }) }),
  compareVersion: (id: string) =>
    req<{ same_line_set: boolean; added: string[]; removed: string[]; similarity: number; unified_diff: string[] }>(`/api/applications/versions/${id}/compare`),
  versionPdfUrl: (id: string) => `${API}/api/applications/versions/${id}/pdf`,
  matchReport: (appId: string, versionId?: string) =>
    req<{ rows: { requirement: string; status: string; evidence: string[] }[]; coverage: number }>(
      `/api/applications/${appId}/match-report${versionId ? `?resume_version_id=${versionId}` : ""}`),
  createPlan: (application_id: string, resume_id?: string) =>
    req<StudyPlan>("/api/learn/plans", { method: "POST", body: JSON.stringify({ application_id, resume_id }) }),
  listPlans: (application_id?: string) =>
    req<StudyPlanSummary[]>(`/api/learn/plans${application_id ? `?application_id=${application_id}` : ""}`),
  getPlan: (id: string) => req<StudyPlan>(`/api/learn/plans/${id}`),
  answerTopic: (id: string, topic: string, answer: string) =>
    req<TopicAnswer>(`/api/learn/plans/${id}/answer`, { method: "POST", body: JSON.stringify({ topic, answer }) }),
  setTopicStatus: (id: string, topic: string, status: string) =>
    req<{ topic: string; status: string }>(`/api/learn/plans/${id}/topics`, { method: "PATCH", body: JSON.stringify({ topic, status }) }),
  startArena: (mode: string, difficulty: string, application_id?: string, resume_id?: string) =>
    req<ArenaSession>("/api/arena/sessions", { method: "POST", body: JSON.stringify({ mode, difficulty, application_id, resume_id }) }),
  listArena: (application_id?: string) =>
    req<ArenaSummary[]>(`/api/arena/sessions${application_id ? `?application_id=${application_id}` : ""}`),
  getArena: (id: string) => req<ArenaSession>(`/api/arena/sessions/${id}`),
  answerArena: (id: string, answer: string) =>
    req<ArenaSession>(`/api/arena/sessions/${id}/answer`, { method: "POST", body: JSON.stringify({ answer }) }),
  integrations: () =>
    req<{ providers: { name: string; active: boolean; model: string; status: string; note?: string }[] }>("/api/integrations"),
  gmailStatus: () => req<{ provider: string; enabled: boolean; connected: boolean; email: string | null; capabilities: string[] }>("/api/integrations/gmail"),
  gmailConnect: () => req<{ authorization_url: string }>("/api/integrations/gmail/connect", { method: "POST" }),
  gmailDisconnect: () => req<{ disconnected: boolean }>("/api/integrations/gmail", { method: "DELETE" }),
  gmailSync: () => req<{ events_added: number }>("/api/integrations/gmail/sync", { method: "POST" }),
  createStartupProspect: (payload: { url: string; name?: string; note?: string }) =>
    req<{ id: string; kind: string; company: string | null; domain: string | null }>("/api/opportunities/startups", { method: "POST", body: JSON.stringify(payload) }),
  listOpportunities: () => req<{ items: { id: string; kind: string; title: string | null; company: string | null; domain: string | null }[] }>("/api/opportunities?limit=100"),
  discoverContacts: (opportunityId: string, idempotencyKey: string) =>
    req<{ task_id: string; status: string; poll_url: string; research_run_id: string; replayed: boolean }>(`/api/opportunities/${opportunityId}/contacts/discover`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey } }),
  opportunityContacts: (opportunityId: string) =>
    req<{ contacts: { id: string; opportunity_id: string | null; name: string | null; role: string | null; email: string | null; source_url: string | null; address_source: string; verification_state: string; review_required: boolean }[]; research_runs: { id: string; task_id: string | null; status: string; result: Record<string, unknown> }[] }>(`/api/opportunities/${opportunityId}/contacts`),
  createOutreachDraft: (payload: { opportunity_id: string; recipient_email: string; recipient_name?: string; recipient_role?: string; recipient_identity: "known" | "unknown"; contact_source_url?: string; contact_source_kind: "published" | "provider_reported" | "inferred_pattern" | "user_supplied" }) =>
    req<{ id: string; subject: string; body: string; payload_sha256: string }>("/api/outreach/drafts", { method: "POST", body: JSON.stringify(payload) }),
  operationsSummary: () => req<{ tasks_by_status: Record<string, number>; discovery: { enabled_sources: number; configured_sources: number; runs_last_24h: number; listing_budget_per_run: number; failures_last_24h: number }; outreach: { send_attempts_last_24h: number; accepted_last_24h: number; unknown_last_24h: number } }>("/api/operations/summary"),
};

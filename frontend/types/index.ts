export interface User {
  id: string;
  username: string;
}

export type AppStatus =
  | "saved" | "applied" | "oa" | "interview"
  | "final_round" | "offer" | "rejected" | "withdrawn";

export const STATUSES: AppStatus[] = [
  "saved", "applied", "oa", "interview",
  "final_round", "offer", "rejected", "withdrawn",
];

export interface Application {
  id: string;
  company: string;
  role: string;
  location: string | null;
  job_url: string | null;
  date_saved: string | null;
  date_applied: string | null;
  status: AppStatus;
  salary: string | null;
  ats_score: number | null;
  resume_version_id: string | null;
  interview_date: string | null;
  next_step: string | null;
  notes: string;
  raw_jd: string;
  jd_analysis: JDAnalysis | null;
  status_history: { from?: string; to: string; at: string }[];
  created_at: string | null;
  updated_at: string | null;
}

export interface JDAnalysis {
  keywords: { term: string; count: number; weight: number }[];
  phrases: string[];
  skills: string[];
  responsibilities: string[];
  experience_years: number | null;
  word_count: number;
}

export interface Resume {
  id: string;
  filename: string;
  content_type: string;
  parse_status: string;
  parse_error: string | null;
  profile: unknown | null;
  raw_text?: string;
  created_at: string | null;
}

export interface ResumeVersion {
  id: string;
  resume_id: string | null;
  application_id: string | null;
  label: string;
  missing_keywords: string[];
  ats_score: number | null;
  created_at: string | null;
  content?: string;
  changes?: ChangeOp[];
}

export interface ChangeOp {
  operation: string;
  target: string;
  reason: string;
  target_requirement: string | null;
  source_evidence: string[];
}

export interface ATSBreakdown {
  score: number;
  keyword_match: number;
  matched_keywords: string[];
  missing_keywords: string[];
  skills_required: string[];
  skills_matched: string[];
  skills_missing: string[];
  skills_match: number;
  experience_required_years: number | null;
  experience_found_years: number;
  experience_match: number;
  formatting_checks: { check: string; passed: boolean }[];
  formatting_score: number;
  formatting_issues: string[];
  recommendations: string[];
  methodology: string;
}

export interface InterviewQuestion {
  question: string;
  category: string;
  reason: string;
  source: string;
}

export interface InterviewPlan {
  topics: string[];
  questions: InterviewQuestion[];
  focus_areas: string[];
  note: string;
}

export interface ApplicationDetail {
  application: Application;
  attached_version: ResumeVersion | null;
  versions: ResumeVersion[];
  ats_history: { id: string; score: number; breakdown: ATSBreakdown; created_at: string | null }[];
  interview_preps: { id: string; plan: InterviewPlan; created_at: string | null }[];
  research: { id: string; name: string; website: string | null; profile: Record<string, unknown>; sources: { source_url: string; source_title: string; retrieved_at: string }[] }[];
}

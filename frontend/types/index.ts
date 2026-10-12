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
  edited_manually?: boolean;
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

export interface StudyTopic {
  term: string;
  known: boolean;
  priority: number;
  order: number;
  resume_evidence: string;
  levels: { name: string; prompt: string }[];
  exercises: string[];
  check: { question: string; expected_points: string[] };
  progress: { status: string; attempts: number; correct: number };
}

export interface StudyPlan {
  id: string;
  application_id: string | null;
  title: string;
  topics: StudyTopic[];
  created_at: string | null;
}

export interface StudyPlanSummary {
  id: string;
  application_id: string | null;
  title: string;
  topics: number;
  mastered: number;
  created_at: string | null;
}

export interface TopicAnswer {
  topic: string;
  score: number;
  verdict: "correct" | "needs_revision";
  hits: string[];
  missed: string[];
  feedback: string;
  progress: { status: string; attempts: number; correct: number };
}

export interface ArenaQuestion {
  topic: string;
  difficulty: string;
  question: string;
  hints: string[];
  tests: string[];
  complexity: string;
  source: string;
  reason: string;
}

export interface ArenaTurn {
  question: ArenaQuestion;
  answer: string;
  evaluation: { score: number; verdict: string; hits: string[]; missed: string[]; feedback: string; follow_up: string | null };
}

export interface ArenaSession {
  id: string;
  application_id: string | null;
  mode: string;
  difficulty: string;
  status: string;
  total: number;
  answered: number;
  current_index: number;
  current: ArenaQuestion | null;
  turns: ArenaTurn[];
  average_score: number | null;
  created_at: string | null;
  evaluation?: ArenaTurn["evaluation"];
  completed?: boolean;
  summary?: { by_category: Record<string, number>; strengths: string[]; weaknesses: string[] };
}

export interface ArenaSummary {
  id: string;
  application_id: string | null;
  mode: string;
  difficulty: string;
  status: string;
  total: number;
  answered: number;
  average_score: number | null;
  created_at: string | null;
}

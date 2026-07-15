/**
 * API Client - Centralized HTTP client for all backend communication.
 *
 * Backend: FastAPI at http://localhost:8000
 * All endpoints as defined in routes/*.py
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ============================================================
// HTTP HELPERS
// ============================================================

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

const get = <T>(path: string) => request<T>(path, { method: "GET" });
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });
const patch = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const del = (path: string) => request(path, { method: "DELETE" });

// ============================================================
// TYPES
// ============================================================

export interface Mission {
  id: number;
  target_role: string;
  target_count: number;
  progress_count: number;
  status: string;
  time_constraint_days?: number;
  location_preference?: string;
  job_type?: string;
  daily_application_limit: number;
  created_at: string;
  completed_at?: string;
}

export interface Job {
  id: number;
  mission_id: number;
  company: string;
  role: string;
  location?: string;
  description: string;
  match_score?: number;
  status: string;
  hr_email?: string;
  hr_name?: string;
  hr_title?: string;             // Apollo Phase 4C
  hr_email_confidence?: string;  // Apollo Phase 4C — "verified"|"likely"|"none"
  apply_link?: string;
  source_portal?: string;
  created_at: string;
}

export interface EmailDraft {
  id: number;
  job_id: number;
  subject: string;
  body: string;
  to_email: string;
  to_name?: string;
  hr_title?: string;             // Apollo Phase 4C — HR contact job title
  hr_email_confidence?: string;  // Apollo Phase 4C — "verified"|"likely"|"none"
  recipient_confirmed: boolean;  // false = to_email is an unverified guess, blocks approval
  status: string;
  created_at: string;
  approved_at?: string;
}

export interface ApplicationRecord {
  id: number;
  job_id: number;
  company: string;
  hr_email: string;
  hr_name?: string;
  gmail_message_id?: string;
  sent_at: string;
  outcome: string;
}

export interface SystemStatus {
  mode: string;
  configured: boolean;
  required_services: {
    database: boolean;
    apify_api: boolean;
    gmail_configured: boolean;
  };
  optional_services: {
    openrouter_api: boolean;
    groq_api: boolean;
  };
  message: string;
}

export interface CVVersionItem {
  id: number;
  mission_id: number;
  job_id?: number;
  version_name: string;
  is_master: number;
  content_markdown: string;
  keyword_match_score?: number;
  optimization_notes?: string; // JSON string: string[]
  job_company?: string;
  job_role?: string;
  job_match_score?: number;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  mission_id: number;
  timestamp: string;
  level: string;
  action_type: string;
  agent_name: string;
  output_summary?: string;
  status: string;
  error_message?: string;
  job_id?: number;
}

// ============================================================
// SYSTEM
// ============================================================

export const systemApi = {
  health: () => get<{ status: string }>("/health"),
  status: () => get<SystemStatus>("/api/system/status"),
};

// ============================================================
// MISSIONS
// ============================================================

export const missionApi = {
  list: () => get<Mission[]>("/api/missions/"),
  get: (id: number) => get<Mission>(`/api/missions/${id}`),
  create: (userInput: string) =>
    post<Mission>("/api/missions/", { user_input: userInput }),
  execute: (
    id: number,
    cvText: string,
    cvFilePath?: string,
    autoApprove = false
  ) =>
    post(`/api/missions/${id}/execute`, {
      cv_text: cvText,
      cv_file_path: cvFilePath,
      auto_approve: autoApprove,
    }),
  auditLog: (id: number, limit = 50) =>
    get<AuditLogEntry[]>(`/api/missions/${id}/audit?limit=${limit}`),
  delete: (id: number) => del(`/api/missions/${id}`),
};

// ============================================================
// JOBS
// ============================================================

export const jobApi = {
  listByMission: (missionId: number, statusFilter?: string, minScore?: number) => {
    const params = new URLSearchParams();
    if (statusFilter) params.set("status_filter", statusFilter);
    if (minScore !== undefined) params.set("min_score", String(minScore));
    const qs = params.toString();
    return get<Job[]>(`/api/jobs/mission/${missionId}${qs ? `?${qs}` : ""}`);
  },
  get: (id: number) => get<Job>(`/api/jobs/${id}`),
};

// ============================================================
// EMAILS (HITL Approval)
// ============================================================

export const emailApi = {
  listPending: () => get<EmailDraft[]>("/api/emails/pending"),
  get: (id: number) => get<EmailDraft>(`/api/emails/${id}`),
  approve: (id: number, approvedBy = "user") =>
    post<EmailDraft>(`/api/emails/${id}/approve`, { approved_by: approvedBy }),
  reject: (id: number, reason?: string) =>
    post<EmailDraft>(`/api/emails/${id}/reject`, { reason }),
  edit: (id: number, subject?: string, body?: string, to_email?: string) =>
    patch<EmailDraft>(`/api/emails/${id}`, { subject, body, to_email }),
};

// ============================================================
// CV VERSIONS
// ============================================================

export interface CvAiEditResult {
  revised_content: string;
  explanation: string;
}

export interface SyncToEmailResult {
  email_id: number;
  subject: string;
  body: string;
  message: string;
}

export const cvVersionApi = {
  listByMission: (missionId: number) =>
    get<CVVersionItem[]>(`/api/cvversions/mission/${missionId}`),
  get: (id: number) => get<CVVersionItem>(`/api/cvversions/${id}`),
  saveManual: (id: number, content_markdown: string) =>
    patch<CVVersionItem>(`/api/cvversions/${id}`, { content_markdown }),
  aiEdit: (id: number, instruction: string) =>
    post<CvAiEditResult>(`/api/cvversions/${id}/ai-edit`, { instruction }),
  syncToEmail: (id: number) =>
    post<SyncToEmailResult>(`/api/cvversions/${id}/sync-to-email`),
};

// ============================================================
// APPLICATIONS
// ============================================================

export const applicationApi = {
  list: () => get<ApplicationRecord[]>("/api/applications/"),
  get: (id: number) => get<ApplicationRecord>(`/api/applications/${id}`),
  send: (emailDraftId: number, cvVersionId: number) =>
    post<ApplicationRecord>("/api/applications/send", {
      email_draft_id: emailDraftId,
      cv_version_id: cvVersionId,
    }),
};

import {
  User,
  Submission,
  Finding,
  Decision,
  Comment,
  Approval,
  GuidelineDoc,
  ApprovedFact,
  Term,
  Asset,
  SystemStatus,
  InsightsSummary,
  ActivityEvent,
  RepeatedIssue,
  GuidelineHealthClause,
  FeedbackCategoryStats,
  CreatorPersonalStats,
  SystemSettings,
  AuditLog,
  Notification,
} from "./types";

const API_BASE = "/api";

export let onColdStartChange: ((isWaking: boolean) => void) | null = null;
export function setColdStartListener(listener: (isWaking: boolean) => void) {
  onColdStartChange = listener;
}

export function getToken(): string | null {
  return localStorage.getItem("brandguard_token");
}

export function setToken(token: string) {
  localStorage.setItem("brandguard_token", token);
}

export function clearToken() {
  localStorage.removeItem("brandguard_token");
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  // Cold start timer for free tier
  const timer = setTimeout(() => {
    if (onColdStartChange) onColdStartChange(true);
  }, 2500);

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    clearTimeout(timer);
    if (onColdStartChange) onColdStartChange(false);

    if (res.status === 401) {
      clearToken();
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
      throw new Error("Session expired. Please log in again.");
    }

    if (!res.ok) {
      let errorMsg = `Request failed: ${res.status}`;
      try {
        const data = await res.json();
        errorMsg = data.detail || errorMsg;
      } catch {}
      throw new Error(errorMsg);
    }

    return (await res.json()) as T;
  } catch (err: any) {
    clearTimeout(timer);
    if (onColdStartChange) onColdStartChange(false);
    throw err;
  }
}

export const api = {
  // Auth
  login: async (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  demoLogin: async (role: User["role"]) =>
    request<{ access_token: string }>("/auth/demo-login", {
      method: "POST",
      body: JSON.stringify({ role }),
    }),
  getMe: async () => request<User>("/auth/me"),

  // Submissions
  getSubmissions: async () => request<Submission[]>("/submissions"),
  getSubmission: async (id: string) => request<Submission>(`/submissions/${id}`),
  createSubmission: async (data: {
    title: string;
    intent?: string;
    text?: string;
    content_type?: string;
  }) =>
    request<Submission>("/submissions", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  uploadSubmission: async (formData: FormData) =>
    request<Submission>("/submissions/upload", {
      method: "POST",
      body: formData,
    }),
  getSubmissionSource: async (submissionId: string, versionId: string): Promise<Blob> => {
    const token = getToken();
    const response = await fetch(`${API_BASE}/submissions/${encodeURIComponent(submissionId)}/versions/${encodeURIComponent(versionId)}/source`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (response.status === 401) {
      clearToken();
      if (!window.location.pathname.includes("/login")) window.location.href = "/login";
      throw new Error("Session expired. Please log in again.");
    }
    if (!response.ok) {
      let message = `Unable to load source document (${response.status})`;
      try {
        const data = await response.json();
        message = data.detail || message;
      } catch { /* Response may not contain JSON. */ }
      throw new Error(message);
    }
    return response.blob();
  },
  checkSubmission: async (id: string) =>
    request<{ status: string; findings_count: number; submission_status: string }>(
      `/submissions/${id}/check`,
      { method: "POST" }
    ),
  addVersion: async (id: string, text: string) =>
    request<any>(`/submissions/${id}/versions`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  // Findings
  getFindings: async (submissionId: string) =>
    request<Finding[]>(`/submissions/${submissionId}/findings`),
  submitDecision: async (
    findingId: string,
    action: "accept" | "edit" | "dispute",
    edited_text?: string,
    reason?: string
  ) =>
    request<Decision>("/decisions", {
      method: "POST",
      body: JSON.stringify({ finding_id: findingId, action, edited_text, reason }),
    }),

  // Workflow
  addComment: async (submissionId: string, body: string, findingId?: string) =>
    request<Comment>(`/submissions/${submissionId}/comments`, {
      method: "POST",
      body: JSON.stringify({ body, finding_id: findingId }),
    }),
  requestReview: async (submissionId: string) =>
    request<{ status: string; submission_status: string }>(
      `/submissions/${submissionId}/request-review`,
      { method: "POST" }
    ),
  approveSubmission: async (submissionId: string, note?: string) =>
    request<Approval>(`/submissions/${submissionId}/approve`, {
      method: "POST",
      body: JSON.stringify({ decision: "approved", note }),
    }),
  rejectSubmission: async (
    submissionId: string,
    decision: "changes_requested" | "rejected",
    note?: string
  ) =>
    request<Approval>(`/submissions/${submissionId}/reject`, {
      method: "POST",
      body: JSON.stringify({ decision, note }),
    }),
  getHistory: async (submissionId: string) =>
    request<any>(`/submissions/${submissionId}/history`),
  getNotifications: async (params?: { unread_only?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.unread_only) query.set("unread_only", "true");
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<Notification[]>(`/notifications${suffix}`);
  },
  markNotificationRead: async (notificationId: string) =>
    request<Notification>(`/notifications/${encodeURIComponent(notificationId)}/read`, { method: "PATCH" }),
  markAllNotificationsRead: async () =>
    request<{ updated_count: number }>("/notifications/read-all", { method: "PATCH" }),

  // Admin Sources
  getGuidelines: async () => request<GuidelineDoc[]>("/admin/guidelines"),
  createGuideline: async (title: string, text: string, description?: string) =>
    request<GuidelineDoc>("/admin/guidelines", {
      method: "POST",
      body: JSON.stringify({ title, text, description }),
    }),
  importGuidelineFile: async (formData: FormData) =>
    request<GuidelineDoc>("/admin/guidelines/import", {
      method: "POST",
      body: formData,
    }),
  deleteGuideline: async (id: string) =>
    request<any>(`/admin/guidelines/${id}`, { method: "DELETE" }),

  getFacts: async () => request<ApprovedFact[]>("/admin/facts"),
  createFact: async (data: {
    statement: string;
    source_note?: string;
    valid_from?: string;
    valid_to?: string;
  }) =>
    request<ApprovedFact>("/admin/facts", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteFact: async (id: string) =>
    request<any>(`/admin/facts/${id}`, { method: "DELETE" }),

  getTerms: async () => request<Term[]>("/admin/terms"),
  createTerm: async (data: { preferred: string; avoid: string[]; note?: string }) =>
    request<Term>("/admin/terms", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteTerm: async (id: string) =>
    request<any>(`/admin/terms/${id}`, { method: "DELETE" }),

  getAssets: async () => request<Asset[]>("/admin/assets"),
  createAsset: async (data: { kind: string; name: string; file_path?: string; metadata?: Record<string, unknown> }) =>
    request<Asset>("/admin/assets", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteAsset: async (id: string) =>
    request<any>(`/admin/assets/${id}`, { method: "DELETE" }),
  reindexSources: async () =>
    request<{ status: string; indexed_count: number }>("/admin/reindex", {
      method: "POST",
    }),
  assignSubmission: async (submissionId: string, reviewerId: string) =>
    request<Submission>(`/submissions/${submissionId}/assign`, {
      method: "POST",
      body: JSON.stringify({ reviewer_id: reviewerId }),
    }),
  getReviewers: async () => request<User[]>("/submissions/reviewers"),
  reviewEscalatedFinding: async (findingId: string, action: "confirm" | "dismiss", justification: string) =>
    request<{ status: string; action: string; finding_id: string }>(`/findings/${findingId}/escalate-review`, {
      method: "POST",
      body: JSON.stringify({ action, justification }),
    }),

  // Insights
  getInsightsSummary: async () => request<InsightsSummary>("/insights/summary"),
  getRecentActivity: async () => request<ActivityEvent[]>("/insights/activity"),
  getRepeatedIssues: async () =>
    request<{ repeated_issues: RepeatedIssue[] }>("/insights/repeated-issues"),
  getPersonalStats: async () => request<CreatorPersonalStats>("/insights/personal"),
  getFeedbackStats: async () =>
    request<{ categories: FeedbackCategoryStats[] }>("/feedback/stats"),
  resetFeedbackModel: async () =>
    request<{ status: string; message: string }>("/feedback/reset", { method: "POST" }),

  // Guideline Health
  getGuidelineHealth: async () => request<GuidelineHealthClause[]>("/guidelines/health"),
  recomputeGuidelineHealth: async () =>
    request<{ status: string; updated_clauses: number; message: string }>("/guidelines/recompute", {
      method: "POST",
    }),
  applyGuidelineRevision: async (clauseId: string, text: string) =>
    request<any>(`/guidelines/clauses/${encodeURIComponent(clauseId)}`, {
      method: "PATCH",
      body: JSON.stringify({ text }),
    }),

  // Admin User & System Management
  getUsers: async () => request<User[]>("/admin/users"),
  createUser: async (data: { name: string; email: string; password: string; role: string }) =>
    request<User>("/admin/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateUser: async (userId: string, data: { name?: string; role?: string; is_active?: boolean }) =>
    request<User>(`/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  resetUserPassword: async (userId: string, password: string) =>
    request<any>(`/admin/users/${userId}/reset-password`, {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  getSystemSettings: async () => request<SystemSettings>("/admin/settings"),
  updateSystemSettings: async (data: Partial<SystemSettings>) =>
    request<SystemSettings>("/admin/settings", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  getAuditLogs: async (params?: { action?: string; entity?: string; user_id?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.action) q.set("action", params.action);
    if (params?.entity) q.set("entity", params.entity);
    if (params?.user_id) q.set("user_id", params.user_id);
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    const qs = q.toString() ? `?${q.toString()}` : "";
    return request<AuditLog[]>(`/admin/audit-logs${qs}`);
  },

  // System
  getSystemStatus: async () => request<SystemStatus>("/system/status"),
  getSystemMode: async () => request<{ llm_mode: string; demo_mode: boolean }>("/system/mode"),
  getHealth: async () => request<{ status: string; version: string }>("/health"),
};

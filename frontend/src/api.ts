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
  RepeatedIssue,
  GuidelineHealthClause,
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
    request<Decision>(`/findings/${findingId}/decision`, {
      method: "POST",
      body: JSON.stringify({ action, edited_text, reason }),
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
  getGuidelineHealth: async () => request<GuidelineHealthClause[]>("/guidelines/health"),
  applyGuidelineRevision: async (clauseId: string, text: string) =>
    request<any>(`/guidelines/clauses/${encodeURIComponent(clauseId)}`, {
      method: "PATCH",
      body: JSON.stringify({ text }),
    }),
  createAsset: async (data: { kind: string; name: string; file_path?: string }) =>
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

  // Insights
  getInsightsSummary: async () => request<InsightsSummary>("/insights/summary"),
  getRepeatedIssues: async () =>
    request<{ repeated_issues: RepeatedIssue[] }>("/insights/repeated-issues"),

  // System
  getSystemStatus: async () => request<SystemStatus>("/system/status"),
  getHealth: async () => request<{ status: string; version: string }>("/health"),
};

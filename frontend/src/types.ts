export type UserRole = "creator" | "manager" | "reviewer" | "admin";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export type SubmissionStatus =
  | "draft"
  | "checked"
  | "in_review"
  | "changes_requested"
  | "approved"
  | "rejected";

export type FindingCategory =
  | "tone"
  | "terminology"
  | "messaging"
  | "factual_accuracy"
  | "unsupported_claim"
  | "accessibility";

export type FindingSeverity = "critical" | "major" | "minor" | "info";
export type FindingConfidence = "high" | "medium" | "low";
export type FindingStatus = "open" | "accepted" | "edited" | "disputed";

export interface Decision {
  id: string;
  finding_id: string;
  user_id: string;
  action: "accept" | "edit" | "dispute";
  edited_text?: string;
  reason?: string;
  created_at: string;
  user?: User;
}

export interface Comment {
  id: string;
  submission_id: string;
  finding_id?: string;
  user_id: string;
  body: string;
  created_at: string;
  user?: User;
}

export interface Approval {
  id: string;
  submission_id: string;
  version_id?: string;
  user_id: string;
  decision: "approved" | "changes_requested" | "rejected";
  note?: string;
  created_at: string;
  user?: User;
}

export interface Finding {
  id: string;
  submission_id: string;
  version_id: string;
  span_start?: number;
  span_end?: number;
  category: FindingCategory;
  issue: string;
  source_type?: string;
  source_id?: string;
  source_quote?: string;
  severity: FindingSeverity;
  confidence: FindingConfidence;
  acceptance_probability?: number | null;
  suggested_rewrite?: string;
  needs_human: boolean;
  status: FindingStatus;
  created_at: string;
  decisions: Decision[];
  location?: { page?: number; bbox?: [number, number, number, number]; media?: string } | null;
}

export interface SubmissionVersion {
  id: string;
  submission_id: string;
  version_no: number;
  text: string;
  source_mime_type?: string;
  source_filename?: string;
  source_layout?: {
    width?: number;
    height?: number;
    pages?: Array<{ page: number; width: number; height: number }>;
    regions?: Array<{ page?: number; start: number; end: number; bbox: number[] }>;
  } | null;
  created_by: string;
  created_at: string;
  creator?: User;
}

export interface Submission {
  id: string;
  creator_id: string;
  title: string;
  intent?: string;
  status: SubmissionStatus;
  content_type: string;
  created_at: string;
  updated_at: string;
  creator?: User;
  versions: SubmissionVersion[];
  finding_count?: number;
}

export interface GuidelineClause {
  id: string;
  doc_id: string;
  code?: string;
  title?: string;
  text: string;
  order_index: number;
}

export interface GuidelineDoc {
  id: string;
  title: string;
  description?: string;
  created_at: string;
  clauses: GuidelineClause[];
}

export interface GuidelineDisputeCluster {
  count: number;
  examples: string[];
}

export interface GuidelineHealthClause {
  id: string;
  doc_id: string;
  doc_title: string;
  code?: string;
  title?: string;
  text: string;
  dispute_friction_index: number;
  dispute_clusters: GuidelineDisputeCluster[];
  proposed_revision?: string | null;
}

export interface ApprovedFact {
  id: string;
  statement: string;
  source_note?: string;
  valid_from?: string;
  valid_to?: string;
  created_at: string;
}

export interface Term {
  id: string;
  preferred: string;
  avoid: string[];
  note?: string;
  created_at: string;
}

export interface Asset {
  id: string;
  kind: string;
  name: string;
  file_path?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface SystemStatus {
  app_name: string;
  version: string;
  llm_mode: string;
  llm_available: boolean;
  database_connected: boolean;
  chroma_indexed: boolean;
  source_counts: Record<string, number>;
}

export interface InsightsSummary {
  total_submissions: number;
  total_findings: number;
  findings_by_category: Record<string, number>;
  findings_by_severity: Record<string, number>;
  accepted_count: number;
  disputed_count: number;
  edited_count: number;
  open_count: number;
  avg_turnaround_hours?: number;
  dropped_findings_count: number;
}

export interface RepeatedIssue {
  issue_pattern: string;
  category: string;
  severity: string;
  count: number;
}

export interface FeedbackCategoryStats {
  category: string;
  decisions_count: number;
  acceptance_rate: number;
  edit_rate: number;
  suppression_count: number;
}

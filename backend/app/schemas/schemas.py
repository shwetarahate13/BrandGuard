"""Pydantic v2 schemas for BrandGuard API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


# ── Auth ──

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Guidelines ──

class GuidelineDocCreate(BaseModel):
    title: str
    description: Optional[str] = None
    text: Optional[str] = None  # raw text to auto-split into clauses

class GuidelineDocResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    created_at: datetime
    clauses: list["GuidelineClauseResponse"] = []
    model_config = {"from_attributes": True}

class GuidelineClauseResponse(BaseModel):
    id: str
    doc_id: str
    code: Optional[str] = None
    title: Optional[str] = None
    text: str
    order_index: int
    model_config = {"from_attributes": True}

class GuidelineClauseCreate(BaseModel):
    code: Optional[str] = None
    title: Optional[str] = None
    text: str


# ── Facts ──

class ApprovedFactCreate(BaseModel):
    statement: str
    source_note: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

class ApprovedFactResponse(BaseModel):
    id: str
    statement: str
    source_note: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Terms ──

class TermCreate(BaseModel):
    preferred: str
    avoid: list[str] = []
    note: Optional[str] = None

class TermResponse(BaseModel):
    id: str
    preferred: str
    avoid: list[str] = []
    note: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Assets ──

class AssetCreate(BaseModel):
    kind: str = "other"
    name: str
    file_path: Optional[str] = None

class AssetResponse(BaseModel):
    id: str
    kind: str
    name: str
    file_path: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Submissions ──

class SubmissionCreate(BaseModel):
    title: str
    intent: Optional[str] = None
    text: Optional[str] = None
    content_type: str = "text"

class SubmissionResponse(BaseModel):
    id: str
    creator_id: str
    title: str
    intent: Optional[str] = None
    status: str
    content_type: str
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserResponse] = None
    versions: list["VersionResponse"] = []
    model_config = {"from_attributes": True}

class SubmissionListResponse(BaseModel):
    id: str
    creator_id: str
    title: str
    intent: Optional[str] = None
    status: str
    content_type: str
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserResponse] = None
    finding_count: Optional[int] = None
    model_config = {"from_attributes": True}

class VersionResponse(BaseModel):
    id: str
    submission_id: str
    version_no: int
    text: str
    created_by: str
    created_at: datetime
    creator: Optional[UserResponse] = None
    model_config = {"from_attributes": True}

class VersionCreate(BaseModel):
    text: str


# ── Findings ──

class FindingResponse(BaseModel):
    id: str
    submission_id: str
    version_id: str
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    category: str
    issue: str
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_quote: Optional[str] = None
    severity: str
    confidence: str
    suggested_rewrite: Optional[str] = None
    needs_human: bool = False
    status: str
    created_at: datetime
    decisions: list["DecisionResponse"] = []
    model_config = {"from_attributes": True}


# ── Decisions ──

class DecisionCreate(BaseModel):
    action: str  # accept, edit, dispute
    edited_text: Optional[str] = None
    reason: Optional[str] = None

class DecisionResponse(BaseModel):
    id: str
    finding_id: str
    user_id: str
    action: str
    edited_text: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime
    user: Optional[UserResponse] = None
    model_config = {"from_attributes": True}


# ── Comments ──

class CommentCreate(BaseModel):
    body: str
    finding_id: Optional[str] = None

class CommentResponse(BaseModel):
    id: str
    submission_id: str
    finding_id: Optional[str] = None
    user_id: str
    body: str
    created_at: datetime
    user: Optional[UserResponse] = None
    model_config = {"from_attributes": True}


# ── Approvals ──

class ApprovalCreate(BaseModel):
    decision: str  # approved, changes_requested, rejected
    note: Optional[str] = None

class ApprovalResponse(BaseModel):
    id: str
    submission_id: str
    version_id: Optional[str] = None
    user_id: str
    decision: str
    note: Optional[str] = None
    created_at: datetime
    user: Optional[UserResponse] = None
    model_config = {"from_attributes": True}


# ── Audit Log ──

class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    entity: Optional[str] = None
    entity_id: Optional[str] = None
    meta: dict = {}
    created_at: datetime
    user: Optional[UserResponse] = None
    model_config = {"from_attributes": True}


# ── Insights ──

class InsightsSummary(BaseModel):
    total_submissions: int = 0
    total_findings: int = 0
    findings_by_category: dict[str, int] = {}
    findings_by_severity: dict[str, int] = {}
    accepted_count: int = 0
    disputed_count: int = 0
    edited_count: int = 0
    open_count: int = 0
    avg_turnaround_hours: Optional[float] = None
    dropped_findings_count: int = 0

class RepeatedIssue(BaseModel):
    issue_pattern: str
    category: str
    count: int
    severity: str

class InsightsRepeatedResponse(BaseModel):
    repeated_issues: list[RepeatedIssue] = []


# ── System ──

class SystemStatus(BaseModel):
    app_name: str
    version: str
    llm_mode: str
    llm_available: bool
    database_connected: bool
    chroma_indexed: bool
    source_counts: dict[str, int] = {}


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = ""

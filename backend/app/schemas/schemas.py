"""Pydantic v2 schemas for BrandGuard API."""
from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator


# ── Auth ──

class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=100)

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=12, max_length=72)

    @field_validator("new_password")
    @classmethod
    def new_password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value

class DemoLoginRequest(BaseModel):
    role: Literal["creator", "manager", "reviewer", "admin"]

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

class GuidelineClauseRevision(BaseModel):
    text: str = Field(min_length=1, max_length=50000)

    @field_validator("text")
    @classmethod
    def reject_blank_revision(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Revision text cannot be blank")
        return value

class GuidelineDisputeCluster(BaseModel):
    count: int
    examples: list[str] = Field(default_factory=list)

class GuidelineHealthClause(BaseModel):
    id: str
    doc_id: str
    doc_title: str
    code: Optional[str] = None
    title: Optional[str] = None
    text: str
    dispute_friction_index: float
    dispute_clusters: list[GuidelineDisputeCluster] = Field(default_factory=list)
    proposed_revision: Optional[str] = None
    proposal_source: Optional[str] = None
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
    metadata: Optional[dict] = None

class AssetResponse(BaseModel):
    id: str
    kind: str
    name: str
    file_path: Optional[str] = None
    metadata: Optional[dict] = Field(default=None, validation_alias="metadata_")
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Submissions ──

class SubmissionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    intent: Optional[str] = None
    text: Optional[str] = Field(default=None, max_length=200_000)
    content_type: str = "text"

    @field_validator("title")
    @classmethod
    def title_is_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Submission title cannot be blank")
        return value

class SubmissionResponse(BaseModel):
    id: str
    creator_id: str
    assigned_to_id: Optional[str] = None
    assignment_due_at: Optional[datetime] = None
    title: str
    intent: Optional[str] = None
    status: str
    content_type: str
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserResponse] = None
    assigned_to: Optional[UserResponse] = None
    versions: list["VersionResponse"] = []
    model_config = {"from_attributes": True}

    @field_validator("assignment_due_at", mode="before")
    @classmethod
    def due_date_is_utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class SubmissionListResponse(BaseModel):
    id: str
    creator_id: str
    assigned_to_id: Optional[str] = None
    assignment_due_at: Optional[datetime] = None
    title: str
    intent: Optional[str] = None
    status: str
    content_type: str
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserResponse] = None
    assigned_to: Optional[UserResponse] = None
    finding_count: Optional[int] = None
    needs_human_count: Optional[int] = 0
    age_hours: Optional[float] = None
    is_overdue: bool = False
    model_config = {"from_attributes": True}

    @field_validator("assignment_due_at", mode="before")
    @classmethod
    def due_date_is_utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class SubmissionAssignRequest(BaseModel):
    reviewer_id: str


class SubmissionDueDateUpdate(BaseModel):
    assignment_due_at: Optional[datetime] = Field(...)


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    submission_id: Optional[str] = None
    kind: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class EscalatedReviewRequest(BaseModel):
    action: Literal["confirm", "dismiss"]
    justification: str = Field(min_length=5, max_length=2000)


class ReviewerSignoffRequest(BaseModel):
    checklist: dict[str, bool]
    evidence_notes: str = Field(min_length=5, max_length=5000)
    justification: str = Field(min_length=5, max_length=2000)


# ── Admin User Management ──

class UserCreateAdmin(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=72)
    role: str = "creator"

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class UserUpdateAdmin(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResetPasswordAdmin(BaseModel):
    password: str = Field(min_length=12, max_length=72)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


# ── Admin System Settings ──

class SystemSettingsResponse(BaseModel):
    llm_enabled: bool
    min_confidence: str
    similarity_threshold: float
    brand_words: list[str] = []
    updated_at: datetime
    model_config = {"from_attributes": True}


class SystemSettingsUpdate(BaseModel):
    llm_enabled: Optional[bool] = None
    min_confidence: Optional[str] = None
    similarity_threshold: Optional[float] = None
    brand_words: Optional[list[str]] = None


# ── Creator Personal Stats ──

class CreatorPersonalStats(BaseModel):
    total_submissions: int = 0
    acceptance_rate: float = 0.0
    recurring_mistakes: list["RepeatedIssue"] = []
    notifications: list[str] = []
    pending_action_count: int = 0

class VersionResponse(BaseModel):
    id: str
    submission_id: str
    version_no: int
    text: str
    source_mime_type: Optional[str] = None
    source_filename: Optional[str] = None
    source_layout: Optional[dict] = None
    created_by: str
    created_at: datetime
    creator: Optional[UserResponse] = None
    model_config = {"from_attributes": True}

class VersionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)

    @field_validator("text")
    @classmethod
    def version_text_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Submission content cannot be blank")
        return value


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
    acceptance_probability: Optional[float] = None
    suggested_rewrite: Optional[str] = None
    needs_human: bool = False
    status: str
    location: Optional[dict] = None
    created_at: datetime
    decisions: list["DecisionResponse"] = []
    model_config = {"from_attributes": True}


# ── Decisions ──

class DecisionCreate(BaseModel):
    action: str  # accept, edit, dispute
    edited_text: Optional[str] = None
    reason: Optional[str] = None

class DecisionRequest(DecisionCreate):
    finding_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    action: Literal["accept", "edit", "dispute"]
    edited_text: Optional[str] = Field(default=None, max_length=50000)
    reason: Optional[str] = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def edited_action_requires_text(self):
        if self.action == "edit" and not (self.edited_text or "").strip():
            raise ValueError("edited_text is required for edit decisions")
        return self


class ApplySafeFixesRequest(BaseModel):
    finding_ids: list[str] = Field(min_length=1, max_length=200)
    mode: Literal["grammar", "safe"] = "safe"


class ApplySafeFixesResponse(BaseModel):
    submission_id: str
    version_no: int
    applied_finding_ids: list[str]
    applied_count: int

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
    body: str = Field(min_length=1, max_length=5000)
    finding_id: Optional[str] = None

    @field_validator("body")
    @classmethod
    def comment_body_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Comment cannot be blank")
        return value.strip()

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
    content_hash: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime
    user: Optional[UserResponse] = None
    model_config = {"from_attributes": True}


# ── Audit Log ──

class AuditLogResponse(BaseModel):
    id: str
    submission_id: Optional[str] = None
    user_id: Optional[str] = None
    action: str
    entity: Optional[str] = None
    entity_id: Optional[str] = None
    meta: dict = {}
    created_at: datetime
    sequence_no: int = 1
    prev_hash: Optional[str] = None
    entry_hash: str
    chained_at: datetime
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
    submissions_by_day: dict[str, int] = {}
    findings_by_day: dict[str, int] = {}

class RepeatedIssue(BaseModel):
    issue_pattern: str
    category: str
    count: int
    severity: str

class InsightsRepeatedResponse(BaseModel):
    repeated_issues: list[RepeatedIssue] = []


class FeedbackCategoryStats(BaseModel):
    category: str
    decisions_count: int = 0
    acceptance_rate: float = 0.0
    edit_rate: float = 0.0
    suppression_count: int = 0


class FeedbackStatsResponse(BaseModel):
    categories: list[FeedbackCategoryStats] = Field(default_factory=list)


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

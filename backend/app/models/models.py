"""SQLAlchemy models for BrandGuard."""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, LargeBinary,
    ForeignKey, Enum as SAEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ──

class UserRole(str, enum.Enum):
    creator = "creator"
    manager = "manager"
    reviewer = "reviewer"
    admin = "admin"


class SubmissionStatus(str, enum.Enum):
    draft = "draft"
    checked = "checked"
    in_review = "in_review"
    changes_requested = "changes_requested"
    approved = "approved"
    rejected = "rejected"


class FindingCategory(str, enum.Enum):
    tone = "tone"
    terminology = "terminology"
    messaging = "messaging"
    factual_accuracy = "factual_accuracy"
    unsupported_claim = "unsupported_claim"
    accessibility = "accessibility"


class FindingSeverity(str, enum.Enum):
    critical = "critical"
    major = "major"
    minor = "minor"
    info = "info"


class FindingConfidence(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class FindingStatus(str, enum.Enum):
    open = "open"
    accepted = "accepted"
    edited = "edited"
    disputed = "disputed"


class DecisionAction(str, enum.Enum):
    accept = "accept"
    edit = "edit"
    dispute = "dispute"


class ApprovalDecision(str, enum.Enum):
    approved = "approved"
    changes_requested = "changes_requested"
    rejected = "rejected"


class SourceType(str, enum.Enum):
    guideline_clause = "guideline_clause"
    approved_fact = "approved_fact"
    term = "term"
    asset = "asset"


class ContentType(str, enum.Enum):
    text = "text"
    pdf = "pdf"
    docx = "docx"
    markdown = "markdown"
    html = "html"
    image = "image"


class AssetKind(str, enum.Enum):
    logo = "logo"
    image = "image"
    template = "template"
    other = "other"


# ── Models ──

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(200), nullable=False)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.creator)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    submissions = relationship("Submission", back_populates="creator")
    decisions = relationship("Decision", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    approvals = relationship("Approval", back_populates="user")


class GuidelineDoc(Base):
    __tablename__ = "guideline_docs"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    clauses = relationship("GuidelineClause", back_populates="doc", cascade="all, delete-orphan")


class GuidelineClause(Base):
    __tablename__ = "guideline_clauses"

    id = Column(String, primary_key=True, default=gen_id)
    doc_id = Column(String, ForeignKey("guideline_docs.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=True)
    title = Column(String(500), nullable=True)
    text = Column(Text, nullable=False)
    order_index = Column(Integer, default=0)
    dispute_friction_index = Column(Float, nullable=False, default=0.0, server_default="0")
    created_at = Column(DateTime, default=utcnow)

    doc = relationship("GuidelineDoc", back_populates="clauses")


class ApprovedFact(Base):
    __tablename__ = "approved_facts"

    id = Column(String, primary_key=True, default=gen_id)
    statement = Column(Text, nullable=False)
    source_note = Column(Text, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Term(Base):
    __tablename__ = "terms"

    id = Column(String, primary_key=True, default=gen_id)
    preferred = Column(String(300), nullable=False)
    avoid = Column(JSON, default=list)  # list of strings
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True, default=gen_id)
    kind = Column(SAEnum(AssetKind), nullable=False, default=AssetKind.other)
    name = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String, primary_key=True, default=gen_id)
    creator_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    intent = Column(Text, nullable=True)
    status = Column(SAEnum(SubmissionStatus), default=SubmissionStatus.draft, nullable=False)
    content_type = Column(SAEnum(ContentType), default=ContentType.text, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    creator = relationship("User", back_populates="submissions")
    versions = relationship("SubmissionVersion", back_populates="submission", order_by="SubmissionVersion.version_no")
    findings = relationship("Finding", back_populates="submission")
    comments = relationship("Comment", back_populates="submission", order_by="Comment.created_at")
    approvals = relationship("Approval", back_populates="submission", order_by="Approval.created_at")


class SubmissionVersion(Base):
    __tablename__ = "submission_versions"

    id = Column(String, primary_key=True, default=gen_id)
    submission_id = Column(String, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    version_no = Column(Integer, nullable=False, default=1)
    text = Column(Text, nullable=False)
    source_file = Column(LargeBinary, nullable=True)
    source_mime_type = Column(String(100), nullable=True)
    source_filename = Column(String(500), nullable=True)
    source_layout = Column(JSON, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    submission = relationship("Submission", back_populates="versions")
    findings_for_version = relationship("Finding", back_populates="version")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_version_submission", "submission_id", "version_no", unique=True),
    )


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String, primary_key=True, default=gen_id)
    submission_id = Column(String, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(String, ForeignKey("submission_versions.id", ondelete="CASCADE"), nullable=False)
    span_start = Column(Integer, nullable=True)
    span_end = Column(Integer, nullable=True)
    category = Column(SAEnum(FindingCategory), nullable=False)
    issue = Column(Text, nullable=False)
    source_type = Column(SAEnum(SourceType), nullable=True)
    source_id = Column(String, nullable=True)
    source_quote = Column(Text, nullable=True)
    severity = Column(SAEnum(FindingSeverity), nullable=False)
    confidence = Column(SAEnum(FindingConfidence), nullable=False, default=FindingConfidence.high)
    suggested_rewrite = Column(Text, nullable=True)
    needs_human = Column(Boolean, default=False)
    status = Column(SAEnum(FindingStatus), default=FindingStatus.open, nullable=False)
    location = Column(JSON, nullable=True)  # For future format-aware review
    created_at = Column(DateTime, default=utcnow)

    submission = relationship("Submission", back_populates="findings")
    version = relationship("SubmissionVersion", back_populates="findings_for_version")
    decisions = relationship("Decision", back_populates="finding", order_by="Decision.created_at")
    comments = relationship("Comment", back_populates="finding")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String, primary_key=True, default=gen_id)
    finding_id = Column(String, ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    action = Column(SAEnum(DecisionAction), nullable=False)
    edited_text = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    finding = relationship("Finding", back_populates="decisions")
    user = relationship("User", back_populates="decisions")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(String, primary_key=True, default=gen_id)
    submission_id = Column(String, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    finding_id = Column(String, ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    submission = relationship("Submission", back_populates="comments")
    finding = relationship("Finding", back_populates="comments")
    user = relationship("User", back_populates="comments")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, default=gen_id)
    submission_id = Column(String, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(String, ForeignKey("submission_versions.id"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    decision = Column(SAEnum(ApprovalDecision), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    submission = relationship("Submission", back_populates="approvals")
    user = relationship("User", back_populates="approvals")
    version = relationship("SubmissionVersion")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity = Column(String(100), nullable=True)
    entity_id = Column(String, nullable=True)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")

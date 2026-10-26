"""Approval report exports for managers and administrators."""
import csv
import io
import textwrap
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from backend.app.database import get_db
from backend.app.models.models import Approval, Submission, User
from backend.app.services.auth import get_current_user
from backend.app.services.permissions import Action, check_permission


router = APIRouter(prefix="/reports", tags=["reports"])

REPORT_HEADERS = [
    "Approval ID",
    "Submission ID",
    "Content title",
    "Content type",
    "Creator",
    "Assigned reviewer",
    "Decision",
    "Decision by",
    "Decision at (UTC)",
    "Submission status",
    "Assignment due at (UTC)",
    "Review note",
]


def _as_utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _format_utc(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return aware.isoformat()


def _validate_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> None:
    if start_date and end_date and _as_utc_naive(start_date) > _as_utc_naive(end_date):
        raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")


def _approval_rows(
    db: Session,
    start_date: Optional[datetime],
    end_date: Optional[datetime],
) -> list[list[str]]:
    query = (
        db.query(Approval)
        .options(
            joinedload(Approval.user),
            joinedload(Approval.submission).joinedload(Submission.creator),
            joinedload(Approval.submission).joinedload(Submission.assigned_to),
        )
        .join(Submission, Approval.submission_id == Submission.id)
    )
    if start_date:
        query = query.filter(Approval.created_at >= _as_utc_naive(start_date))
    if end_date:
        query = query.filter(Approval.created_at <= _as_utc_naive(end_date))

    rows = []
    for approval in query.order_by(Approval.created_at.asc(), Approval.id.asc()).all():
        submission = approval.submission
        rows.append([
            approval.id,
            submission.id,
            submission.title,
            submission.content_type.value if hasattr(submission.content_type, "value") else str(submission.content_type),
            submission.creator.name if submission.creator else "Unknown",
            submission.assigned_to.name if submission.assigned_to else "",
            approval.decision.value if hasattr(approval.decision, "value") else str(approval.decision),
            approval.user.name if approval.user else "Unknown",
            _format_utc(approval.created_at),
            submission.status.value if hasattr(submission.status, "value") else str(submission.status),
            _format_utc(submission.assignment_due_at),
            approval.note or "",
        ])
    return rows


def _csv_safe(value: str) -> str:
    # Prevent spreadsheet software from evaluating exported text as a formula.
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _pdf_escape(value: str) -> bytes:
    encoded = value.encode("cp1252", errors="replace").decode("cp1252")
    escaped = encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped.encode("cp1252")


def _approval_pdf(rows: list[list[str]], start_date: Optional[datetime], end_date: Optional[datetime]) -> bytes:
    title = "BrandGuard Approval Report"
    if start_date or end_date:
        title += f" ({start_date.isoformat() if start_date else 'Beginning'} to {end_date.isoformat() if end_date else 'Now'})"
    lines = [title, f"{len(rows)} workflow decision(s)", ""]
    for row in rows:
        details = [
            f"Decision: {row[6]} | Decided (UTC): {row[8]}",
            f"Content: {row[2]} | Submission ID: {row[1]}",
            f"Creator: {row[4]} | Assigned reviewer: {row[5] or 'None'}",
            f"Decision by: {row[7]} | Content type: {row[3]} | Current status: {row[9]}",
            f"Assignment due (UTC): {row[10] or 'None'}",
            f"Review note: {row[11] or 'None'}",
            "",
        ]
        for detail in details:
            lines.extend(textwrap.wrap(detail, width=104, break_long_words=True, break_on_hyphens=False) or [""])

    page_lines = [lines[index:index + 46] for index in range(0, len(lines), 46)] or [[]]
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_object_ids = [4 + index * 2 for index in range(len(page_lines))]
    kids = b" ".join(f"{object_id} 0 R".encode("ascii") for object_id in page_object_ids)
    objects.append(b"<< /Type /Pages /Kids [" + kids + f"] /Count {len(page_lines)} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for page_index, content_lines in enumerate(page_lines):
        page_id = page_object_ids[page_index]
        content_id = page_id + 1
        commands = [b"BT", b"/F1 9 Tf", b"40 560 Td", b"12 TL"]
        for line in content_lines:
            commands.extend([b"(" + _pdf_escape(line) + b") Tj", b"T*"])
        commands.append(b"ET")
        stream = b"\n".join(commands)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 792 612] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii")
        )
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


@router.get("/approvals.csv")
def export_approval_report_csv(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.APPROVAL_REPORT_EXPORT)
    _validate_date_range(start_date, end_date)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(REPORT_HEADERS)
    writer.writerows([_csv_safe(value) for value in row] for row in _approval_rows(db, start_date, end_date))
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="brandguard_approval_report.csv"'},
    )


@router.get("/approvals.pdf")
def export_approval_report_pdf(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.APPROVAL_REPORT_EXPORT)
    _validate_date_range(start_date, end_date)
    rows = _approval_rows(db, start_date, end_date)
    return Response(
        content=_approval_pdf(rows, start_date, end_date),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="brandguard_approval_report.pdf"'},
    )

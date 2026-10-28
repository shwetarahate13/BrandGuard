"""Dispute thresholds for individual offline grammar rules."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.models import WritingRuleDispute


def writing_rule_dispute_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(WritingRuleDispute.rule_id, func.count(WritingRuleDispute.id))
        .group_by(WritingRuleDispute.rule_id)
        .all()
    )
    return {str(rule_id): int(count) for rule_id, count in rows}


def suppressed_writing_rules(db: Session, threshold: int = 3) -> set[str]:
    return {rule_id for rule_id, count in writing_rule_dispute_counts(db).items() if count >= threshold}

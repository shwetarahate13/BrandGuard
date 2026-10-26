"""Workspace-level reviewer feedback analytics and admin model reset."""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import Decision, Finding, FindingCategory, User, PreferenceModelState
from backend.app.pipeline.confidence import suppressed_counts_by_category
from backend.app.schemas.schemas import FeedbackCategoryStats, FeedbackStatsResponse
from backend.app.services.auth import get_current_user
from backend.app.services.permissions import Action, check_permission
from backend.app.utils.audit import log_action

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/stats", response_model=FeedbackStatsResponse)
def get_feedback_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Report acceptance, edit, and repeated-dismissal rates by finding category."""
    check_permission(current_user, Action.FEEDBACK_STATS_VIEW)
    rows = (
        db.query(Finding.category, Decision.action, func.count(Decision.id))
        .join(Decision, Decision.finding_id == Finding.id)
        .group_by(Finding.category, Decision.action)
        .all()
    )
    counts: dict[str, dict[str, int]] = {
        category.value: {"accept": 0, "edit": 0, "dispute": 0}
        for category in FindingCategory
    }
    for category, action, count in rows:
        category_name = category.value if hasattr(category, "value") else str(category)
        action_name = action.value if hasattr(action, "value") else str(action)
        counts.setdefault(category_name, {"accept": 0, "edit": 0, "dispute": 0})
        counts[category_name][action_name] = int(count)

    suppressed = suppressed_counts_by_category(db)
    categories = []
    for category_name, actions in counts.items():
        total = sum(actions.values())
        categories.append(FeedbackCategoryStats(
            category=category_name,
            decisions_count=total,
            acceptance_rate=actions["accept"] / total if total else 0.0,
            edit_rate=actions["edit"] / total if total else 0.0,
            suppression_count=int(suppressed.get(category_name, 0)),
        ))
    return FeedbackStatsResponse(categories=categories)


@router.post("/reset")
def reset_feedback_model(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset the online preference feedback model state (Admin only)."""
    check_permission(current_user, Action.FEEDBACK_RESET)
    db.query(PreferenceModelState).delete()
    log_action(db, current_user.id, "reset_feedback_model", "preference_model_state", "workspace-default")
    db.commit()
    return {"status": "ok", "message": "Feedback model state reset successfully"}

"""Authenticated status endpoint for bounded background work."""
from fastapi import APIRouter, Depends, HTTPException

from backend.app.models.models import User
from backend.app.workers.background_jobs import background_jobs
from backend.app.services.auth import get_current_user

router = APIRouter(prefix="/jobs", tags=["background jobs"])


@router.get("/{job_id}")
def get_background_job(job_id: str, current_user: User = Depends(get_current_user)):
    job = background_jobs.get(job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Background job not found")
    return job

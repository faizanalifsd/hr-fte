"""
Job API Routes - Job listing management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..models import Job, JobStatus, get_db

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class JobResponse(BaseModel):
    """Response model for job data."""
    id: int
    mission_id: int
    company: str
    role: str
    location: Optional[str]
    description: str
    match_score: Optional[float]
    status: str
    hr_email: Optional[str]
    hr_name: Optional[str]
    hr_title: Optional[str]
    hr_email_confidence: Optional[str]
    apply_link: Optional[str]
    source_portal: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# JOB ENDPOINTS
# ============================================================

@router.get("/mission/{mission_id}", response_model=List[JobResponse])
def list_jobs_by_mission(
    mission_id: int,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all jobs for a mission with optional status filter.

    Args:
        mission_id: Mission ID
        status_filter: Filter by job status
    """
    query = db.query(Job).filter(Job.mission_id == mission_id)

    if status_filter:
        try:
            status_enum = JobStatus[status_filter.upper()]
            query = query.filter(Job.status == status_enum)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )

    jobs = query.order_by(Job.created_at.asc()).all()

    return [
        JobResponse(
            id=j.id,
            mission_id=j.mission_id,
            company=j.company,
            role=j.role,
            location=j.location,
            description=j.description,
            match_score=j.match_score,
            status=j.status.value,
            hr_email=j.hr_email,
            hr_name=j.hr_name,
            hr_title=j.hr_title,
            hr_email_confidence=j.hr_email_confidence,
            apply_link=j.apply_link,
            source_portal=j.source_portal,
            created_at=j.created_at
        )
        for j in jobs
    ]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get job by ID.
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    return JobResponse(
        id=job.id,
        mission_id=job.mission_id,
        company=job.company,
        role=job.role,
        location=job.location,
        description=job.description,
        match_score=job.match_score,
        status=job.status.value,
        hr_email=job.hr_email,
        hr_name=job.hr_name,
        apply_link=job.apply_link,
        source_portal=job.source_portal,
        created_at=job.created_at
    )

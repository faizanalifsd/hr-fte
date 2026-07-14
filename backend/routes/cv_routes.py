"""
CV Version API Routes - expose CV versions (original + AI-tailored) to the frontend.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..models import CVVersion, Job, Mission, EmailDraft, EmailStatus, get_db

router = APIRouter(prefix="/api/cvversions", tags=["cvversions"])


class CVVersionResponse(BaseModel):
    id: int
    mission_id: int
    job_id: Optional[int]
    version_name: str
    is_master: int
    content_markdown: str
    keyword_match_score: Optional[int]
    optimization_notes: Optional[str]   # JSON list of suggested improvements
    # Job info (null for master CV)
    job_company: Optional[str]
    job_role: Optional[str]
    job_match_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True



@router.get("/mission/{mission_id}", response_model=List[CVVersionResponse])
def list_cv_versions(mission_id: int, db: Session = Depends(get_db)):
    """
    Return all CV versions for a mission — master first, then per-job tailored.
    """
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Mission {mission_id} not found")

    versions = (
        db.query(CVVersion)
        .filter(CVVersion.mission_id == mission_id)
        .order_by(CVVersion.is_master.desc(), CVVersion.id.asc())
        .all()
    )

    result = []
    for v in versions:
        job = db.query(Job).filter(Job.id == v.job_id).first() if v.job_id else None
        result.append(CVVersionResponse(
            id=v.id,
            mission_id=v.mission_id,
            job_id=v.job_id,
            version_name=v.version_name,
            is_master=v.is_master,
            content_markdown=v.content_markdown or "",
            keyword_match_score=v.keyword_match_score,
            optimization_notes=v.optimization_notes,
            job_company=job.company if job else None,
            job_role=job.role if job else None,
            job_match_score=job.match_score if job else None,
            created_at=v.created_at,
        ))
    return result


@router.get("/{cv_id}", response_model=CVVersionResponse)
def get_cv_version(cv_id: int, db: Session = Depends(get_db)):
    """Return a single CV version by ID."""
    v = db.query(CVVersion).filter(CVVersion.id == cv_id).first()
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"CV version {cv_id} not found")
    job = db.query(Job).filter(Job.id == v.job_id).first() if v.job_id else None
    return CVVersionResponse(
        id=v.id,
        mission_id=v.mission_id,
        job_id=v.job_id,
        version_name=v.version_name,
        is_master=v.is_master,
        content_markdown=v.content_markdown or "",
        keyword_match_score=v.keyword_match_score,
        optimization_notes=v.optimization_notes,
        job_company=job.company if job else None,
        job_role=job.role if job else None,
        job_match_score=job.match_score if job else None,
        created_at=v.created_at,
    )


class CVEditRequest(BaseModel):
    content_markdown: str


class CVAiEditRequest(BaseModel):
    instruction: str


class CVAiEditResponse(BaseModel):
    revised_content: str
    explanation: str


@router.patch("/{cv_id}", response_model=CVVersionResponse)
def save_cv_edit(cv_id: int, body: CVEditRequest, db: Session = Depends(get_db)):
    """Save manually-edited content_markdown back to the CV version."""
    v = db.query(CVVersion).filter(CVVersion.id == cv_id).first()
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"CV version {cv_id} not found")
    v.content_markdown = body.content_markdown[:60000]
    db.commit()
    db.refresh(v)
    job = db.query(Job).filter(Job.id == v.job_id).first() if v.job_id else None
    return CVVersionResponse(
        id=v.id, mission_id=v.mission_id, job_id=v.job_id,
        version_name=v.version_name, is_master=v.is_master,
        content_markdown=v.content_markdown or "",
        keyword_match_score=v.keyword_match_score,
        optimization_notes=v.optimization_notes,
        job_company=job.company if job else None,
        job_role=job.role if job else None,
        job_match_score=job.match_score if job else None,
        created_at=v.created_at,
    )


@router.post("/{cv_id}/ai-edit", response_model=CVAiEditResponse)
def ai_edit_cv(cv_id: int, body: CVAiEditRequest, db: Session = Depends(get_db)):
    """Apply an AI instruction to revise the CV content (does NOT save — frontend decides)."""
    v = db.query(CVVersion).filter(CVVersion.id == cv_id).first()
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"CV version {cv_id} not found")
    if not body.instruction.strip():
        raise HTTPException(status_code=400, detail="Instruction cannot be empty")

    from ..services.ai.ollama_service import OllamaService
    job = db.query(Job).filter(Job.id == v.job_id).first() if v.job_id else None
    job_role = job.role if job else ""

    llm = OllamaService()
    result = llm.edit_cv_with_instruction(
        current_content=v.content_markdown or "",
        instruction=body.instruction.strip(),
        job_role=job_role,
    )
    return CVAiEditResponse(
        revised_content=result["revised_content"],
        explanation=result["explanation"],
    )


class SyncToEmailResponse(BaseModel):
    email_id: int
    subject: str
    body: str
    message: str


@router.post("/{cv_id}/sync-to-email", response_model=SyncToEmailResponse)
def sync_cv_to_email(cv_id: int, db: Session = Depends(get_db)):
    """
    Re-generate the cover letter email for the job linked to this CV version,
    using the current (possibly edited) CV content.

    Only works for tailored CVs (is_master=0) that have a pending email draft.
    """
    v = db.query(CVVersion).filter(CVVersion.id == cv_id).first()
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"CV version {cv_id} not found")
    if v.is_master:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot sync master CV — sync is only for job-tailored CVs")
    if not v.job_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="CV version has no linked job")

    job = db.query(Job).filter(Job.id == v.job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Job {v.job_id} not found")

    email = db.query(EmailDraft).filter(
        EmailDraft.job_id == v.job_id,
        EmailDraft.status == EmailStatus.PENDING_APPROVAL,
    ).first()
    if not email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No pending email draft found for this job")

    # Re-generate the cover letter using the updated CV content
    import json as _json
    from ..services.ai.ollama_service import OllamaService
    llm = OllamaService()

    matched_skills: list = []
    try:
        matched_skills = _json.loads(job.matched_skills) if job.matched_skills else []
    except Exception:
        pass

    # Use first 500 chars of the updated CV as the candidate summary
    cv_summary = (v.content_markdown or "")[:500]

    email_content = llm.generate_email(
        job_role=job.role,
        company=job.company,
        cv_summary=cv_summary,
        hr_name=job.hr_name,
        matched_skills=matched_skills,
    )

    # Append the updated tailored CV beneath the regenerated cover letter
    body = email_content["body"].rstrip()
    if v.content_markdown:
        body = body + "\n\n" + "—" * 40 + "\n\n" + v.content_markdown.strip()

    email.subject = email_content["subject"]
    email.body = body
    db.commit()
    db.refresh(email)

    return SyncToEmailResponse(
        email_id=email.id,
        subject=email.subject,
        body=email.body,
        message="Cover letter regenerated from updated CV",
    )

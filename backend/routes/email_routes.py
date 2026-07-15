"""
Email API Routes - HITL approval workflow for email drafts.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..models import EmailDraft, EmailStatus, CVVersion, Job, get_db
from ..services.orchestrator import ApplicationOrchestrator, RecipientNotConfirmedError

router = APIRouter(prefix="/api/emails", tags=["emails"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class EmailDraftResponse(BaseModel):
    """Response model for email draft."""
    id: int
    job_id: int
    subject: str
    body: str
    to_email: str
    to_name: Optional[str]
    hr_title: Optional[str]              # Apollo Phase 4C — HR contact job title
    hr_email_confidence: Optional[str]   # Apollo Phase 4C — "verified"|"likely"|"none"
    recipient_confirmed: bool            # False = to_email is an unverified guess, blocks approval
    status: str
    created_at: datetime
    approved_at: Optional[datetime]

    class Config:
        from_attributes = True


class EmailApproveRequest(BaseModel):
    """Request model for email approval."""
    approved_by: str = "user"


class EmailRejectRequest(BaseModel):
    """Request model for email rejection."""
    reason: Optional[str] = None


class EmailEditRequest(BaseModel):
    """Request model for email editing."""
    subject: Optional[str] = None
    body: Optional[str] = None
    to_email: Optional[str] = None


# ============================================================
# EMAIL DRAFT ENDPOINTS
# ============================================================

@router.get("/pending", response_model=List[EmailDraftResponse])
def list_pending_emails(
    db: Session = Depends(get_db)
):
    """
    List all emails pending approval.

    Phase 8: HITL Approval
    """
    emails = db.query(EmailDraft).filter(
        EmailDraft.status == EmailStatus.PENDING_APPROVAL
    ).all()

    result = []
    for e in emails:
        job = db.query(Job).filter(Job.id == e.job_id).first()
        result.append(EmailDraftResponse(
            id=e.id,
            job_id=e.job_id,
            subject=e.subject,
            body=e.body,
            to_email=e.to_email,
            to_name=e.to_name,
            hr_title=job.hr_title if job else None,
            hr_email_confidence=job.hr_email_confidence if job else None,
            recipient_confirmed=e.recipient_confirmed,
            status=e.status.value,
            created_at=e.created_at,
            approved_at=e.approved_at
        ))
    return result


@router.get("/{email_id}", response_model=EmailDraftResponse)
def get_email_draft(
    email_id: int,
    db: Session = Depends(get_db)
):
    """
    Get email draft by ID.
    """
    email = db.query(EmailDraft).filter(EmailDraft.id == email_id).first()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email draft {email_id} not found"
        )

    job = db.query(Job).filter(Job.id == email.job_id).first()
    return EmailDraftResponse(
        id=email.id,
        job_id=email.job_id,
        subject=email.subject,
        body=email.body,
        to_email=email.to_email,
        to_name=email.to_name,
        hr_title=job.hr_title if job else None,
        hr_email_confidence=job.hr_email_confidence if job else None,
        recipient_confirmed=email.recipient_confirmed,
        status=email.status.value,
        created_at=email.created_at,
        approved_at=email.approved_at
    )


@router.post("/{email_id}/approve", response_model=EmailDraftResponse)
def approve_email(
    email_id: int,
    request: EmailApproveRequest,
    db: Session = Depends(get_db)
):
    """
    Approve an email draft.

    Phase 8: HITL - User approves email for sending.
    As per constitution.md 3.1: No email sent without approval.
    """
    try:
        orchestrator = ApplicationOrchestrator(db)
        email = orchestrator.approve_email(email_id, request.approved_by)

        # Find the CV version to attach — job-specific first, then master CV
        job = db.query(Job).filter(Job.id == email.job_id).first()
        cv_version = None
        if job:
            cv_version = (
                db.query(CVVersion).filter(CVVersion.job_id == email.job_id).first()
                or db.query(CVVersion).filter(
                    CVVersion.mission_id == job.mission_id,
                    CVVersion.is_master == 1
                ).first()
            )

        # Send immediately — this is the constitution §3 approved send
        if cv_version:
            orchestrator.send_application(email_id, cv_version.id)
            db.refresh(email)

        job = db.query(Job).filter(Job.id == email.job_id).first()
        return EmailDraftResponse(
            id=email.id,
            job_id=email.job_id,
            subject=email.subject,
            body=email.body,
            to_email=email.to_email,
            to_name=email.to_name,
            hr_title=job.hr_title if job else None,
            hr_email_confidence=job.hr_email_confidence if job else None,
            recipient_confirmed=email.recipient_confirmed,
            status=email.status.value,
            created_at=email.created_at,
            approved_at=email.approved_at
        )

    except RecipientNotConfirmedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval failed: {str(e)}"
        )


@router.post("/{email_id}/reject", response_model=EmailDraftResponse)
def reject_email(
    email_id: int,
    request: EmailRejectRequest,
    db: Session = Depends(get_db)
):
    """
    Reject an email draft.

    Phase 8: HITL - User rejects email.
    As per constitution.md 3.4: Rejected items must be logged.
    """
    try:
        orchestrator = ApplicationOrchestrator(db)
        email = orchestrator.reject_email(email_id, request.reason)

        job = db.query(Job).filter(Job.id == email.job_id).first()
        return EmailDraftResponse(
            id=email.id,
            job_id=email.job_id,
            subject=email.subject,
            body=email.body,
            to_email=email.to_email,
            to_name=email.to_name,
            hr_title=job.hr_title if job else None,
            hr_email_confidence=job.hr_email_confidence if job else None,
            recipient_confirmed=email.recipient_confirmed,
            status=email.status.value,
            created_at=email.created_at,
            approved_at=email.approved_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rejection failed: {str(e)}"
        )


@router.patch("/{email_id}", response_model=EmailDraftResponse)
def edit_email(
    email_id: int,
    request: EmailEditRequest,
    db: Session = Depends(get_db)
):
    """
    Edit email draft content.

    Phase 8: HITL - User can edit email before approval.
    """
    email = db.query(EmailDraft).filter(EmailDraft.id == email_id).first()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email draft {email_id} not found"
        )

    if email.status != EmailStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only edit emails pending approval"
        )

    # Edit content
    email.edit_content(request.subject, request.body, request.to_email)
    db.commit()
    db.refresh(email)

    job = db.query(Job).filter(Job.id == email.job_id).first()
    return EmailDraftResponse(
        id=email.id,
        job_id=email.job_id,
        subject=email.subject,
        body=email.body,
        to_email=email.to_email,
        to_name=email.to_name,
        hr_title=job.hr_title if job else None,
        hr_email_confidence=job.hr_email_confidence if job else None,
        recipient_confirmed=email.recipient_confirmed,
        status=email.status.value,
        created_at=email.created_at,
        approved_at=email.approved_at
    )

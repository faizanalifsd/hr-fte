"""
Application API Routes - Application sending and tracking.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..models import ApplicationRecord, ApplicationOutcome, get_db
from ..services.orchestrator import ApplicationOrchestrator

router = APIRouter(prefix="/api/applications", tags=["applications"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class ApplicationResponse(BaseModel):
    """Response model for application record."""
    id: int
    job_id: int
    company: str
    hr_email: str
    hr_name: Optional[str]
    gmail_message_id: Optional[str]
    sent_at: datetime
    outcome: str

    class Config:
        from_attributes = True


class SendApplicationRequest(BaseModel):
    """Request model for sending application."""
    email_draft_id: int
    cv_version_id: int


# ============================================================
# APPLICATION ENDPOINTS
# ============================================================

@router.post("/send", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def send_application(
    request: SendApplicationRequest,
    db: Session = Depends(get_db)
):
    """
    Send approved application via Gmail.

    Phase 9: Application Sending
    """
    try:
        orchestrator = ApplicationOrchestrator(db)
        app_record = orchestrator.send_application(
            email_draft_id=request.email_draft_id,
            cv_version_id=request.cv_version_id
        )

        return ApplicationResponse(
            id=app_record.id,
            job_id=app_record.job_id,
            company=app_record.company,
            hr_email=app_record.hr_email,
            hr_name=app_record.hr_name,
            gmail_message_id=app_record.gmail_message_id,
            sent_at=app_record.sent_at,
            outcome=app_record.outcome.value
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Application sending failed: {str(e)}"
        )


@router.get("/", response_model=List[ApplicationResponse])
def list_applications(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all sent applications.
    """
    applications = db.query(ApplicationRecord).offset(skip).limit(limit).all()

    return [
        ApplicationResponse(
            id=a.id,
            job_id=a.job_id,
            company=a.company,
            hr_email=a.hr_email,
            hr_name=a.hr_name,
            gmail_message_id=a.gmail_message_id,
            sent_at=a.sent_at,
            outcome=a.outcome.value
        )
        for a in applications
    ]


@router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(
    application_id: int,
    db: Session = Depends(get_db)
):
    """
    Get application record by ID.
    """
    app = db.query(ApplicationRecord).filter(
        ApplicationRecord.id == application_id
    ).first()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )

    return ApplicationResponse(
        id=app.id,
        job_id=app.job_id,
        company=app.company,
        hr_email=app.hr_email,
        hr_name=app.hr_name,
        gmail_message_id=app.gmail_message_id,
        sent_at=app.sent_at,
        outcome=app.outcome.value
    )

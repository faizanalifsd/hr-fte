"""
ApplicationRecord Model - Immutable record of sent applications.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from . import Base


class ApplicationOutcome(enum.Enum):
    """Application outcome tracking."""
    SENT = "Sent"
    DELIVERED = "Delivered"
    OPENED = "Opened"
    REPLIED = "Replied"
    REJECTED = "Rejected"
    INTERVIEW_SCHEDULED = "Interview_Scheduled"
    OFFER_RECEIVED = "Offer_Received"
    NO_RESPONSE = "No_Response"


class ApplicationRecord(Base):
    """
    ApplicationRecord entity - immutable audit trail of applications.

    As per constitution.md Section 6.2:
    - Company
    - HR email
    - Timestamp
    - Email content hash

    Created in Phase 9 after successful email send.
    """
    __tablename__ = "application_records"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    email_draft_id = Column(Integer, ForeignKey("email_drafts.id"), nullable=False)
    cv_version_id = Column(Integer, ForeignKey("cv_versions.id"), nullable=False)

    # Application Details
    company = Column(String(255), nullable=False, index=True)
    hr_email = Column(String(255), nullable=False, index=True)
    hr_name = Column(String(255), nullable=True)

    # Email Evidence (for audit)
    email_subject = Column(String(500), nullable=False)
    email_content_hash = Column(String(64), nullable=False)  # SHA-256 hash

    # Gmail Details
    gmail_message_id = Column(String(255), nullable=True, unique=True, index=True)
    gmail_thread_id = Column(String(255), nullable=True)

    # Timestamps (immutable)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Tracking
    outcome = Column(
        Enum(ApplicationOutcome),
        default=ApplicationOutcome.SENT,
        nullable=False
    )
    outcome_updated_at = Column(DateTime, nullable=True)
    outcome_notes = Column(Text, nullable=True)

    # Follow-up tracking
    last_follow_up_at = Column(DateTime, nullable=True)
    follow_up_count = Column(Integer, default=0)

    # Relationships
    job = relationship("Job", back_populates="application_records")
    email_draft = relationship("EmailDraft", back_populates="application_records")
    cv_version = relationship("CVVersion", back_populates="application_records")

    def __repr__(self):
        return f"<ApplicationRecord(id={self.id}, company='{self.company}', sent_at={self.sent_at})>"

    def update_outcome(self, outcome: ApplicationOutcome, notes: str = None):
        """Update application outcome (tracking only)."""
        self.outcome = outcome
        self.outcome_updated_at = datetime.utcnow()
        if notes:
            self.outcome_notes = notes

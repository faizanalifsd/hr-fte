"""
EmailDraft Model - Represents generated email drafts awaiting approval.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from . import Base


class EmailStatus(enum.Enum):
    """Email draft status enumeration."""
    PENDING_APPROVAL = "PendingApproval"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    SENT = "Sent"
    FAILED = "Failed"


class EmailDraft(Base):
    """
    EmailDraft entity - stores email drafts for HITL approval.

    As per constitution.md Section 3:
    - No email sent without explicit human approval
    - User can: Approve, Edit, Reject
    - Rejected items must be logged

    Generated in Phase 7 by Ollama (mistral:7b-instruct-q4).
    """
    __tablename__ = "email_drafts"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Key
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)

    # Email Content
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)

    # Recipients
    to_email = Column(String(255), nullable=False)
    to_name = Column(String(255), nullable=True)
    cc_emails = Column(String(500), nullable=True)  # Comma-separated

    # Status
    status = Column(
        Enum(EmailStatus),
        default=EmailStatus.PENDING_APPROVAL,
        nullable=False,
        index=True
    )

    # Approval workflow
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_reason = Column(Text, nullable=True)

    # Edit history
    original_subject = Column(String(500), nullable=True)
    original_body = Column(Text, nullable=True)
    edit_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job = relationship("Job", back_populates="email_drafts")
    application_records = relationship("ApplicationRecord", back_populates="email_draft")

    def __repr__(self):
        return f"<EmailDraft(id={self.id}, to='{self.to_email}', status={self.status.value})>"

    def approve(self, approved_by: str = "user"):
        """Mark email as approved."""
        self.status = EmailStatus.APPROVED
        self.approved_by = approved_by
        self.approved_at = datetime.utcnow()

    def reject(self, reason: str = None):
        """Mark email as rejected."""
        self.status = EmailStatus.REJECTED
        self.rejected_reason = reason

    def edit_content(self, new_subject: str = None, new_body: str = None):
        """Edit email content and track changes."""
        if self.edit_count == 0:
            # Save original on first edit
            self.original_subject = self.subject
            self.original_body = self.body

        if new_subject:
            self.subject = new_subject
        if new_body:
            self.body = new_body

        self.edit_count += 1
        self.updated_at = datetime.utcnow()

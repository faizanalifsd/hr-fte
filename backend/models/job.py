"""
Job Model - Represents a scraped job listing.
"""

from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from . import Base


class JobStatus(enum.Enum):
    """Job status enumeration."""
    SCRAPED = "Scraped"
    MATCHED = "Matched"
    SELECTED = "Selected"
    CV_OPTIMIZED = "CV_Optimized"
    EMAIL_DRAFTED = "Email_Drafted"
    PENDING_APPROVAL = "Pending_Approval"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    APPLIED = "Applied"
    FAILED = "Failed"


class Job(Base):
    """
    Job entity - represents a job listing from scraping.

    Workflow:
    1. Scraped from job portals (Phase 4)
    2. Randomly selected (5 jobs) in Phase 5
    3. CV optimized (Phase 6)
    4. Email drafted (Phase 7)
    5. Human approval (Phase 8)
    6. Application sent (Phase 9)
    """
    __tablename__ = "jobs"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Key
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False, index=True)

    # Job Details
    company = Column(String(255), nullable=False, index=True)
    role = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    job_type = Column(String(100), nullable=True)  # Full-time, Contract, etc.

    # Job Description
    description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=True)  # JSON array as text

    # Application Details
    apply_link = Column(String(500), nullable=True)
    hr_email = Column(String(255), nullable=True, index=True)
    hr_name = Column(String(255), nullable=True)
    hr_title = Column(String(255), nullable=True)           # Phase 4C: Apollo job title
    hr_email_confidence = Column(String(50), nullable=True) # Phase 4C: "verified"|"likely"|"none"

    # Selection metadata (Phase 5 — random pick)
    match_score = Column(Float, nullable=True, index=True)
    matched_skills = Column(Text, nullable=True)  # JSON array as text
    missing_skills = Column(Text, nullable=True)  # JSON array as text
    experience_alignment = Column(String(50), nullable=True)

    # Status
    status = Column(
        Enum(JobStatus),
        default=JobStatus.SCRAPED,
        nullable=False,
        index=True
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)

    # Scraping metadata
    source_portal = Column(String(100), nullable=True)  # LinkedIn, Indeed, etc.
    job_posting_date = Column(DateTime, nullable=True)

    # Relationships
    mission = relationship("Mission", back_populates="jobs")
    cv_versions = relationship("CVVersion", back_populates="job", cascade="all, delete-orphan")
    email_drafts = relationship("EmailDraft", back_populates="job", cascade="all, delete-orphan")
    application_records = relationship("ApplicationRecord", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job(id={self.id}, company='{self.company}', role='{self.role}', score={self.match_score})>"

    def should_apply(self) -> bool:
        """Return True if this job was selected (Phase 5 random pick)."""
        return self.status == JobStatus.SELECTED

    def recommendation(self) -> str:
        """Get application recommendation based on selection status."""
        if self.status == JobStatus.SELECTED:
            return "Apply"
        return "Not Selected"

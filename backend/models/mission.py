"""
Mission Model - Represents a job application mission.
"""

from sqlalchemy import Column, Integer, String, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from . import Base


class MissionStatus(enum.Enum):
    """Mission status enumeration."""
    INITIALIZED = "Initialized"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    FAILED = "Failed"


class Mission(Base):
    """
    Mission entity - represents a job application campaign.

    As per constitution.md:
    - Must contain: target role, target count, optional time constraint
    - Status states: Initialized, Running, Paused, Completed, Failed
    - Marked Completed only when target count achieved and all logged
    """
    __tablename__ = "missions"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Mission Details
    target_role = Column(String(255), nullable=False, index=True)
    target_count = Column(Integer, nullable=False)
    progress_count = Column(Integer, default=0)

    # Optional time constraint (in days)
    time_constraint_days = Column(Integer, nullable=True)

    # Status
    status = Column(
        Enum(MissionStatus),
        default=MissionStatus.INITIALIZED,
        nullable=False,
        index=True
    )

    # Additional filters/preferences
    location_preference = Column(String(255), nullable=True)
    salary_min = Column(Integer, nullable=True)
    job_type = Column(String(100), nullable=True)  # Full-time, Contract, etc.

    # Notes
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Rate limiting (per constitution.md - default max 20/day)
    daily_application_limit = Column(Integer, default=20)

    # Relationships
    jobs = relationship("Job", back_populates="mission", cascade="all, delete-orphan")
    cv_versions = relationship("CVVersion", back_populates="mission", cascade="all, delete-orphan")
    execution_states = relationship("ExecutionState", back_populates="mission", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="mission", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Mission(id={self.id}, role='{self.target_role}', status={self.status.value})>"

    def is_complete(self) -> bool:
        """Check if mission has reached its target."""
        return self.progress_count >= self.target_count

    def can_apply_more(self) -> bool:
        """Check if mission can accept more applications."""
        return (
            self.status == MissionStatus.RUNNING and
            self.progress_count < self.target_count
        )

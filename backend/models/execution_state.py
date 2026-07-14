"""
ExecutionState Model - Tracks real-time execution state of mission workflow.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from . import Base


class ExecutionStatus(enum.Enum):
    """Execution state enumeration."""
    IDLE = "Idle"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    PAUSED = "Paused"


class ExecutionPhase(enum.Enum):
    """Workflow phase enumeration (12 phases from execution_plan.md)."""
    MISSION_INIT = "Mission_Initialization"
    CV_UPLOAD = "CV_Upload"
    CV_PARSING = "CV_Parsing"
    JOB_SCRAPING = "Job_Scraping"
    JOB_MATCHING = "Job_Matching"
    CV_VERSIONING = "CV_Versioning"
    EMAIL_GENERATION = "Email_Generation"
    HITL_APPROVAL = "HITL_Approval"
    APPLICATION_SENDING = "Application_Sending"
    EVIDENCE_AUDIT = "Evidence_Audit"
    MISSION_VALIDATION = "Mission_Validation"
    GRAPH_UPDATE = "Graph_Update"


class ExecutionState(Base):
    """
    ExecutionState entity - real-time workflow tracking.

    As per constitution.md Section 10:
    - Execution state must be trackable
    - States: Idle, Running, Completed, Failed
    - Graph view reflects real-time execution state
    """
    __tablename__ = "execution_states"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Key
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False, index=True)

    # Current Phase
    current_phase = Column(
        Enum(ExecutionPhase),
        nullable=False,
        index=True
    )

    # Status
    status = Column(
        Enum(ExecutionStatus),
        default=ExecutionStatus.IDLE,
        nullable=False,
        index=True
    )

    # Progress tracking
    phase_progress = Column(Integer, default=0)  # 0-100 percentage
    total_progress = Column(Integer, default=0)  # Overall mission progress 0-100

    # Current job being processed
    current_job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)

    # Execution details
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Metadata
    context_data = Column(Text, nullable=True)  # JSON for additional context

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    mission = relationship("Mission", back_populates="execution_states")

    def __repr__(self):
        return f"<ExecutionState(mission_id={self.mission_id}, phase={self.current_phase.value}, status={self.status.value})>"

    def heartbeat(self):
        """Update last heartbeat timestamp."""
        self.last_heartbeat = datetime.utcnow()

    def start_phase(self, phase: ExecutionPhase):
        """Start a new execution phase."""
        self.current_phase = phase
        self.status = ExecutionStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.error_message = None
        self.heartbeat()

    def complete_phase(self):
        """Mark current phase as completed."""
        self.status = ExecutionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.phase_progress = 100
        self.heartbeat()

    def fail_phase(self, error_message: str):
        """Mark current phase as failed."""
        self.status = ExecutionStatus.FAILED
        self.error_message = error_message
        self.retry_count += 1
        self.heartbeat()
